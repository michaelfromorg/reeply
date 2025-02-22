import os
from pathlib import Path
import json
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any

from db_init import init_db
from process_messages import process_messages
from process_calls import process_calls, get_call_type_display, format_duration
from notion_sync import NotionSync, sync_contacts_to_notion

from dotenv import load_dotenv

SMS_BACKUP_PATH = r"/mnt/c/Users/mdema/Dropbox/Apps/SMSBackupRestore"
DEBUG = False

load_dotenv()  # Load .env file
notion_token = os.getenv("NOTION_TOKEN")
notion_db = os.getenv("NOTION_DATABASE_ID")

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("reply_analyzer.log"), logging.StreamHandler()],
)


def update_contact_summaries(conn) -> List[Dict[str, Any]]:
    """
    Update contact_summaries table with latest data
    Returns list of contacts needing replies
    """
    cursor = conn.cursor()

    # Update or insert contact summaries
    cursor.execute("""
        INSERT OR REPLACE INTO contact_summaries (
            address,
            last_message_timestamp,
            last_call_timestamp,
            last_outbound_timestamp,
            recent_messages,
            needs_reply
        )
        SELECT 
            address,
            MAX(message_date) as last_message,
            MAX(call_date) as last_call,
            MAX(outbound_date) as last_outbound,
            json_group_array(message) as recent_msgs,
            CASE 
                WHEN MAX(message_date) > MAX(outbound_date) 
                AND julianday('now') - julianday(MAX(message_date)) > 2
                AND NOT is_short
                THEN 1
                ELSE 0
            END as needs_reply
        FROM (
            -- Get latest message dates
            SELECT 
                address,
                date as message_date,
                NULL as call_date,
                CASE WHEN type = 2 THEN date END as outbound_date,
                json_object('date', date, 'body', body, 'type', type) as message,
                is_short
            FROM messages
            UNION ALL
            -- Get latest call dates
            SELECT 
                address,
                NULL as message_date,
                date as call_date,
                CASE WHEN type = 2 THEN date END as outbound_date,
                NULL as message,
                0 as is_short
            FROM calls
        ) combined
        GROUP BY address
    """)

    # Get contacts needing replies
    cursor.execute("""
        SELECT 
            address,
            last_message_timestamp,
            recent_messages
        FROM contact_summaries
        WHERE needs_reply = 1
        ORDER BY last_message_timestamp DESC
    """)

    logging.debug("Raw query results:")

    needs_reply = []
    for row in cursor.fetchall():
        address, last_msg_date, recent_msgs = row
        logging.debug(f"Raw recent_msgs: {recent_msgs}")
        parsed_msgs = json.loads(recent_msgs) if recent_msgs else []
        logging.debug(f"Parsed messages: {parsed_msgs}")
        if isinstance(parsed_msgs, list):
            recent = parsed_msgs[-3:]  # Last 3 messages
        else:
            recent = [parsed_msgs] if parsed_msgs else []
        needs_reply.append(
            {
                "address": address,
                "last_message": last_msg_date,
                "recent_messages": recent,
            }
        )

    conn.commit()
    return needs_reply


