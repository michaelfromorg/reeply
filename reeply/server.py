from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
from datetime import datetime
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Message(BaseModel):
    date: str
    type: int


class Thread(BaseModel):
    address: str
    messages: List[Message]
    first_message: str
    last_message: str


def get_db():
    db = sqlite3.connect("replies.db")
    db.row_factory = sqlite3.Row
    return db


@app.get("/api/threads", response_model=List[Thread])
async def get_threads(offset: int = 0, limit: int = 50):
    db = get_db()
    try:
        cursor = db.cursor()
        # First get the thread addresses with proper sorting
        cursor.execute(
            """
            WITH thread_bounds AS (
                SELECT 
                    address,
                    MIN(date) as first_message,
                    MAX(date) as last_message
                FROM messages
                GROUP BY address
            )
            SELECT 
                address,
                first_message,
                last_message
            FROM thread_bounds
            ORDER BY first_message ASC, last_message ASC
            LIMIT ? OFFSET ?
        """,
            (limit, offset),
        )

        threads = []
        for row in cursor.fetchall():
            # For each thread, get all its messages
            cursor.execute(
                """
                SELECT date, type
                FROM messages
                WHERE address = ?
                ORDER BY date ASC
            """,
                (row["address"],),
            )

            messages = [dict(msg) for msg in cursor.fetchall()]

            threads.append(
                {
                    "address": row["address"],
                    "messages": messages,
                    "first_message": row["first_message"],
                    "last_message": row["last_message"],
                }
            )

        return threads
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
