"""
The driver to process phone call data.
"""

import sqlite3
from pathlib import Path
import xml.etree.ElementTree as ET
from datetime import datetime


def process_calls(
    conn: sqlite3.Connection, xml_path: Path, last_run_date: datetime = None
) -> int:
    """
    Process call logs from XML backup file
    Returns number of new calls processed

    Call types from XML:
        1 = incoming
        2 = outgoing
        3 = missed
        5 = rejected
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

    new_calls = 0

    for call in root.findall("call"):
        # Convert timestamp from milliseconds to datetime
        date = datetime.fromtimestamp(int(call.get("date")) / 1000)

        # Skip if before last run
        if last_run_date and date <= last_run_date:
            continue

        # Generate unique ID from date and number
        call_id = f"{call.get('date')}_{call.get('number')}"

        try:
            cursor.execute(
                """
                INSERT INTO calls (
                    id, address, date, duration, type, processed_run_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    call_id,
                    call.get("number"),
                    date.isoformat(),
                    int(call.get("duration", 0)),
                    int(call.get("type")),
                    run_id,
                ),
            )
            new_calls += 1
        except sqlite3.IntegrityError:
            # Skip if call already exists
            continue

    # Update run with last processed call date
    if new_calls > 0:
        cursor.execute(
            """
            UPDATE runs 
            SET last_message_processed = (
                SELECT MAX(date) FROM calls 
                WHERE processed_run_id = ?
            )
            WHERE id = ?
        """,
            (run_id, run_id),
        )

    conn.commit()
    return new_calls


def get_call_type_display(type_code: int) -> str:
    """Convert numeric call type to display string"""
    return {1: "incoming", 2: "outgoing", 3: "missed", 5: "rejected"}.get(
        type_code, "unknown"
    )


def format_duration(seconds: int) -> str:
    """Format call duration in seconds to human readable string"""
    if seconds == 0:
        return "no duration"
    elif seconds < 60:
        return f"{seconds}s"
    else:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds}s"


if __name__ == "__main__":
    from db_init import init_db

    # Connect to database
    conn = init_db()

    # Get last run date
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(run_date) FROM runs")
    last_run = cursor.fetchone()[0]
    if last_run:
        last_run = datetime.fromisoformat(last_run)

    # Process calls from test XML
    xml_path = Path("test_calls-20250222112816.xml")
    new_count = process_calls(conn, xml_path, last_run)
    print(f"Processed {new_count} new calls")

    # Show some sample data
    cursor.execute("""
        SELECT date, address, type, duration 
        FROM calls 
        ORDER BY date DESC 
        LIMIT 5
    """)
    print("\nLatest calls:")
    for call in cursor.fetchall():
        date, number, type_code, duration = call
        call_type = get_call_type_display(type_code)
        duration_str = format_duration(duration)
        print(f"{date} - {number}: {call_type} ({duration_str})")

    conn.close()
