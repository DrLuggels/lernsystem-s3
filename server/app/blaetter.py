"""Übungsblätter: anlegen, bearbeiten, abgeben, korrigieren. Die Level-Regel wird hier angewendet."""

import base64
import binascii
import json
import sqlite3
from typing import Literal

from pydantic import BaseModel, Field

from . import level

ERLAUBTE_MIME = {"image/png", "image/jpeg", "application/pdf"}


class AufgabeIn(BaseModel):
    nummer: int
    format: Literal["text", "tabelle", "code", "pdf"]
    text: str
    punkte: float = Field(0, ge=0)
    vorgabe: dict | None = None
    eintraege: list[str] = Field(min_length=1)


class BlattIn(BaseModel):
    titel: str
    fach: str | None = None
    thema: str | None = None
    quell_commit: str | None = None
    aufgaben: list[AufgabeIn] = Field(min_length=1)


class AntwortIn(BaseModel):
    antwort: str | None = None
    user_wert: int | None = Field(None, ge=0, le=100)


class KorrekturAufgabe(BaseModel):
    nummer: int
    erreichte_punkte: float = Field(ge=0)
    claude_wert: int = Field(ge=0, le=100)
    feedback: str = ""
    musterloesung: str = ""
    quellverweis: str = ""


class KorrekturIn(BaseModel):
    aufgaben: list[KorrekturAufgabe]


class DateiIn(BaseModel):
    name: str = Field(pattern=r"^[\w.-]{1,120}$")
    mime: str
    inhalt_base64: str


