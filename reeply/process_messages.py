"""
The driver to process SMS message data.
"""

import sqlite3
from pathlib import Path
import xml.etree.ElementTree as ET
from datetime import datetime
import json


def is_short_message(body: str) -> bool:
    """
    Determine if a message is a short confirmation/response
    Returns True for things like "ok", "thanks", "sure", etc.
    """
    if not body:
        return True

    # Convert to lowercase and strip whitespace
    text = body.lower().strip()

    # List of common short responses
    short_responses = {
        "ok",
        "k",
        "kk",
        "yes",
        "no",
        "yeah",
        "nah",
        "sure",
        "thanks",
        "thx",
        "ty",
        "np",
        "lol",
    }

    # Check if it's a short response or very short message
    return (
        text in short_responses
        or len(text.split()) <= 2  # 2 or fewer words
        or len(text) <= 5
    )  # 5 or fewer characters


def process_messages(
    conn: sqlite3.Connection, xml_path: Path, last_run_date: datetime = None
) -> int:
    """
    Process SMS messages from XML backup file
    Returns number of new messages processed
    """
    cursor = conn.cursor()

    # Start a new processing run
    cursor.execute(
        "INSERT INTO runs (run_date) VALUES (CURRENT_TIMESTAMP) RETURNING id"
    )
    run_id = cursor.fetchone()[0]

    # Parse XML
    tree = ET.parse(xml_path)
    root = tree.getroot()

    new_messages = 0

    for sms in root.findall("sms"):
        # Convert timestamp from milliseconds to datetime
        date = datetime.fromtimestamp(int(sms.get("date")) / 1000)

        # Skip if before last run
        if last_run_date and date <= last_run_date:
            continue

        # Generate unique ID from date and address
        msg_id = f"{sms.get('date')}_{sms.get('address')}"

        try:
            cursor.execute(
                """
                INSERT INTO messages (
                    id, address, date, type, body, is_short, processed_run_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    msg_id,
                    sms.get("address"),
                    date.isoformat(),
                    int(sms.get("type")),
                    sms.get("body"),
                    is_short_message(sms.get("body")),
                    run_id,
                ),
            )
            new_messages += 1
        except sqlite3.IntegrityError:
            # Skip if message already exists
            continue

    # Update run with last processed message date
    if new_messages > 0:
        cursor.execute(
            """
            UPDATE runs 
            SET last_message_processed = (
                SELECT MAX(date) FROM messages 
                WHERE processed_run_id = ?
            )
            WHERE id = ?
        """,
            (run_id, run_id),
        )

    conn.commit()
    return new_messages


if __name__ == "__main__":
    from db_init import init_db  # Import our database initialization

    # Connect to database
    conn = init_db()

    # Get last run date
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(run_date) FROM runs")
    last_run = cursor.fetchone()[0]
    if last_run:
        last_run = datetime.fromisoformat(last_run)

    # Process messages from test XML
    xml_path = Path("test_sms-20250222112816.xml")
    new_count = process_messages(conn, xml_path, last_run)
    print(f"Processed {new_count} new messages")

    # Show some sample data
    cursor.execute("""
        SELECT date, address, type, body, is_short 
        FROM messages 
        ORDER BY date DESC 
        LIMIT 5
    """)
    print("\nLatest messages:")
    for msg in cursor.fetchall():
        print(f"{msg[0]} - {msg[1]}: {'→' if msg[2] == 2 else '←'} {msg[3][:50]}...")

    conn.close()
