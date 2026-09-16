import sqlite3
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from src.config import settings
from src.models.channel import ChannelEvent, ChannelUser
from src.models.session import ActiveTripSession, ExpenseItem

class DatabaseManager:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.SQLITE_DB_PATH
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for high concurrency
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            # 1. Group Messages Buffer
            conn.execute("""
                CREATE TABLE IF NOT EXISTS group_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE,
                    channel_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    sender_id TEXT NOT NULL,
                    sender_name TEXT NOT NULL,
                    text TEXT,
                    has_media INTEGER DEFAULT 0,
                    media_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_group_messages_channel ON group_messages(channel_id, created_at DESC);")

            # 2. Active Trips
            conn.execute("""
                CREATE TABLE IF NOT EXISTS active_trips (
                    session_id TEXT PRIMARY KEY,
                    channel_id TEXT UNIQUE NOT NULL,
                    status TEXT NOT NULL,
                    destination TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    participants_json TEXT,
                    itinerary_json TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 3. Trip Expenses
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trip_expenses (
                    expense_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    paid_by_user_id TEXT NOT NULL,
                    paid_by_name TEXT NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'USD',
                    description TEXT NOT NULL,
                    split_between_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

    def buffer_message(self, event: ChannelEvent):
        """Silently inserts group message into the short-term sliding buffer."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO group_messages 
                (event_id, channel_id, platform, sender_id, sender_name, text, has_media, media_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id,
                event.channel_id,
                event.platform,
                event.sender.id,
                event.sender.name,
                event.text or "",
                1 if event.media else 0,
                event.media.type if event.media else None
            ))
            conn.commit()

    def get_recent_group_messages(self, channel_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        """Retrieves preceding N group messages in chronological order for arbitration."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT sender_name, text, media_type, created_at
                FROM group_messages
                WHERE channel_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (channel_id, limit))
            rows = cursor.fetchall()
            # Reverse to return chronological order
            return [dict(r) for r in reversed(rows)]

    def save_active_trip(self, trip: ActiveTripSession):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO active_trips (session_id, channel_id, status, destination, start_date, end_date, participants_json, itinerary_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(channel_id) DO UPDATE SET
                    session_id=excluded.session_id,
                    status=excluded.status,
                    destination=excluded.destination,
                    start_date=excluded.start_date,
                    end_date=excluded.end_date,
                    participants_json=excluded.participants_json,
                    itinerary_json=excluded.itinerary_json,
                    updated_at=CURRENT_TIMESTAMP
            """, (
                trip.session_id,
                trip.channel_id,
                trip.status,
                trip.destination,
                trip.start_date,
                trip.end_date,
                json.dumps([p.dict() for p in trip.participants]),
                json.dumps([i.dict() for i in trip.itinerary])
            ))
            conn.commit()

    def get_active_trip(self, channel_id: str) -> Optional[ActiveTripSession]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM active_trips WHERE channel_id = ?", (channel_id,))
            row = cursor.fetchone()
            if not row:
                return None
            
            expenses = self.get_trip_expenses(row["session_id"])
            return ActiveTripSession(
                session_id=row["session_id"],
                channel_id=row["channel_id"],
                status=row["status"],
                destination=row["destination"],
                start_date=row["start_date"],
                end_date=row["end_date"],
                participants=json.loads(row["participants_json"] or "[]"),
                itinerary=json.loads(row["itinerary_json"] or "[]"),
                expenses=expenses
            )

    def add_expense(self, session_id: str, expense: ExpenseItem):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO trip_expenses (expense_id, session_id, paid_by_user_id, paid_by_name, amount, currency, description, split_between_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                expense.expense_id,
                session_id,
                expense.paid_by_user_id,
                expense.paid_by_name,
                expense.amount,
                expense.currency,
                expense.description,
                json.dumps(expense.split_between_user_ids)
            ))
            conn.commit()

    def get_trip_expenses(self, session_id: str) -> List[ExpenseItem]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM trip_expenses WHERE session_id = ? ORDER BY created_at ASC", (session_id,))
            rows = cursor.fetchall()
            return [
                ExpenseItem(
                    expense_id=r["expense_id"],
                    paid_by_user_id=r["paid_by_user_id"],
                    paid_by_name=r["paid_by_name"],
                    amount=r["amount"],
                    currency=r["currency"],
                    description=r["description"],
                    split_between_user_ids=json.loads(r["split_between_json"])
                )
                for r in rows
            ]

db = DatabaseManager()
