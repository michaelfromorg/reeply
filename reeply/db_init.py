import sqlite3
from pathlib import Path

DB_PATH = Path("replies.db")

def init_db():
    """Initialize the SQLite database with our schema"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create runs table to track our processing history
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_message_processed TIMESTAMP
    )
    """)

    # Store processed messages
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        address TEXT NOT NULL,
        date TIMESTAMP NOT NULL,
        type INTEGER NOT NULL,  -- 1=received, 2=sent
        body TEXT,
        is_short BOOLEAN NOT NULL,  -- For filtering one-word responses
        processed_run_id INTEGER,
        FOREIGN KEY(processed_run_id) REFERENCES runs(id)
    )
    """)

    # Create index on messages date for faster lookups
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_messages_date 
    ON messages(date)
    """)

    # Store call history
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS calls (
        id TEXT PRIMARY KEY,
        address TEXT NOT NULL,
        date TIMESTAMP NOT NULL,
        duration INTEGER,
        type INTEGER NOT NULL,  -- 1=incoming, 2=outgoing, 3=missed
        processed_run_id INTEGER,
        FOREIGN KEY(processed_run_id) REFERENCES runs(id)
    )
    """)

    # Create index on calls date
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_calls_date 
    ON calls(date)
    """)

    # Contact summary table - updated after each run
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contact_summaries (
        address TEXT PRIMARY KEY,
        last_message_timestamp TIMESTAMP,
        last_call_timestamp TIMESTAMP,
        last_outbound_timestamp TIMESTAMP,
        recent_messages TEXT,  -- JSON array of last 3 messages
        needs_reply BOOLEAN,
        notion_id TEXT         -- For future Notion sync
    )
    """)

    conn.commit()
    return conn

def get_last_run_date(conn):
    """Get the date of the last successful run, or None if first run"""
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(run_date) FROM runs")
    result = cursor.fetchone()
    return result[0] if result and result[0] else None

if __name__ == "__main__":
    print(f"Initializing database at {DB_PATH}...")
    conn = init_db()
    print("Database initialized successfully!")
    
    last_run = get_last_run_date(conn)
    print(f"Last run date: {last_run or 'No previous runs'}")
    
    conn.close()
