import sqlite3
from pathlib import Path

_SCHEMA = Path(__file__).with_name("schema.sql")


def verbinden(pfad: str) -> sqlite3.Connection:
    """Öffnet die DB. isolation_level=None: Transaktionen werden explizit mit BEGIN geführt."""
    conn = sqlite3.connect(pfad, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def initialisieren(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA.read_text(encoding="utf-8"))
