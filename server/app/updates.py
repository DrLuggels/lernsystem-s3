"""Quell-Updates: Lauf anlegen, Änderungen atomar anwenden, Protokoll führen."""

import sqlite3

from pydantic import BaseModel

from . import importer, level
from .blaetter import BlattFehler as UpdateFehler  # gleicher Aufbau: Status + Text

LAUF_GILT_MINUTEN = 45


class UpdateStart(BaseModel):
    commit_von: str | None = None
    commit_bis: str


class UpdateAnwenden(BaseModel):
    zusammenfassung: str
    protokoll: str = ""
    # Neue Einträge und kleine Änderungen (Level bleibt):
    daten: importer.ImportIn = importer.ImportIn()
    # Inhaltlich stark geändert: Status 'geaendert', eine Stufe zurück:
    stark_geaendert: list[str] = []
    # Aus der Quelle verschwunden: Status 'archiviert', Verlauf bleibt:
    archiviert: list[str] = []


class UpdateFehlschlag(BaseModel):
    protokoll: str = ""


def stand(conn: sqlite3.Connection) -> dict:
    zeile = conn.execute("SELECT wert FROM meta WHERE schluessel = 'quell_commit'").fetchone()
    letztes = conn.execute("SELECT * FROM updates ORDER BY id DESC LIMIT 1").fetchone()
    return {"quell_commit": zeile["wert"] if zeile else None, "letztes_update": dict(letztes) if letztes else None}


def liste(conn: sqlite3.Connection) -> list[dict]:
    return [dict(z) for z in conn.execute("SELECT * FROM updates ORDER BY id DESC LIMIT 50")]


def starten(conn: sqlite3.Connection, daten: UpdateStart) -> dict:
    laeuft = conn.execute(
        "SELECT id FROM updates WHERE status = 'laeuft' AND commit_bis = ?"
        " AND am > datetime('now', ?)", (daten.commit_bis, f"-{LAUF_GILT_MINUTEN} minutes")).fetchone()
    if laeuft:
        raise UpdateFehler(409, f"Update {laeuft['id']} für diesen Commit läuft bereits")
    # Liegengebliebene Läufe als Fehler abschließen.
    conn.execute("UPDATE updates SET status = 'fehler', protokoll = COALESCE(protokoll, '') || 'Abgebrochen.'"
                 " WHERE status = 'laeuft'")
    update_id = conn.execute("INSERT INTO updates(commit_von, commit_bis) VALUES (?, ?)",
                             (daten.commit_von, daten.commit_bis)).lastrowid
    return {"id": update_id}


def _lauf(conn: sqlite3.Connection, update_id: int) -> sqlite3.Row:
    zeile = conn.execute("SELECT * FROM updates WHERE id = ?", (update_id,)).fetchone()
    if zeile is None:
        raise UpdateFehler(404, "Update nicht gefunden")
    if zeile["status"] != "laeuft":
        raise UpdateFehler(409, f"Update ist bereits abgeschlossen ({zeile['status']})")
    return zeile


def anwenden(conn: sqlite3.Connection, update_id: int, daten: UpdateAnwenden) -> dict:
    doppelt = set(daten.stark_geaendert) & set(daten.archiviert)
    if doppelt:
        raise UpdateFehler(422, "Eintrag zugleich geändert und archiviert: " + ", ".join(sorted(doppelt)))
    conn.execute("BEGIN")
    try:
        lauf = _lauf(conn, update_id)
        zaehler = importer.schreiben(conn, daten.daten)
        # Was im Import wieder auftaucht, ist nicht mehr archiviert.
        for e in daten.daten.eintraege:
            conn.execute("UPDATE eintraege SET status = 'aktuell' WHERE schluessel = ? AND status = 'archiviert'",
                         (e.schluessel,))
        for schluessel in daten.stark_geaendert:
            zeile = conn.execute("SELECT id, level FROM eintraege WHERE schluessel = ?", (schluessel,)).fetchone()
            if zeile is None:
                raise UpdateFehler(422, f"Unbekannter Eintrag '{schluessel}'")
            conn.execute("UPDATE eintraege SET status = 'geaendert', level = ? WHERE id = ?",
                         (level.nach_starker_aenderung(zeile["level"]), zeile["id"]))
        for schluessel in daten.archiviert:
            if not conn.execute("UPDATE eintraege SET status = 'archiviert' WHERE schluessel = ?",
                                (schluessel,)).rowcount:
                raise UpdateFehler(422, f"Unbekannter Eintrag '{schluessel}'")
        conn.execute(
            "INSERT INTO meta(schluessel, wert) VALUES ('quell_commit', ?)"
            " ON CONFLICT(schluessel) DO UPDATE SET wert = excluded.wert", (lauf["commit_bis"],))
        conn.execute("UPDATE updates SET status = 'fertig', zusammenfassung = ?, protokoll = ? WHERE id = ?",
                     (daten.zusammenfassung, daten.protokoll, update_id))
        conn.execute("COMMIT")
    except importer.ImportFehler as fehler:
        conn.execute("ROLLBACK")
        raise UpdateFehler(422, str(fehler)) from fehler
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return {"status": "fertig", **zaehler,
            "stark_geaendert": len(daten.stark_geaendert), "archiviert": len(daten.archiviert)}


def fehlgeschlagen(conn: sqlite3.Connection, update_id: int, daten: UpdateFehlschlag) -> dict:
    _lauf(conn, update_id)
    conn.execute("UPDATE updates SET status = 'fehler', protokoll = ? WHERE id = ?", (daten.protokoll, update_id))
    return {"status": "fehler"}
