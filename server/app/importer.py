"""Import aus der Extraktion: Upsert von Fächern, Themen und Einträgen, alles oder nichts."""

import sqlite3
from typing import Literal

from pydantic import BaseModel


class FachIn(BaseModel):
    slug: str
    name: str
    about_pfad: str | None = None
    about_hash: str | None = None


class ThemaIn(BaseModel):
    schluessel: str
    fach: str
    parent: str | None = None
    titel: str
    reihenfolge: int = 0


class EintragIn(BaseModel):
    schluessel: str
    thema: str
    art: Literal["aufgabe", "klausurfrage", "lernpunkt"]
    titel: str
    kurztext: str = ""
    quellpfad: str
    anker: str = ""
    quell_hash: str
    punkte: float | None = None


class ImportIn(BaseModel):
    quell_commit: str | None = None
    faecher: list[FachIn] = []
    themen: list[ThemaIn] = []
    eintraege: list[EintragIn] = []


class ImportFehler(Exception):
    pass


def _id(conn: sqlite3.Connection, tabelle: str, spalte: str, wert: str, wofuer: str) -> int:
    zeile = conn.execute(f"SELECT id FROM {tabelle} WHERE {spalte} = ?", (wert,)).fetchone()
    if zeile is None:
        raise ImportFehler(f"{wofuer}: unbekannter Verweis '{wert}'")
    return zeile["id"]


def schreiben(conn: sqlite3.Connection, daten: ImportIn) -> dict:
    """Upsert ohne eigene Transaktion; der Aufrufer führt BEGIN/COMMIT."""
    for f in daten.faecher:
        conn.execute(
            "INSERT INTO faecher(slug, name, about_pfad, about_hash) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(slug) DO UPDATE SET name=excluded.name,"
            " about_pfad=excluded.about_pfad, about_hash=excluded.about_hash",
            (f.slug, f.name, f.about_pfad, f.about_hash),
        )
    for t in daten.themen:
        fach_id = _id(conn, "faecher", "slug", t.fach, f"Thema {t.schluessel}")
        parent_id = None
        if t.parent is not None:
            parent_id = _id(conn, "themen", "schluessel", t.parent, f"Thema {t.schluessel}")
        conn.execute(
            "INSERT INTO themen(fach_id, parent_id, schluessel, titel, reihenfolge) VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(schluessel) DO UPDATE SET fach_id=excluded.fach_id,"
            " parent_id=excluded.parent_id, titel=excluded.titel, reihenfolge=excluded.reihenfolge",
            (fach_id, parent_id, t.schluessel, t.titel, t.reihenfolge),
        )
    for e in daten.eintraege:
        thema_id = _id(conn, "themen", "schluessel", e.thema, f"Eintrag {e.schluessel}")
        conn.execute(
            "INSERT INTO eintraege(schluessel, thema_id, art, titel, kurztext, quellpfad, anker, quell_hash, punkte)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(schluessel) DO UPDATE SET thema_id=excluded.thema_id, art=excluded.art,"
            " titel=excluded.titel, kurztext=excluded.kurztext, quellpfad=excluded.quellpfad,"
            " anker=excluded.anker, quell_hash=excluded.quell_hash, punkte=excluded.punkte",
            (e.schluessel, thema_id, e.art, e.titel, e.kurztext, e.quellpfad, e.anker, e.quell_hash, e.punkte),
        )
    return {"faecher": len(daten.faecher), "themen": len(daten.themen), "eintraege": len(daten.eintraege)}


def importieren(conn: sqlite3.Connection, daten: ImportIn) -> dict:
    conn.execute("BEGIN")
    try:
        zaehler = schreiben(conn, daten)
        if daten.quell_commit:
            conn.execute(
                "INSERT INTO meta(schluessel, wert) VALUES ('quell_commit', ?)"
                " ON CONFLICT(schluessel) DO UPDATE SET wert=excluded.wert",
                (daten.quell_commit,),
            )
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return zaehler
