import sqlite3

import pytest

from app import db

TABELLEN = {
    "faecher", "themen", "eintraege", "blaetter", "blatt_aufgaben",
    "blatt_aufgabe_eintraege", "dateien", "bewertungen", "updates", "meta",
}


def test_initialisieren_legt_alle_tabellen_an(tmp_path):
    conn = db.verbinden(str(tmp_path / "t.db"))
    db.initialisieren(conn)
    db.initialisieren(conn)  # zweimal aufrufbar
    namen = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert TABELLEN <= namen


def test_fremdschluessel_sind_aktiv(tmp_path):
    conn = db.verbinden(str(tmp_path / "t.db"))
    db.initialisieren(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO themen(fach_id, schluessel, titel) VALUES (999, 'x', 'X')"
        )


def test_neuer_eintrag_startet_auf_level_0(tmp_path):
    conn = db.verbinden(str(tmp_path / "t.db"))
    db.initialisieren(conn)
    conn.execute("INSERT INTO faecher(slug, name) VALUES ('f', 'F')")
    conn.execute("INSERT INTO themen(fach_id, schluessel, titel) VALUES (1, 't', 'T')")
    conn.execute(
        "INSERT INTO eintraege(schluessel, thema_id, art, titel, quellpfad, quell_hash)"
        " VALUES ('e', 1, 'lernpunkt', 'E', 'f/t/TOPIC.md', 'h')"
    )
    zeile = conn.execute("SELECT level, aktiv, status FROM eintraege").fetchone()
    assert (zeile["level"], zeile["aktiv"], zeile["status"]) == (0, 1, "aktuell")
