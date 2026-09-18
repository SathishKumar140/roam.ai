import json
import sqlite3
import time
import uuid
import random
import re
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation

from src.models.channel import ChannelEvent


class RoamAIStore:
    def __init__(self, path: str):
        self.path = path
        with self.connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS roamai_groups (
                    id TEXT PRIMARY KEY, platform TEXT NOT NULL, channel_id TEXT NOT NULL,
                    connection_id TEXT NOT NULL, last_offer REAL NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS roamai_inbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, group_id TEXT NOT NULL,
                    event_id TEXT NOT NULL, payload TEXT NOT NULL, received REAL NOT NULL,
                    available REAL NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0, lease REAL NOT NULL DEFAULT 0,
                    notify_failure INTEGER NOT NULL DEFAULT 0, error TEXT,
                    UNIQUE(group_id, event_id)
                );
                CREATE INDEX IF NOT EXISTS roamai_inbox_ready ON roamai_inbox(state, available);
                CREATE TABLE IF NOT EXISTS roamai_topics (
                    id TEXT PRIMARY KEY, group_id TEXT NOT NULL, title TEXT NOT NULL,
                    summary TEXT NOT NULL, intent TEXT NOT NULL, participants TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'observed', updated REAL NOT NULL,
                    offered_to TEXT, last_offer REAL NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS roamai_topics_group ON roamai_topics(group_id, updated);
                CREATE TABLE IF NOT EXISTS roamai_preferences (
                    group_id TEXT NOT NULL, user_id TEXT NOT NULL, key TEXT NOT NULL,
                    value TEXT NOT NULL, evidence_id TEXT NOT NULL, updated REAL NOT NULL,
                    PRIMARY KEY(group_id, user_id, key)
                );
                CREATE TABLE IF NOT EXISTS roamai_outbox (
                    id TEXT PRIMARY KEY, group_id TEXT NOT NULL, topic_id TEXT,
                    payload TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0, available REAL NOT NULL,
                    created REAL NOT NULL, kind TEXT NOT NULL, source_id INTEGER,
                    error TEXT, provider_ids TEXT NOT NULL DEFAULT '[]'
                );
                CREATE INDEX IF NOT EXISTS roamai_outbox_ready ON roamai_outbox(state, available);
                CREATE TABLE IF NOT EXISTS roamai_polls (
                    id TEXT PRIMARY KEY, group_id TEXT NOT NULL, topic_id TEXT NOT NULL,
                    question TEXT NOT NULL, options TEXT NOT NULL, closes REAL NOT NULL,
                    state TEXT NOT NULL DEFAULT 'open', request_id TEXT UNIQUE
                );
                CREATE TABLE IF NOT EXISTS roamai_votes (
                    poll_id TEXT NOT NULL, user_id TEXT NOT NULL, choice INTEGER NOT NULL,
                    PRIMARY KEY(poll_id, user_id)
                );
                CREATE TABLE IF NOT EXISTS roamai_members (
                    group_id TEXT NOT NULL, user_id TEXT NOT NULL, name TEXT NOT NULL,
                    PRIMARY KEY(group_id, user_id)
                );
                CREATE TABLE IF NOT EXISTS roamai_expenses (
                    id TEXT PRIMARY KEY, group_id TEXT NOT NULL, topic_id TEXT NOT NULL,
                    payer_id TEXT NOT NULL, amount TEXT NOT NULL, currency TEXT NOT NULL,
                    description TEXT NOT NULL, participants TEXT NOT NULL,
                    confirmed TEXT NOT NULL DEFAULT '[]', state TEXT NOT NULL DEFAULT 'pending'
                );
                CREATE TABLE IF NOT EXISTS roamai_reminders (
                    id TEXT PRIMARY KEY, group_id TEXT NOT NULL, topic_id TEXT NOT NULL,
                    text TEXT NOT NULL, due REAL NOT NULL, state TEXT NOT NULL DEFAULT 'pending'
                );
                CREATE TABLE IF NOT EXISTS roamai_topic_messages (
                    group_id TEXT NOT NULL, topic_id TEXT NOT NULL, inbox_id INTEGER NOT NULL,
                    PRIMARY KEY(group_id, topic_id, inbox_id)
                );
                CREATE TABLE IF NOT EXISTS roamai_topic_facts (
                    group_id TEXT NOT NULL, topic_id TEXT NOT NULL, key TEXT NOT NULL,
                    value TEXT NOT NULL, evidence_id TEXT NOT NULL, evidence_quote TEXT NOT NULL,
                    PRIMARY KEY(group_id, topic_id, key)
                );
                CREATE TABLE IF NOT EXISTS roamai_scoped_preferences (
                    group_id TEXT NOT NULL, topic_id TEXT NOT NULL, user_id TEXT NOT NULL,
                    key TEXT NOT NULL, value TEXT NOT NULL, evidence_id TEXT NOT NULL,
                    evidence_quote TEXT NOT NULL, updated REAL NOT NULL,
                    PRIMARY KEY(group_id, topic_id, user_id, key)
                );
            """)
            columns = {row[1] for row in connection.execute("PRAGMA table_info(roamai_inbox)")}
            if "notify_failure" not in columns:
                connection.execute("ALTER TABLE roamai_inbox ADD COLUMN notify_failure INTEGER NOT NULL DEFAULT 0")
            if "error" not in columns:
                connection.execute("ALTER TABLE roamai_inbox ADD COLUMN error TEXT")
            topic_columns = {row[1] for row in connection.execute("PRAGMA table_info(roamai_topics)")}
            if "initial_summary" not in topic_columns:
                connection.execute("ALTER TABLE roamai_topics ADD COLUMN initial_summary TEXT NOT NULL DEFAULT ''")
                connection.execute("UPDATE roamai_topics SET initial_summary = summary")
            connection.execute("CREATE VIRTUAL TABLE IF NOT EXISTS roamai_topic_search USING fts5(topic_id UNINDEXED, group_id UNINDEXED, content)")
            connection.execute("""
                INSERT INTO roamai_topic_search(topic_id, group_id, content)
                SELECT id, group_id, title || ' ' || summary || ' ' || initial_summary FROM roamai_topics topic
                WHERE NOT EXISTS (SELECT 1 FROM roamai_topic_search search WHERE search.topic_id = topic.id)
            """)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def enqueue(self, event: ChannelEvent, debounce: float = 10) -> bool:
        now = time.time()
        delay = 0 if event.explicitly_addressed else debounce
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT OR IGNORE INTO roamai_groups(id, platform, channel_id, connection_id) VALUES (?, ?, ?, ?)",
                (event.conversation_id, event.platform, event.channel_id, event.connection_id),
            )
            inserted = connection.execute(
                "INSERT OR IGNORE INTO roamai_inbox(group_id, event_id, payload, received, available) VALUES (?, ?, ?, ?, ?)",
                (event.conversation_id, event.event_id, event.model_dump_json(), now, now + delay),
            ).rowcount
            if inserted:
                connection.execute(
                    "INSERT INTO roamai_members VALUES (?, ?, ?) ON CONFLICT(group_id, user_id) DO UPDATE SET name = excluded.name",
                    (event.conversation_id, event.sender.id, event.sender.name),
                )
                connection.execute(
                    "UPDATE roamai_inbox SET available = MIN(received + 30, ?) WHERE group_id = ? AND state = 'pending'",
                    (now + delay, event.conversation_id),
                )
        return bool(inserted)

    def claim(self, now: float | None = None) -> list[dict]:
        now = now if now is not None else time.time()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("UPDATE roamai_inbox SET state = 'pending' WHERE state = 'processing' AND lease < ?", (now,))
            row = connection.execute("""
                SELECT group_id FROM roamai_inbox candidate
                WHERE state = 'pending' AND available <= ? AND NOT EXISTS (
                    SELECT 1 FROM roamai_inbox active
                    WHERE active.group_id = candidate.group_id AND active.state = 'processing'
                ) ORDER BY id LIMIT 1
            """, (now,)).fetchone()
            if not row:
                return []
            rows = connection.execute(
                "SELECT * FROM roamai_inbox WHERE group_id = ? AND state = 'pending' ORDER BY id LIMIT 50",
                (row["group_id"],),
            ).fetchall()
            for index, item in enumerate(rows):
                if ChannelEvent.model_validate_json(item["payload"]).explicitly_addressed:
                    rows = rows[:index] if index else rows[:1]
                    break
            for item in rows:
                connection.execute(
                    "UPDATE roamai_inbox SET state = 'processing', lease = ?, attempts = attempts + 1 WHERE id = ?",
                    (now + 180, item["id"]),
                )
            return [dict(item) for item in rows]

    def context(self, group_id: str, before_id: int = 9223372036854775807, selected_topic_id: str | None = None) -> dict:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT id, payload, state FROM roamai_inbox WHERE group_id = ? AND id <= ?
                    AND (state = 'processing' OR id IN (
                        SELECT id FROM roamai_inbox WHERE group_id = ? AND id <= ? ORDER BY id DESC LIMIT 40
                    )) ORDER BY id DESC""", (group_id, before_id, group_id, before_id),
            ).fetchall()
            selected = [selected_topic_id] if selected_topic_id else []
            if not selected_topic_id:
                text = " ".join(ChannelEvent.model_validate_json(row["payload"]).text or "" for row in reversed(rows) if row["state"] == "processing")
                if not text and rows:
                    text = ChannelEvent.model_validate_json(rows[0]["payload"]).text or ""
                terms = list(dict.fromkeys(re.findall(r"\w{3,}", text.casefold())))[:30]
                if terms:
                    query = " OR ".join('"' + term + '"' for term in terms)
                    selected.extend(row[0] for row in connection.execute(
                        "SELECT topic_id FROM roamai_topic_search WHERE roamai_topic_search MATCH ? AND group_id = ? ORDER BY rank LIMIT 8",
                        (query, group_id)))
                selected.extend(row[0] for row in connection.execute(
                    "SELECT topic_id FROM roamai_outbox WHERE group_id = ? AND state = 'sent' AND topic_id IS NOT NULL ORDER BY created DESC LIMIT 4", (group_id,)))
                selected.extend(row[0] for row in connection.execute(
                    "SELECT id FROM roamai_topics WHERE group_id = ? ORDER BY updated DESC LIMIT 20", (group_id,)))
            selected = list(dict.fromkeys(selected))[:20]
            placeholders = ",".join("?" for identity in selected) or "NULL"
            topics = connection.execute(
                f"SELECT * FROM roamai_topics WHERE group_id = ? AND id IN ({placeholders}) ORDER BY updated DESC", (group_id, *selected),
            ).fetchall()
            preferences = connection.execute(
                f"SELECT topic_id, user_id, key, value, evidence_id FROM roamai_scoped_preferences WHERE group_id = ? AND (topic_id = '' OR topic_id IN ({placeholders}))", (group_id, *selected),
            ).fetchall()
            facts = connection.execute(f"SELECT * FROM roamai_topic_facts WHERE group_id = ? AND topic_id IN ({placeholders})", (group_id, *selected)).fetchall()
            topic_count = connection.execute("SELECT COUNT(*) FROM roamai_topics WHERE group_id = ?", (group_id,)).fetchone()[0]
            last_offer = connection.execute("SELECT last_offer FROM roamai_groups WHERE id = ?", (group_id,)).fetchone()
            outbound = connection.execute(
                "SELECT id, topic_id, payload, provider_ids, created FROM roamai_outbox WHERE group_id = ? AND state = 'sent' ORDER BY created DESC, rowid DESC LIMIT 10",
                (group_id,),
            ).fetchall()
            members = connection.execute("SELECT user_id, name FROM roamai_members WHERE group_id = ?", (group_id,)).fetchall()
        messages = []
        for row in reversed(rows):
            event = ChannelEvent.model_validate_json(row["payload"])
            messages.append({
                "id": str(row["id"]), "sender_id": event.sender.id, "sender_name": event.sender.name,
                "text": event.text or "", "message_id": event.message_id,
                "reply_to_message_id": event.reply_to_message_id,
                "explicitly_addressed": event.explicitly_addressed,
            })
        return {
            "messages": messages,
            "topic_count": topic_count,
            "topics": [dict(row) | {"participants": json.loads(row["participants"]),
                "facts": {fact["key"]: dict(fact) for fact in facts if fact["topic_id"] == row["id"]}} for row in topics],
            "preferences": [dict(row) for row in preferences],
            "last_offer": last_offer["last_offer"] if last_offer else 0,
            "members": [dict(row) for row in members],
            "outbound": [dict(row) | {"payload": json.loads(row["payload"]), "provider_ids": json.loads(row["provider_ids"])} for row in outbound],
        }

    def save_topic(self, group_id: str, source_id: int, observation, participant_ids: list[str]) -> str:
        topic_id = observation.topic_id or uuid.uuid5(uuid.NAMESPACE_URL, f"{group_id}:{source_id}").hex
        with self.connect() as connection:
            existing = connection.execute("SELECT group_id, participants, title FROM roamai_topics WHERE id = ?", (topic_id,)).fetchone()
            if existing and existing["group_id"] != group_id:
                raise ValueError("Topic does not belong to this conversation")
            if existing:
                participant_ids = sorted(set(participant_ids) | set(json.loads(existing["participants"])))
            title = existing["title"] if existing and observation.title == "Conversation" else observation.title
            connection.execute("""
                INSERT INTO roamai_topics(id, group_id, title, summary, intent, participants, updated, initial_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET title=excluded.title, summary=excluded.summary,
                    intent=excluded.intent, participants=excluded.participants, updated=excluded.updated
            """, (topic_id, group_id, title, observation.summary, observation.intent, json.dumps(participant_ids), time.time(), observation.summary))
            evidence_ids = {str(source_id), *observation.evidence_message_ids,
                            *(fact.evidence_message_id for fact in observation.facts)}
            for evidence_id in evidence_ids:
                connection.execute("""
                    INSERT OR IGNORE INTO roamai_topic_messages
                    SELECT group_id, ?, id FROM roamai_inbox WHERE group_id = ? AND id = ?
                    AND NOT EXISTS (SELECT 1 FROM roamai_topic_messages WHERE inbox_id = roamai_inbox.id AND topic_id != ?)
                """, (topic_id, group_id, evidence_id, topic_id))
            for fact in observation.facts:
                source = connection.execute("""
                    SELECT payload FROM roamai_inbox WHERE group_id = ? AND id = ? AND id <= ?
                    AND EXISTS (SELECT 1 FROM roamai_topic_messages WHERE inbox_id = roamai_inbox.id AND topic_id = ?)
                """, (group_id, fact.evidence_message_id, source_id, topic_id)).fetchone()
                if not source:
                    continue
                text = ChannelEvent.model_validate_json(source["payload"]).text or ""
                if fact.evidence_quote not in text or fact.value not in fact.evidence_quote:
                    continue
                connection.execute("""
                    INSERT INTO roamai_topic_facts VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(group_id, topic_id, key) DO UPDATE SET value=excluded.value,
                        evidence_id=excluded.evidence_id, evidence_quote=excluded.evidence_quote
                    WHERE CAST(excluded.evidence_id AS INTEGER) >= CAST(roamai_topic_facts.evidence_id AS INTEGER)
                """, (group_id, topic_id, fact.key, fact.value, fact.evidence_message_id, fact.evidence_quote))
            topic = connection.execute("SELECT title, summary, initial_summary FROM roamai_topics WHERE id = ? AND group_id = ?", (topic_id, group_id)).fetchone()
            facts = connection.execute("SELECT key, value FROM roamai_topic_facts WHERE topic_id = ? AND group_id = ?", (topic_id, group_id)).fetchall()
            content = json.dumps({"topic": dict(topic), "facts": [dict(fact) for fact in facts]}, ensure_ascii=False)
            connection.execute("DELETE FROM roamai_topic_search WHERE topic_id = ? AND group_id = ?", (topic_id, group_id))
            connection.execute("INSERT INTO roamai_topic_search VALUES (?, ?, ?)", (topic_id, group_id, content))
        return topic_id

    def topic_context(self, group_id: str, topic_id: str, before_id: int = 9223372036854775807) -> dict:
        context = self.context(group_id, before_id, selected_topic_id=topic_id)
        context["topics"] = [topic for topic in context["topics"] if topic["id"] == topic_id]
        if not context["topics"]:
            raise ValueError("Topic does not belong to this conversation")
        context["preferences"] = [item for item in context["preferences"] if item["topic_id"] in {"", topic_id}]
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT inbox.id, inbox.payload FROM roamai_inbox inbox
                JOIN roamai_topic_messages memory ON memory.inbox_id = inbox.id
                WHERE inbox.group_id = ? AND memory.topic_id = ? AND inbox.id <= ?
                ORDER BY inbox.id DESC LIMIT 80
            """, (group_id, topic_id, before_id)).fetchall()
            evidence_rows = connection.execute("""
                SELECT DISTINCT inbox.id, inbox.payload FROM roamai_inbox inbox
                JOIN roamai_topic_facts fact ON CAST(fact.evidence_id AS INTEGER) = inbox.id AND fact.group_id = inbox.group_id
                WHERE inbox.group_id = ? AND fact.topic_id = ? AND inbox.id <= ?
            """, (group_id, topic_id, before_id)).fetchall()
            rows = sorted({row["id"]: row for row in [*rows, *evidence_rows]}.values(), key=lambda row: row["id"], reverse=True)
            outbound = connection.execute("""
                SELECT id, topic_id, payload, provider_ids, created FROM roamai_outbox
                WHERE group_id = ? AND topic_id = ? AND state = 'sent'
                ORDER BY created DESC, rowid DESC LIMIT 10
            """, (group_id, topic_id)).fetchall()
        context["messages"] = []
        for row in reversed(rows):
            incoming = ChannelEvent.model_validate_json(row["payload"])
            context["messages"].append({"id": str(row["id"]), "sender_id": incoming.sender.id,
                "sender_name": incoming.sender.name, "text": incoming.text or "", "message_id": incoming.message_id})
        context["outbound"] = [dict(row) | {"payload": json.loads(row["payload"]), "provider_ids": json.loads(row["provider_ids"])} for row in outbound]
        return context

    def set_topic_state(self, group_id: str, topic_id: str, state: str):
        if state not in {"observed", "offered", "active", "declined", "closed"}:
            raise ValueError("Invalid topic state")
        with self.connect() as connection:
            connection.execute("UPDATE roamai_topics SET state = ?, updated = ? WHERE group_id = ? AND id = ?", (state, time.time(), group_id, topic_id))

    def save_preference(self, group_id: str, user_id: str, key: str, value: str, evidence_id: str,
                        topic_id: str | None = None, scope: str = "topic", evidence_quote: str = ""):
        if key not in {"sport", "dietary_preference", "transportation_preference", "accessibility", "accommodation_preference"}:
            return False
        with self.connect() as connection:
            source = connection.execute("SELECT payload FROM roamai_inbox WHERE group_id = ? AND id = ?", (group_id, evidence_id)).fetchone()
            if not source or not topic_id:
                return False
            incoming = ChannelEvent.model_validate_json(source["payload"])
            if incoming.sender.id != user_id or not evidence_quote or evidence_quote not in (incoming.text or "") or value not in evidence_quote:
                return False
            if not connection.execute("SELECT 1 FROM roamai_topics WHERE group_id = ? AND id = ?", (group_id, topic_id)).fetchone():
                return False
            if scope == "global":
                if not re.search(r"\bremember\b.*\b(?:future trips|all trips|always)\b", evidence_quote, re.I):
                    return False
                topic_id = ""
            elif scope != "topic":
                return False
            connection.execute("""
                INSERT INTO roamai_scoped_preferences VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(group_id, topic_id, user_id, key) DO UPDATE SET value=excluded.value,
                    evidence_id=excluded.evidence_id, evidence_quote=excluded.evidence_quote, updated=excluded.updated
            """, (group_id, topic_id, user_id, key, value, evidence_id, evidence_quote, time.time()))
        return True

    def complete(self, rows: list[dict], topic_id: str | None = None, response: dict | None = None, kind: str = "response"):
        group_id = rows[-1]["group_id"]
        now = time.time()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            newer = connection.execute("SELECT 1 FROM roamai_inbox WHERE group_id = ? AND id > ? LIMIT 1", (group_id, rows[-1]["id"])).fetchone()
            if response and not (kind == "offer" and newer):
                if kind == "response" and "awaiting_reply" not in response:
                    response = response | {"awaiting_reply": bool(response.get("addressed_to") and "?" in response.get("text", "") and not response.get("buttons"))}
                self._insert_outbox(connection, str(rows[-1]["id"]), group_id, topic_id, response, kind, rows[-1]["id"], now)
            for row in rows:
                connection.execute("UPDATE roamai_inbox SET state = 'done' WHERE id = ?", (row["id"],))

    def pending_reply(self, group_id, user_id, before_id):
        with self.connect() as connection:
            row = connection.execute("""
                SELECT outbox.* FROM roamai_outbox outbox
                LEFT JOIN roamai_topics topic ON topic.id = outbox.topic_id AND topic.group_id = outbox.group_id
                WHERE outbox.group_id = ? AND outbox.state = 'sent' AND (outbox.topic_id IS NULL OR topic.state = 'active')
                    AND outbox.created > ? AND outbox.source_id < ?
                    AND json_extract(outbox.payload, '$.addressed_to') = ?
                ORDER BY outbox.created DESC, outbox.rowid DESC LIMIT 1
            """, (group_id, time.time() - 3600, before_id, user_id)).fetchone()
            if not row or not json.loads(row["payload"]).get("awaiting_reply"):
                return None
            answered = connection.execute("""
                SELECT 1 FROM roamai_inbox WHERE group_id = ? AND id > ? AND id < ?
                    AND state = 'done' AND json_extract(payload, '$.sender.id') = ? LIMIT 1
            """, (group_id, row["source_id"], before_id, user_id)).fetchone()
            return None if answered else dict(row) | {"payload": json.loads(row["payload"])}

    def _insert_outbox(self, connection, outbox_id, group_id, topic_id, response, kind, source_id, now):
        text = response.get("text", "")
        chunks = [text[index:index + 3000] for index in range(0, max(1, len(text)), 3000)]
        for index, chunk in enumerate(chunks):
            payload = response | {"text": chunk, "buttons": response.get("buttons", []) if index == len(chunks) - 1 else []}
            connection.execute("""
                INSERT OR IGNORE INTO roamai_outbox(id, group_id, topic_id, payload, available, created, kind, source_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (f"{outbox_id}:{index}", group_id, topic_id, json.dumps(payload), now, now, kind, source_id))

    def retry(self, rows: list[dict], error: str):
        attempts = max(row["attempts"] + 1 for row in rows)
        if attempts >= 3:
            event = ChannelEvent.model_validate_json(rows[-1]["payload"])
            response = None
            if event.explicitly_addressed or rows[-1].get("notify_failure"):
                response = {"text": "I couldn't complete that request. Please try again.", "buttons": [], "reply_to_message_id": event.message_id}
            self.complete(rows, response=response, kind="error")
            with self.connect() as connection:
                for row in rows:
                    connection.execute("UPDATE roamai_inbox SET state = 'failed', error = ? WHERE id = ?", (error[:500], row["id"]))
            return
        with self.connect() as connection:
            for row in rows:
                connection.execute("UPDATE roamai_inbox SET state = 'pending', available = ?, error = ? WHERE id = ?", (time.time() + 2 ** attempts + random.uniform(0, 1), error[:500], row["id"]))

    def mark_responding(self, rows):
        with self.connect() as connection:
            for row in rows:
                connection.execute("UPDATE roamai_inbox SET notify_failure = 1 WHERE id = ?", (row["id"],))
                row["notify_failure"] = 1

    def next_delivery(self) -> dict | None:
        now = time.time()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("UPDATE roamai_outbox SET state = 'pending' WHERE state = 'sending' AND available < ?", (now,))
            connection.execute("""
                UPDATE roamai_outbox SET state = 'cancelled' WHERE state = 'pending' AND kind = 'offer'
                AND (created < ? OR EXISTS (SELECT 1 FROM roamai_inbox WHERE group_id = roamai_outbox.group_id AND id > source_id))
            """, (now - 300,))
            row = connection.execute("""
                SELECT candidate.*, groups.platform, groups.channel_id FROM roamai_outbox candidate
                JOIN roamai_groups groups ON groups.id = candidate.group_id
                WHERE candidate.state = 'pending' AND candidate.available <= ? AND NOT EXISTS (
                    SELECT 1 FROM roamai_outbox earlier WHERE earlier.group_id = candidate.group_id
                    AND earlier.state IN ('pending', 'sending') AND earlier.rowid < candidate.rowid
                ) ORDER BY candidate.rowid LIMIT 1
            """, (now,)).fetchone()
            if not row:
                return None
            connection.execute("UPDATE roamai_outbox SET state = 'sending', available = ? WHERE id = ?", (now + 60, row["id"]))
            return dict(row) | {"payload": json.loads(row["payload"])}

    def delivery_result(self, delivery: dict, success: bool, provider_ids=(), error="", retry_after: float | None = None, permanent=False):
        now = time.time()
        attempts = delivery["attempts"] + 1
        state = "sent" if success else "failed" if permanent or attempts >= 6 else "pending"
        delay = retry_after if retry_after is not None else min(300, 2 ** attempts + random.uniform(0, 1))
        with self.connect() as connection:
            connection.execute("UPDATE roamai_outbox SET state = ?, attempts = ?, available = ?, error = ?, provider_ids = ? WHERE id = ?", (state, attempts, now + delay, error[:500], json.dumps(list(provider_ids)), delivery["id"]))
            if success and delivery["kind"] == "offer":
                connection.execute("UPDATE roamai_groups SET last_offer = ? WHERE id = ?", (now, delivery["group_id"]))
                connection.execute("UPDATE roamai_topics SET state = 'offered', last_offer = ?, offered_to = ? WHERE id = ? AND group_id = ?", (now, delivery["payload"].get("offered_to"), delivery["topic_id"], delivery["group_id"]))

    def create_poll(self, group_id, topic_id, question, options, minutes, request_id):
        if not 2 <= len(options) <= 3 or len(set(options)) != len(options) or any(not option.strip() or len(option) > 20 for option in options):
            raise ValueError("Provide two or three distinct options of at most 20 characters")
        if not 1 <= minutes <= 10080:
            raise ValueError("Poll duration must be between one minute and seven days")
        poll_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{group_id}:{request_id}").hex[:20]
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT id FROM roamai_polls WHERE group_id = ? AND topic_id = ? AND state = 'open' AND closes > ? AND id != ?",
                (group_id, topic_id, time.time(), poll_id),
            ).fetchone()
            if existing:
                raise ValueError("An active poll already exists for this topic; creating another cannot update it")
            connection.execute("INSERT OR IGNORE INTO roamai_polls VALUES (?, ?, ?, ?, ?, ?, 'open', ?)", (poll_id, group_id, topic_id, question, json.dumps(options), time.time() + minutes * 60, f"{group_id}:{request_id}"))
        return poll_id

    def open_polls(self, group_id, topic_id):
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM roamai_polls WHERE group_id = ? AND topic_id = ? AND state = 'open' AND closes > ?", (group_id, topic_id, time.time())).fetchall()
        return [dict(row) | {"options": json.loads(row["options"])} for row in rows]

    def vote(self, group_id, poll_id, user_id, choice):
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            poll = connection.execute("SELECT * FROM roamai_polls WHERE id = ? AND group_id = ? AND state = 'open' AND closes > ?", (poll_id, group_id, time.time())).fetchone()
            if not poll or not 0 <= choice < len(json.loads(poll["options"])):
                return False
            connection.execute("INSERT INTO roamai_votes VALUES (?, ?, ?) ON CONFLICT(poll_id, user_id) DO UPDATE SET choice = excluded.choice", (poll_id, user_id, choice))
            return True

    def close_due_polls(self):
        now = time.time()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for poll in connection.execute("SELECT * FROM roamai_polls WHERE state = 'open' AND closes <= ?", (now,)).fetchall():
                options = json.loads(poll["options"])
                counts = {row["choice"]: row["total"] for row in connection.execute("SELECT choice, COUNT(*) AS total FROM roamai_votes WHERE poll_id = ? GROUP BY choice", (poll["id"],))}
                lines = ["Poll closed: " + poll["question"]] + [f"{option}: {counts.get(index, 0)} vote(s)" for index, option in enumerate(options)]
                if not counts:
                    lines.append("No votes were recorded; no decision has been made.")
                else:
                    lines.append("These are preferences, not a booking or attendance confirmation.")
                self._insert_outbox(connection, "poll:" + poll["id"], poll["group_id"], poll["topic_id"], {"text": "\n".join(lines), "buttons": []}, "poll_result", None, now)
                connection.execute("UPDATE roamai_polls SET state = 'closed' WHERE id = ?", (poll["id"],))

    def accept_offer(self, group_id, topic_id, user_id, accepted=True):
        with self.connect() as connection:
            return bool(connection.execute(
                "UPDATE roamai_topics SET state = ?, updated = ? WHERE id = ? AND group_id = ? AND state IN ('offered', ?) AND offered_to = ? AND last_offer > ?",
                ("active" if accepted else "declined", time.time(), topic_id, group_id, "active" if accepted else "declined", user_id, time.time() - 3600),
            ).rowcount)

    def propose_expense(self, group_id, topic_id, payer_id, amount, currency, description, participant_ids, request_id):
        try:
            number = Decimal(amount)
        except InvalidOperation:
            raise ValueError("Amount must be a number") from None
        if not number.is_finite() or number <= 0 or number.as_tuple().exponent < -3:
            raise ValueError("Provide a positive amount with at most three decimal places")
        if len(currency) != 3 or not currency.isascii() or not currency.isalpha() or currency != currency.upper():
            raise ValueError("Confirm a three-letter currency code; '$' alone is ambiguous")
        precision = 0 if currency in {"JPY", "KRW", "VND"} else 3 if currency in {"BHD", "KWD", "OMR", "JOD", "TND"} else 2
        if number % (Decimal(10) ** -precision):
            raise ValueError("Amount has invalid precision for this currency")
        participants = sorted(set(participant_ids))
        if not participants:
            raise ValueError("Select actual participants, not just a head count")
        expense_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{group_id}:{request_id}:expense").hex[:20]
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            members = {row[0] for row in connection.execute("SELECT user_id FROM roamai_members WHERE group_id = ?", (group_id,))}
            if not set(participants + [payer_id]) <= members:
                raise ValueError("Every participant must have a known identity in this group")
            existing = connection.execute("SELECT * FROM roamai_expenses WHERE group_id = ? AND topic_id = ?", (group_id, topic_id)).fetchone()
            if existing and (existing["id"] != expense_id or existing["state"] != "pending"):
                raise ValueError("This topic already has an expense. Do not recreate or reopen it; a distinct payment needs a new topic and new consent.")
            if existing and (Decimal(existing["amount"]) != number or existing["currency"] != currency
                    or existing["payer_id"] != payer_id or json.loads(existing["participants"]) != participants):
                raise ValueError("A retry cannot change an expense's amount, currency, payer or participants")
            connection.execute(
                "INSERT OR IGNORE INTO roamai_expenses(id, group_id, topic_id, payer_id, amount, currency, description, participants) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (expense_id, group_id, topic_id, payer_id, str(number), currency, description, json.dumps(participants)),
            )
            row = connection.execute("SELECT * FROM roamai_expenses WHERE id = ?", (expense_id,)).fetchone()
        return dict(row)

    def confirm_expense(self, group_id, expense_id, user_id, accepted=True):
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM roamai_expenses WHERE id = ? AND group_id = ?", (expense_id, group_id)).fetchone()
            if not row or row["state"] != "pending":
                return None
            required = set(json.loads(row["participants"])) | {row["payer_id"]}
            if user_id not in required:
                return None
            confirmed = set(json.loads(row["confirmed"]))
            if accepted:
                confirmed.add(user_id)
            else:
                confirmed.discard(user_id)
            state = "rejected" if not accepted else "confirmed" if required <= confirmed else "pending"
            connection.execute("UPDATE roamai_expenses SET confirmed = ?, state = ? WHERE id = ?", (json.dumps(sorted(confirmed)), state, expense_id))
            return state

    def tasks(self, group_id, topic_id):
        with self.connect() as connection:
            expenses = connection.execute("SELECT * FROM roamai_expenses WHERE group_id = ? AND topic_id = ?", (group_id, topic_id)).fetchall()
            reminders = connection.execute("SELECT * FROM roamai_reminders WHERE group_id = ? AND topic_id = ?", (group_id, topic_id)).fetchall()
        return {"polls": self.open_polls(group_id, topic_id), "expenses": [dict(row) for row in expenses], "reminders": [dict(row) for row in reminders]}

    def balances(self, group_id):
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM roamai_expenses WHERE group_id = ? AND state = 'confirmed'", (group_id,)).fetchall()
        currencies = {}
        for row in rows:
            amounts = currencies.setdefault(row["currency"], {})
            number = Decimal(row["amount"])
            precision = 0 if row["currency"] in {"JPY", "KRW", "VND"} else 3 if row["currency"] in {"BHD", "KWD", "OMR", "JOD", "TND"} else 2
            unit = Decimal(10) ** -precision
            if number % unit:
                raise ValueError("Expense amount has invalid precision for its currency")
            participants = json.loads(row["participants"])
            units = int(number / unit)
            share, remainder = divmod(units, len(participants))
            amounts[row["payer_id"]] = amounts.get(row["payer_id"], Decimal(0)) + number
            for index, participant in enumerate(participants):
                debit = (share + (1 if index < remainder else 0)) * unit
                amounts[participant] = amounts.get(participant, Decimal(0)) - debit
        return {currency: {member: str(amount) for member, amount in amounts.items()} for currency, amounts in currencies.items()}

    def schedule_reminder(self, group_id, topic_id, text, due, request_id):
        if not time.time() < due <= time.time() + 366 * 86400:
            raise ValueError("Reminder must be in the next year and include a timezone")
        reminder_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{group_id}:{request_id}:reminder").hex[:20]
        with self.connect() as connection:
            connection.execute("INSERT OR IGNORE INTO roamai_reminders VALUES (?, ?, ?, ?, ?, 'pending')", (reminder_id, group_id, topic_id, text, due))
        return reminder_id

    def cancel_reminder(self, group_id, topic_id, reminder_id):
        with self.connect() as connection:
            return bool(connection.execute("UPDATE roamai_reminders SET state = 'cancelled' WHERE id = ? AND group_id = ? AND topic_id = ? AND state = 'pending'", (reminder_id, group_id, topic_id)).rowcount)

    def release_due_reminders(self):
        now = time.time()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for row in connection.execute("SELECT * FROM roamai_reminders WHERE state = 'pending' AND due <= ?", (now,)).fetchall():
                topic = connection.execute("SELECT state FROM roamai_topics WHERE id = ? AND group_id = ?", (row["topic_id"], row["group_id"])).fetchone()
                valid = topic and topic["state"] == "active" and now - row["due"] < 3600
                if valid:
                    self._insert_outbox(connection, "reminder:" + row["id"], row["group_id"], row["topic_id"], {"text": row["text"]}, "reminder", None, now)
                connection.execute("UPDATE roamai_reminders SET state = ? WHERE id = ?", ("queued" if valid else "cancelled", row["id"]))

    def web_messages(self, group_id, after=0):
        with self.connect() as connection:
            rows = connection.execute("SELECT rowid AS sequence, payload FROM roamai_outbox WHERE group_id = ? AND state = 'sent' AND rowid > ? ORDER BY rowid LIMIT 100", (group_id, after)).fetchall()
        return [json.loads(row["payload"]) | {"sequence": row["sequence"]} for row in rows]

    def queue_status(self):
        now = time.time()
        with self.connect() as connection:
            inbox = {row["state"]: row["count"] for row in connection.execute("SELECT state, COUNT(*) AS count FROM roamai_inbox GROUP BY state")}
            outbox = {row["state"]: row["count"] for row in connection.execute("SELECT state, COUNT(*) AS count FROM roamai_outbox GROUP BY state")}
            overdue = connection.execute("""
                SELECT COUNT(*) FROM roamai_inbox WHERE (state = 'pending' AND available < ?)
                    OR (state = 'processing' AND lease < ?)
            """, (now - 180, now)).fetchone()[0]
            overdue += connection.execute("""
                SELECT COUNT(*) FROM roamai_outbox WHERE (state = 'pending' AND available < ?)
                    OR (state = 'sending' AND available < ?)
            """, (now - 180, now)).fetchone()[0]
        return {"inbox": inbox, "outbox": outbox, "overdue": overdue}