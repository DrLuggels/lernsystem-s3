import pytest

from app import db

DATEN = {
    "faecher": [{"slug": "cc", "name": "Cloud Computing"}, {"slug": "se", "name": "Systems Engineering"}],
    "themen": [
        {"schluessel": "cc/docker", "fach": "cc", "titel": "Docker", "reihenfolge": 1},
        {"schluessel": "cc/docker/02", "fach": "cc", "parent": "cc/docker", "titel": "Container", "reihenfolge": 2},
        {"schluessel": "cc/docker/01", "fach": "cc", "parent": "cc/docker", "titel": "Grundlagen", "reihenfolge": 1},
    ],
    "eintraege": [
        {"schluessel": "a", "thema": "cc/docker/01", "art": "lernpunkt", "titel": "A", "quellpfad": "p", "quell_hash": "h"},
        {"schluessel": "b", "thema": "cc/docker/01", "art": "aufgabe", "titel": "B", "quellpfad": "p", "quell_hash": "h"},
        {"schluessel": "c", "thema": "cc/docker/02", "art": "klausurfrage", "titel": "C", "quellpfad": "p", "quell_hash": "h"},
        {"schluessel": "d", "thema": "cc/docker/02", "art": "lernpunkt", "titel": "D", "quellpfad": "p", "quell_hash": "h"},
    ],
}


@pytest.fixture
def gefuellt(client, token, settings):
    assert client.post("/api/import", json=DATEN, headers=token).status_code == 200
    conn = db.verbinden(settings.db_pfad)
    conn.execute("UPDATE eintraege SET level=5 WHERE schluessel='a'")
    conn.execute("UPDATE eintraege SET level=4 WHERE schluessel='b'")
    conn.execute("UPDATE eintraege SET level=1 WHERE schluessel='c'")
    conn.execute("UPDATE eintraege SET status='archiviert' WHERE schluessel='d'")
    conn.close()
    return client


def _cc(client, token):
    faecher = client.get("/api/uebersicht", headers=token).json()
    return next(f for f in faecher if f["slug"] == "cc")


def test_braucht_auth(client):
    assert client.get("/api/uebersicht").status_code == 401


def test_zaehler_und_reihenfolge(gefuellt, token):
    faecher = gefuellt.get("/api/uebersicht", headers=token).json()
    assert [f["slug"] for f in faecher] == ["cc", "se"]
    cc = faecher[0]
    assert (cc["gesamt"], cc["beherrscht"], cc["fortschritt"]) == (3, 2, 0.67)
    docker = cc["themen"][0]
    assert [t["titel"] for t in docker["themen"]] == ["Grundlagen", "Container"]
    grundlagen, container = docker["themen"]
    assert (grundlagen["gesamt"], grundlagen["beherrscht"], grundlagen["fortschritt"]) == (2, 2, 0.9)
    assert (container["gesamt"], container["beherrscht"], container["fortschritt"]) == (1, 0, 0.2)
    assert [e["titel"] for e in container["eintraege"]] == ["C"]  # archiviert fehlt
    assert faecher[1]["gesamt"] == 0 and faecher[1]["fortschritt"] == 0.0


def test_eintrag_deaktivieren(gefuellt, token):
    eintrag_id = _cc(gefuellt, token)["themen"][0]["themen"][0]["eintraege"][0]["id"]
    antwort = gefuellt.patch(f"/api/eintraege/{eintrag_id}", json={"aktiv": False}, headers=token)
    assert antwort.status_code == 200
    cc = _cc(gefuellt, token)
    assert (cc["gesamt"], cc["beherrscht"]) == (2, 1)
    assert cc["themen"][0]["themen"][0]["eintraege"][0]["aktiv"] is False


def test_thema_deaktivieren_zaehlt_unterthemen_nicht(gefuellt, token):
    docker_id = _cc(gefuellt, token)["themen"][0]["id"]
    assert gefuellt.patch(f"/api/themen/{docker_id}", json={"aktiv": False}, headers=token).status_code == 200
    cc = _cc(gefuellt, token)
    assert (cc["gesamt"], cc["beherrscht"], cc["fortschritt"]) == (0, 0, 0.0)
    assert cc["themen"][0]["aktiv"] is False
    assert len(cc["themen"][0]["themen"]) == 2  # bleibt sichtbar


def test_unbekannte_id_404(client, token):
    assert client.patch("/api/eintraege/999", json={"aktiv": False}, headers=token).status_code == 404
    assert client.patch("/api/themen/999", json={"aktiv": False}, headers=token).status_code == 404