def generate_report(conn, needs_reply: List[Dict[str, Any]], output_path: Path):
    """Generate a summary report of the processing run"""
    logging.debug("Needs reply data:")
    for contact in needs_reply:
        logging.debug(f"Contact: {contact['address']}")
        logging.debug(
            f"Recent messages (type: {type(contact['recent_messages'])}): {contact['recent_messages']}"
        )
    cursor = conn.cursor()

    # Get stats from latest run
    cursor.execute("""
        SELECT 
            r.id,
            r.run_date,
            (SELECT COUNT(*) FROM messages WHERE processed_run_id = r.id) as new_messages,
            (SELECT COUNT(*) FROM calls WHERE processed_run_id = r.id) as new_calls
        FROM runs r
        ORDER BY r.run_date DESC
        LIMIT 1
    """)
    run_stats = cursor.fetchone()

    # Get contacts not contacted in 30 days
    cursor.execute("""
        SELECT 
            address,
            last_message_timestamp,
            last_call_timestamp
        FROM contact_summaries
        WHERE (
            julianday('now') - julianday(COALESCE(last_message_timestamp, last_call_timestamp)) > 30
        )
        ORDER BY COALESCE(last_message_timestamp, last_call_timestamp) DESC
    """)
    inactive_contacts = cursor.fetchall()

    # Generate report
    with open(output_path, "w") as f:
        f.write(
            f"Reply Analyzer Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        f.write("=" * 80 + "\n\n")

        # Processing stats
        f.write("Processing Statistics:\n")
        f.write(f"- Run ID: {run_stats[0]}\n")
        f.write(f"- Run Date: {run_stats[1]}\n")
        f.write(f"- New Messages Processed: {run_stats[2]}\n")
        f.write(f"- New Calls Processed: {run_stats[3]}\n\n")

        # Needs reply
        f.write(f"Messages Needing Replies ({len(needs_reply)}):\n")
        for contact in needs_reply:
            f.write(f"\nContact: {contact['address']}\n")
            f.write(f"Last Message: {contact['last_message']}\n")
            f.write("Recent Messages:\n")
            messages = contact["recent_messages"]
            logging.debug(f"Processing messages for report: {messages}")
            for msg in messages:
                if msg is not None and isinstance(msg, str):
                    msg = json.loads(msg)
                    direction = "←" if msg["type"] == 1 else "→"
                    f.write(f"  {msg['date']} {direction} {msg['body'][:100]}...\n")
        f.write("\n")

        # Inactive contacts
        f.write(f"\nInactive Contacts (30+ days) ({len(inactive_contacts)}):\n")
        for address, last_msg, last_call in inactive_contacts:
            latest = (
                max(last_msg, last_call)
                if last_msg and last_call
                else (last_msg or last_call)
            )
            days_ago = (datetime.now() - datetime.fromisoformat(latest)).days
            f.write(f"- {address}: Last contact {days_ago} days ago ({latest})\n")


def format_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def list_backup_files() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    files = os.listdir(SMS_BACKUP_PATH)
    print(files)
    xml_files = [f for f in files if f.endswith(".xml")]
    if DEBUG:
        xml_files = [f for f in xml_files if f.startswith("test_")]
    else:
        xml_files = [f for f in xml_files if not f.startswith("test_")]

    sms_files = [
        (f, format_size(os.path.getsize(os.path.join(SMS_BACKUP_PATH, f))))
        for f in xml_files
        if f.startswith("sms-")
    ]

    call_files = [
        (f, format_size(os.path.getsize(os.path.join(SMS_BACKUP_PATH, f))))
        for f in xml_files
        if f.startswith("calls-")
    ]

    return sms_files, call_files


def main():
    # Set debug level for troubleshooting
    logging.getLogger().setLevel(logging.DEBUG)
    logging.info("Starting Reply Analyzer processing run")

    # Get latest backup files
    sms_files, call_files = list_backup_files()

    if not sms_files or not call_files:
        logging.error("No backup files found")
        return

    # Get most recent files
    sms_path = Path(os.path.join(SMS_BACKUP_PATH, sms_files[0][0]))
    calls_path = Path(os.path.join(SMS_BACKUP_PATH, call_files[0][0]))

    logging.info(f"Using SMS backup: {sms_path} ({sms_files[0][1]})")
    logging.info(f"Using calls backup: {calls_path} ({call_files[0][1]})")

    # Initialize database connection
    conn = init_db()

    try:
        # Get last run date
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(run_date) FROM runs")
        last_run = cursor.fetchone()[0]
        if last_run:
            last_run = datetime.fromisoformat(last_run)
            logging.info(f"Last run: {last_run}")
        else:
            logging.info("First run - processing all messages")

        # Process messages
        # sms_path = Path("test_sms-20250222112816.xml")
        new_messages = process_messages(conn, sms_path, last_run)
        logging.info(f"Processed {new_messages} new messages")

        # Process calls
        # calls_path = Path("test_calls-20250222112816.xml")
        new_calls = process_calls(conn, calls_path, last_run)
        logging.info(f"Processed {new_calls} new calls")

        # Update summaries and get contacts needing replies
        needs_reply = update_contact_summaries(conn)
        logging.info(f"Found {len(needs_reply)} contacts needing replies")

        # Generate report
        report_path = Path(f"report_{datetime.now().strftime('%Y%m%d')}.txt")
        generate_report(conn, needs_reply, report_path)
        logging.info(f"Generated report: {report_path}")

        notion = NotionSync(database_id=notion_db, notion_token=notion_token)
        updates, not_found = sync_contacts_to_notion(conn, notion)
        logging.info(f"Notion sync complete: {updates} updated, {not_found} not found")
    except Exception as e:
        logging.error(f"Error during processing: {e}", exc_info=True)
        raise
    finally:
        conn.close()
        logging.info("Processing complete")


if __name__ == "__main__":
    main()
