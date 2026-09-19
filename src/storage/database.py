import sqlite3
import json
from typing import List, Optional, Dict, Any
from src.config import settings
from src.models.channel import ChannelEvent
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

            # 3. Trip Expenses with Consent Tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trip_expenses (
                    expense_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    paid_by_user_id TEXT NOT NULL,
                    paid_by_name TEXT NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'SGD',
                    description TEXT NOT NULL,
                    split_between_json TEXT NOT NULL,
                    confirmed_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'pending_confirmation',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Safe column additions if table already existed
            try:
                conn.execute("ALTER TABLE trip_expenses ADD COLUMN confirmed_json TEXT NOT NULL DEFAULT '[]';")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE trip_expenses ADD COLUMN status TEXT NOT NULL DEFAULT 'pending_confirmation';")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE group_messages ADD COLUMN media_json TEXT;")
            except Exception:
                pass

            # 4. Long-term User Memory & Preferences
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_memory (
                    user_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, key)
                );
            """)
            conn.commit()

    def buffer_message(self, event: ChannelEvent):
        """Silently inserts group message into the short-term sliding buffer."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO group_messages 
                (event_id, channel_id, platform, sender_id, sender_name, text, has_media, media_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    event.event_id,
                    event.channel_id,
                    event.platform,
                    event.sender.id,
                    event.sender.name,
                    event.text or "",
                    1 if event.media else 0,
                    event.media.type if event.media else None,
                ),
            )
            conn.commit()

    def get_recent_group_messages(self, channel_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        """Retrieves preceding N group messages in chronological order for arbitration."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT sender_name, text, media_type, created_at
                FROM group_messages
                WHERE channel_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """,
                (channel_id, limit),
            )
            rows = cursor.fetchall()
            # Reverse to return chronological order
            return [dict(r) for r in reversed(rows)]

    def save_active_trip(self, trip: ActiveTripSession):
        with self._get_connection() as conn:
            conn.execute(
                """
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
            """,
                (
                    trip.session_id,
                    trip.channel_id,
                    trip.status,
                    trip.destination,
                    trip.start_date,
                    trip.end_date,
                    json.dumps([p.dict() for p in trip.participants]),
                    json.dumps([i.dict() for i in trip.itinerary]),
                ),
            )
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
                expenses=expenses,
            )

    def add_expense(self, session_id: str, expense: ExpenseItem):
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO trip_expenses (expense_id, session_id, paid_by_user_id, paid_by_name, amount, currency, description, split_between_json, confirmed_json, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    expense.expense_id,
                    session_id,
                    expense.paid_by_user_id,
                    expense.paid_by_name,
                    expense.amount,
                    expense.currency,
                    expense.description,
                    json.dumps(expense.split_between_user_ids),
                    json.dumps(expense.confirmed_by_user_ids),
                    expense.status,
                ),
            )
            conn.commit()

    def get_trip_expenses(self, session_id: str) -> List[ExpenseItem]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM trip_expenses WHERE session_id = ? ORDER BY created_at ASC", (session_id,))
            rows = cursor.fetchall()
            expenses = []
            for r in rows:
                keys = r.keys()
                confirmed = json.loads(r["confirmed_json"]) if "confirmed_json" in keys and r["confirmed_json"] else []
                status = r["status"] if "status" in keys and r["status"] else "pending_confirmation"
                expenses.append(
                    ExpenseItem(
                        expense_id=r["expense_id"],
                        paid_by_user_id=r["paid_by_user_id"],
                        paid_by_name=r["paid_by_name"],
                        amount=r["amount"],
                        currency=r["currency"] or "SGD",
                        description=r["description"],
                        split_between_user_ids=json.loads(r["split_between_json"]),
                        confirmed_by_user_ids=confirmed,
                        status=status,
                    )
                )
            return expenses

    def confirm_expense_participant(
        self, session_id: str, participant_name_or_id: str, expense_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Registers participant consent/confirmation for an expense.
        Marks them as confirmed. If all split participants confirmed, marks status='confirmed'.
        Returns list of updated expense summaries.
        """
        p_clean = participant_name_or_id.strip().lower()
        updated = []
        with self._get_connection() as conn:
            if expense_id:
                cursor = conn.execute("SELECT * FROM trip_expenses WHERE session_id = ? AND expense_id = ?", (session_id, expense_id))
            else:
                cursor = conn.execute(
                    "SELECT * FROM trip_expenses WHERE session_id = ? AND status = 'pending_confirmation' ORDER BY created_at DESC",
                    (session_id,),
                )
            rows = cursor.fetchall()

            for r in rows:
                keys = r.keys()
                split_members = json.loads(r["split_between_json"])
                confirmed = json.loads(r["confirmed_json"]) if "confirmed_json" in keys and r["confirmed_json"] else []

                # Payer is always considered confirmed
                payer_name = r["paid_by_name"]
                if payer_name not in confirmed:
                    confirmed.append(payer_name)

                # Match participant
                matched_name = next(
                    (m for m in split_members if m.lower() == p_clean or p_clean in m.lower()), participant_name_or_id.strip()
                )
                if matched_name not in confirmed:
                    confirmed.append(matched_name)

                # Check if all split members confirmed
                all_confirmed = all(any(c.lower() == m.lower() or m.lower() in c.lower() for c in confirmed) for m in split_members)
                new_status = "confirmed" if all_confirmed else "pending_confirmation"

                conn.execute(
                    """
                    UPDATE trip_expenses 
                    SET confirmed_json = ?, status = ?
                    WHERE expense_id = ?
                """,
                    (json.dumps(confirmed), new_status, r["expense_id"]),
                )

                pending_names = [m for m in split_members if not any(c.lower() == m.lower() or m.lower() in c.lower() for c in confirmed)]
                updated.append(
                    {
                        "expense_id": r["expense_id"],
                        "description": r["description"],
                        "amount": r["amount"],
                        "currency": r["currency"] or "SGD",
                        "confirmed_by": confirmed,
                        "pending_for": pending_names,
                        "status": new_status,
                    }
                )
            conn.commit()
        return updated

    def set_user_memory(self, user_id: str, key: str, value: str):
        """Persists a key-value user preference or attribute (e.g. home_city, origin_airport)."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO user_memory (user_id, key, value, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, key) DO UPDATE SET
                    value=excluded.value,
                    updated_at=CURRENT_TIMESTAMP
            """,
                (user_id, key, value),
            )
            conn.commit()

    def get_user_memories(self, user_id: str) -> Dict[str, str]:
        """Retrieves all stored long-term preferences/attributes for a given user."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT key, value FROM user_memory WHERE user_id = ?", (user_id,))
            return {row["key"]: row["value"] for row in cursor.fetchall()}


db = DatabaseManager()