class BlattFehler(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _blatt(conn: sqlite3.Connection, blatt_id: int) -> sqlite3.Row:
    zeile = conn.execute("SELECT * FROM blaetter WHERE id = ?", (blatt_id,)).fetchone()
    if zeile is None:
        raise BlattFehler(404, "Blatt nicht gefunden")
    return zeile


def _optional_id(conn: sqlite3.Connection, tabelle: str, spalte: str, wert: str | None) -> int | None:
    if wert is None:
        return None
    zeile = conn.execute(f"SELECT id FROM {tabelle} WHERE {spalte} = ?", (wert,)).fetchone()
    if zeile is None:
        raise BlattFehler(422, f"Unbekannter Verweis '{wert}'")
    return zeile["id"]


def anlegen(conn: sqlite3.Connection, daten: BlattIn) -> dict:
    nummern = [a.nummer for a in daten.aufgaben]
    if len(set(nummern)) != len(nummern):
        raise BlattFehler(422, "Aufgabennummern sind nicht eindeutig")
    conn.execute("BEGIN")
    try:
        fach_id = _optional_id(conn, "faecher", "slug", daten.fach)
        thema_id = _optional_id(conn, "themen", "schluessel", daten.thema)
        blatt_id = conn.execute(
            "INSERT INTO blaetter(titel, fach_id, thema_id, quell_commit) VALUES (?, ?, ?, ?)",
            (daten.titel, fach_id, thema_id, daten.quell_commit),
        ).lastrowid
        for a in daten.aufgaben:
            aufgabe_id = conn.execute(
                "INSERT INTO blatt_aufgaben(blatt_id, nummer, format, text, punkte, vorgabe) VALUES (?, ?, ?, ?, ?, ?)",
                (blatt_id, a.nummer, a.format, a.text, a.punkte,
                 json.dumps(a.vorgabe, ensure_ascii=False) if a.vorgabe is not None else None),
            ).lastrowid
            for schluessel in dict.fromkeys(a.eintraege):
                eintrag = conn.execute(
                    "SELECT id FROM eintraege WHERE schluessel = ? AND status != 'archiviert'", (schluessel,)
                ).fetchone()
                if eintrag is None:
                    raise BlattFehler(422, f"Aufgabe {a.nummer}: unbekannter Eintrag '{schluessel}'")
                conn.execute(
                    "INSERT INTO blatt_aufgabe_eintraege(aufgabe_id, eintrag_id) VALUES (?, ?)",
                    (aufgabe_id, eintrag["id"]),
                )
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return {"id": blatt_id}


def liste(conn: sqlite3.Connection) -> list[dict]:
    return [dict(z) for z in conn.execute(
        "SELECT b.id, b.titel, b.status, b.erstellt_am, b.abgegeben_am, b.korrigiert_am,"
        " f.name AS fach, COUNT(a.id) AS aufgaben, COALESCE(SUM(a.punkte), 0) AS punkte,"
        " SUM(a.erreichte_punkte) AS erreichte_punkte,"
        " SUM(a.format = 'pdf') AS pdf_aufgaben"
        " FROM blaetter b LEFT JOIN faecher f ON f.id = b.fach_id"
        " LEFT JOIN blatt_aufgaben a ON a.blatt_id = b.id"
        " GROUP BY b.id ORDER BY b.id DESC"
    )]


def lesen(conn: sqlite3.Connection, blatt_id: int) -> dict:
    blatt = dict(_blatt(conn, blatt_id))
    aufgaben = []
    for z in conn.execute("SELECT * FROM blatt_aufgaben WHERE blatt_id = ? ORDER BY nummer", (blatt_id,)):
        aufgabe = dict(z)
        aufgabe.pop("blatt_id")
        aufgabe["vorgabe"] = json.loads(aufgabe["vorgabe"]) if aufgabe["vorgabe"] else None
        aufgabe["eintraege"] = [dict(e) for e in conn.execute(
            "SELECT e.id, e.schluessel, e.titel, e.level FROM eintraege e"
            " JOIN blatt_aufgabe_eintraege v ON v.eintrag_id = e.id WHERE v.aufgabe_id = ? ORDER BY e.id",
            (aufgabe["id"],),
        )]
        aufgaben.append(aufgabe)
    blatt["aufgaben"] = aufgaben
    blatt["dateien"] = [z["name"] for z in conn.execute(
        "SELECT name FROM dateien WHERE blatt_id = ? ORDER BY name", (blatt_id,))]
    return blatt


def antwort_speichern(conn: sqlite3.Connection, blatt_id: int, aufgabe_id: int, daten: AntwortIn) -> dict:
    if _blatt(conn, blatt_id)["status"] != "offen":
        raise BlattFehler(409, "Blatt ist bereits abgegeben")
    felder = daten.model_dump(exclude_unset=True)
    if not felder:
        return {"gespeichert": False}
    zuweisung = ", ".join(f"{name} = ?" for name in felder)
    geaendert = conn.execute(
        f"UPDATE blatt_aufgaben SET {zuweisung} WHERE id = ? AND blatt_id = ?",
        (*felder.values(), aufgabe_id, blatt_id),
    ).rowcount
    if not geaendert:
        raise BlattFehler(404, "Aufgabe nicht gefunden")
    return {"gespeichert": True}


def abgeben(conn: sqlite3.Connection, blatt_id: int) -> dict:
    if _blatt(conn, blatt_id)["status"] != "offen":
        raise BlattFehler(409, "Blatt ist bereits abgegeben")
    fehlend = [z["nummer"] for z in conn.execute(
        "SELECT nummer FROM blatt_aufgaben WHERE blatt_id = ? AND user_wert IS NULL ORDER BY nummer", (blatt_id,))]
    if fehlend:
        raise BlattFehler(422, "Sicherheit fehlt bei Aufgabe " + ", ".join(map(str, fehlend)))
    conn.execute("UPDATE blaetter SET status = 'abgegeben', abgegeben_am = datetime('now') WHERE id = ?", (blatt_id,))
    return {"status": "abgegeben"}


def korrigieren(conn: sqlite3.Connection, blatt_id: int, daten: KorrekturIn) -> dict:
    conn.execute("BEGIN")
    try:
        status = _blatt(conn, blatt_id)["status"]
        if status == "offen":
            raise BlattFehler(409, "Blatt ist noch nicht abgegeben")
        if status == "korrigiert":
            raise BlattFehler(409, "Blatt ist bereits korrigiert")

        aufgaben = {z["nummer"]: z for z in conn.execute(
            "SELECT id, nummer, punkte, user_wert FROM blatt_aufgaben WHERE blatt_id = ?", (blatt_id,))}
        korrektur = {k.nummer: k for k in daten.aufgaben}
        if len(korrektur) != len(daten.aufgaben) or set(korrektur) != set(aufgaben):
            raise BlattFehler(422, "Die Korrektur muss jede Aufgabe des Blatts genau einmal enthalten")

        # Je Eintrag zählt die schwächste Aufgabe des Blatts; ein Blatt hebt höchstens eine Stufe.
        werte: dict[int, tuple[int, int]] = {}
        for nummer, k in korrektur.items():
            aufgabe = aufgaben[nummer]
            if k.erreichte_punkte > aufgabe["punkte"]:
                raise BlattFehler(422, f"Aufgabe {nummer}: mehr Punkte als erreichbar")
            conn.execute(
                "UPDATE blatt_aufgaben SET erreichte_punkte = ?, claude_wert = ?, feedback = ?,"
                " musterloesung = ?, quellverweis = ? WHERE id = ?",
                (k.erreichte_punkte, k.claude_wert, k.feedback, k.musterloesung, k.quellverweis, aufgabe["id"]),
            )
            for v in conn.execute(
                "SELECT eintrag_id FROM blatt_aufgabe_eintraege WHERE aufgabe_id = ?", (aufgabe["id"],)
            ).fetchall():
                bisher = werte.get(v["eintrag_id"], (100, 100))
                werte[v["eintrag_id"]] = (min(bisher[0], k.claude_wert), min(bisher[1], aufgabe["user_wert"]))

        aenderungen = []
        for eintrag_id, (claude_wert, user_wert) in sorted(werte.items()):
            eintrag = conn.execute("SELECT titel, level FROM eintraege WHERE id = ?", (eintrag_id,)).fetchone()
            nachher = level.neues_level(eintrag["level"], claude_wert, user_wert)
            conn.execute(
                "UPDATE eintraege SET level = ?, claude_wert = ?, user_wert = ?, bewertet_am = datetime('now'),"
                " status = CASE status WHEN 'geaendert' THEN 'aktuell' ELSE status END WHERE id = ?",
                (nachher, claude_wert, user_wert, eintrag_id),
            )
            conn.execute(
                "INSERT INTO bewertungen(eintrag_id, blatt_id, claude_wert, user_wert, level_vorher, level_nachher)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (eintrag_id, blatt_id, claude_wert, user_wert, eintrag["level"], nachher),
            )
            aenderungen.append({
                "eintrag_id": eintrag_id, "titel": eintrag["titel"], "claude_wert": claude_wert,
                "user_wert": user_wert, "level_vorher": eintrag["level"], "level_nachher": nachher,
            })
        conn.execute(
            "UPDATE blaetter SET status = 'korrigiert', korrigiert_am = datetime('now') WHERE id = ?", (blatt_id,))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return {"status": "korrigiert", "aenderungen": aenderungen}


def loeschen(conn: sqlite3.Connection, blatt_id: int) -> dict:
    if _blatt(conn, blatt_id)["status"] == "korrigiert":
        raise BlattFehler(409, "Korrigierte Blätter gehören zum Verlauf und werden nicht gelöscht")
    conn.execute("DELETE FROM blaetter WHERE id = ?", (blatt_id,))
    return {"geloescht": blatt_id}


def bewertungen(conn: sqlite3.Connection, blatt_id: int) -> list[dict]:
    return [dict(z) for z in conn.execute(
        "SELECT b.eintrag_id, e.titel, b.claude_wert, b.user_wert, b.level_vorher, b.level_nachher"
        " FROM bewertungen b JOIN eintraege e ON e.id = b.eintrag_id WHERE b.blatt_id = ? ORDER BY b.id",
        (blatt_id,),
    )]


def datei_speichern(conn: sqlite3.Connection, blatt_id: int, daten: DateiIn) -> dict:
    _blatt(conn, blatt_id)
    if daten.mime not in ERLAUBTE_MIME:
        raise BlattFehler(422, f"Dateityp {daten.mime} ist nicht erlaubt")
    try:
        inhalt = base64.b64decode(daten.inhalt_base64, validate=True)
    except (binascii.Error, ValueError) as fehler:
        raise BlattFehler(422, "Inhalt ist kein gültiges Base64") from fehler
    conn.execute(
        "INSERT INTO dateien(blatt_id, name, mime, inhalt) VALUES (?, ?, ?, ?)"
        " ON CONFLICT(blatt_id, name) DO UPDATE SET mime = excluded.mime, inhalt = excluded.inhalt",
        (blatt_id, daten.name, daten.mime, inhalt),
    )
    return {"name": daten.name, "bytes": len(inhalt)}


def datei_lesen(conn: sqlite3.Connection, blatt_id: int, name: str) -> tuple[str, bytes]:
    zeile = conn.execute(
        "SELECT mime, inhalt FROM dateien WHERE blatt_id = ? AND name = ?", (blatt_id, name)).fetchone()
    if zeile is None:
        raise BlattFehler(404, "Datei nicht gefunden")
    return zeile["mime"], zeile["inhalt"]


def auswahl(conn: sqlite3.Connection, fach: str | None, thema: str | None, alle: bool = False) -> list[dict]:
    """Einträge eines Fachs oder Themas (mit Unterthemen), schwächste zuerst.

    Standard: nur aktive Einträge in aktiven Themen (für Blätter). Mit alle=True auch
    deaktivierte (für Quell-Updates); archivierte nie.
    """
    nur_aktive_themen = "" if alle else "aktiv = 1 AND "
    nur_aktive_kinder = "" if alle else " WHERE t.aktiv = 1"
    nur_aktive_eintraege = "" if alle else " AND e.aktiv = 1"
    if thema is not None:
        start, parameter, wofuer = "schluessel = ?", thema, "Thema"
    elif fach is not None:
        start = "parent_id IS NULL AND fach_id = (SELECT id FROM faecher WHERE slug = ?)"
        parameter, wofuer = fach, "Fach"
    else:
        raise BlattFehler(422, "fach oder thema angeben")
    tabelle, spalte = ("themen", "schluessel") if thema is not None else ("faecher", "slug")
    if conn.execute(f"SELECT 1 FROM {tabelle} WHERE {spalte} = ?", (parameter,)).fetchone() is None:
        raise BlattFehler(404, f"{wofuer} '{parameter}' nicht gefunden")
    return [dict(z) for z in conn.execute(
        f"WITH RECURSIVE baum(id) AS ("
        f"  SELECT id FROM themen WHERE {nur_aktive_themen}{start}"
        f"  UNION ALL SELECT t.id FROM themen t JOIN baum b ON t.parent_id = b.id{nur_aktive_kinder})"
        f" SELECT e.id, e.schluessel, e.art, e.titel, e.kurztext, e.quellpfad, e.anker, e.punkte, e.level, e.aktiv,"
        f" e.status, e.bewertet_am, t.schluessel AS thema, t.titel AS thema_titel"
        f" FROM eintraege e JOIN themen t ON t.id = e.thema_id"
        f" WHERE e.thema_id IN (SELECT id FROM baum){nur_aktive_eintraege} AND e.status != 'archiviert'"
        f" ORDER BY e.level, e.bewertet_am IS NOT NULL, e.bewertet_am, e.id",
        (parameter,),
    )]
