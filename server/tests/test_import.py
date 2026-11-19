import copy

from app import db

DATEN = {
    "quell_commit": "79ecc04",
    "faecher": [{"slug": "cc", "name": "Cloud Computing", "about_pfad": "cc/ABOUT.md", "about_hash": "a1"}],
    "themen": [
        {"schluessel": "cc/topics/docker", "fach": "cc", "parent": None, "titel": "Docker", "reihenfolge": 1},
        {"schluessel": "cc/topics/docker/06-net", "fach": "cc", "parent": "cc/topics/docker", "titel": "Networking", "reihenfolge": 6},
    ],
    "eintraege": [
        {"schluessel": "cc/topics/docker/06-net/TOPIC.md#modi", "thema": "cc/topics/docker/06-net", "art": "lernpunkt",
         "titel": "Netzwerkmodi erklären", "quellpfad": "cc/topics/docker/06-net/TOPIC.md", "anker": "Motivation", "quell_hash": "h1"},
        {"schluessel": "cc/origin-tasks/task-9/TASKS.md#1", "thema": "cc/topics/docker/06-net", "art": "aufgabe",
         "titel": "Aufgabe 9.1", "quellpfad": "cc/origin-tasks/task-9/TASKS.md", "anker": "1", "quell_hash": "h2", "punkte": 4},
    ],
}


def _zeilen(settings, sql):
    conn = db.verbinden(settings.db_pfad)
    try:
        return [dict(z) for z in conn.execute(sql)]
    finally:
        conn.close()


def test_import_braucht_auth(client):
    assert client.post("/api/import", json=DATEN).status_code == 401


def test_import_legt_alles_an(client, token, settings):
    antwort = client.post("/api/import", json=DATEN, headers=token)
    assert antwort.status_code == 200
    assert antwort.json() == {"faecher": 1, "themen": 2, "eintraege": 2}
    themen = _zeilen(settings, "SELECT titel, parent_id FROM themen ORDER BY id")
    assert themen[0]["parent_id"] is None and themen[1]["parent_id"] == 1
    assert _zeilen(settings, "SELECT wert FROM meta WHERE schluessel='quell_commit'") == [{"wert": "79ecc04"}]


def test_erneuter_import_aktualisiert_und_behaelt_lernstand(client, token, settings):
    client.post("/api/import", json=DATEN, headers=token)
    conn = db.verbinden(settings.db_pfad)
    conn.execute("UPDATE eintraege SET level=3, aktiv=0, status='geaendert', claude_wert=80, user_wert=85")
    conn.close()

    neu = copy.deepcopy(DATEN)
    neu["eintraege"][0]["titel"] = "Netzwerkmodi vergleichen"
    neu["eintraege"][0]["quell_hash"] = "h1b"
    assert client.post("/api/import", json=neu, headers=token).status_code == 200

    zeilen = _zeilen(settings, "SELECT titel, quell_hash, level, aktiv, status, claude_wert FROM eintraege ORDER BY id")
    assert len(zeilen) == 2
    assert zeilen[0] == {"titel": "Netzwerkmodi vergleichen", "quell_hash": "h1b", "level": 3,
                         "aktiv": 0, "status": "geaendert", "claude_wert": 80}


def test_unbekanntes_thema_wird_abgelehnt_und_nichts_geschrieben(client, token, settings):
    kaputt = copy.deepcopy(DATEN)
    kaputt["eintraege"][1]["thema"] = "gibt/es/nicht"
    antwort = client.post("/api/import", json=kaputt, headers=token)
    assert antwort.status_code == 422
    assert "gibt/es/nicht" in antwort.json()["detail"]
    assert _zeilen(settings, "SELECT * FROM faecher") == []
    assert _zeilen(settings, "SELECT * FROM eintraege") == []


def test_unbekannte_art_wird_abgelehnt(client, token):
    kaputt = copy.deepcopy(DATEN)
    kaputt["eintraege"][0]["art"] = "quiz"
    assert client.post("/api/import", json=kaputt, headers=token).status_code == 422


def test_thema_darf_auf_bestehendes_fach_verweisen(client, token):
    client.post("/api/import", json=DATEN, headers=token)
    nachtrag = {"themen": [{"schluessel": "cc/topics/k8s", "fach": "cc", "parent": None, "titel": "Kubernetes"}]}
    assert client.post("/api/import", json=nachtrag, headers=token).json() == {"faecher": 0, "themen": 1, "eintraege": 0}
