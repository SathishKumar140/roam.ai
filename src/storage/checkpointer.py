import sqlite3
from typing import Optional
from src.config import settings


def get_sqlite_checkpointer(db_path: Optional[str] = None):
    """
    Returns a persistent SqliteSaver instance for LangGraph thread memory.
    Falls back to in-memory MemorySaver if SqliteSaver cannot be imported.
    """
    path = db_path or settings.CHECKPOINT_DB_PATH
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver

        conn = sqlite3.connect(path, check_same_thread=False)
        return SqliteSaver(conn)
    except (ImportError, Exception):
        try:
            from langgraph.checkpoint.memory import MemorySaver

            return MemorySaver()
        except ImportError:
            return None
