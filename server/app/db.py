import sqlite3
from collections.abc import Iterator
from pathlib import Path

from fastapi import Request

_SCHEMA = Path(__file__).with_name("schema.sql")


def verbinden(pfad: str) -> sqlite3.Connection:
    """Öffnet die DB. isolation_level=None: Transaktionen werden explizit mit BEGIN geführt."""
    conn = sqlite3.connect(pfad, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


# Spalten, die nach der ersten Version dazukamen: (Tabelle, Spalte, Typ)
_NEUE_SPALTEN = [("blatt_aufgaben", "vorgabe", "TEXT")]


def initialisieren(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA.read_text(encoding="utf-8"))
    for tabelle, spalte, typ in _NEUE_SPALTEN:
        vorhanden = {z["name"] for z in conn.execute(f"PRAGMA table_info({tabelle})")}
        if spalte not in vorhanden:
            conn.execute(f"ALTER TABLE {tabelle} ADD COLUMN {spalte} {typ}")


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    """FastAPI-Dependency: eine Verbindung je Anfrage."""
    conn = verbinden(request.app.state.settings.db_pfad)
    try:
        yield conn
    finally:
        conn.close()
