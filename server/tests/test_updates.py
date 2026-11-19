import pytest

from app import db

STOFF = {
    "quell_commit": "alt",
    "faecher": [{"slug": "cc", "name": "Cloud Computing"}],
    "themen": [{"schluessel": "cc/docker", "fach": "cc", "titel": "Docker"}],
    "eintraege": [
        {"schluessel": s, "thema": "cc/docker", "art": "lernpunkt", "titel": s.upper(), "quellpfad": "p", "quell_hash": "h"}
        for s in ("a", "b", "c")
    ],
}


@pytest.fixture
def api(client, token, settings):
    client.headers.update(token)
    assert client.post("/api/import", json=STOFF).status_code == 200
    conn = db.verbinden(settings.db_pfad)
    conn.execute("UPDATE eintraege SET level = 3")
    conn.execute("UPDATE eintraege SET aktiv = 0 WHERE schluessel = 'c'")
    conn.close()
    return client


def _eintraege(settings):
    conn = db.verbinden(settings.db_pfad)
    try:
        return {z["schluessel"]: (z["level"], z["status"], z["titel"]) for z in conn.execute("SELECT * FROM eintraege")}
    finally:
        conn.close()


def test_stand_und_start(api):
    assert api.get("/api/stand").json() == {"quell_commit": "alt", "letztes_update": None}
    update_id = api.post("/api/updates", json={"commit_von": "alt", "commit_bis": "neu"}).json()["id"]
    assert api.get("/api/stand").json()["letztes_update"]["status"] == "laeuft"
    # derselbe Commit startet keinen zweiten Lauf
    assert api.post("/api/updates", json={"commit_von": "alt", "commit_bis": "neu"}).status_code == 409
    # ein neuerer Commit schließt den liegengebliebenen Lauf ab
    assert api.post("/api/updates", json={"commit_von": "alt", "commit_bis": "neuer"}).status_code == 200
    assert [u["status"] for u in api.get("/api/updates").json()] == ["laeuft", "fehler"]
    assert api.post(f"/api/updates/{update_id}/anwenden", json={"zusammenfassung": "x"}).status_code == 409


def test_anwenden_setzt_regeln_um(api, settings):
    update_id = api.post("/api/updates", json={"commit_von": "alt", "commit_bis": "neu"}).json()["id"]
    antwort = api.post(f"/api/updates/{update_id}/anwenden", json={
        "zusammenfassung": "Docker überarbeitet", "protokoll": "a: Tippfehler …",
        "daten": {"eintraege": [
            {"schluessel": "a", "thema": "cc/docker", "art": "lernpunkt", "titel": "A neu", "quellpfad": "p", "quell_hash": "h2"},
            {"schluessel": "d", "thema": "cc/docker", "art": "aufgabe", "titel": "D", "quellpfad": "p", "quell_hash": "h"},
        ]},
        "stark_geaendert": ["b"], "archiviert": ["c"],
    })
    assert antwort.status_code == 200
    assert antwort.json() == {"status": "fertig", "faecher": 0, "themen": 0, "eintraege": 2,
                              "stark_geaendert": 1, "archiviert": 1}
    assert _eintraege(settings) == {
        "a": (3, "aktuell", "A neu"),       # kleine Änderung: Level bleibt
        "b": (2, "geaendert", "B"),         # starke Änderung: eine Stufe zurück
        "c": (3, "archiviert", "C"),        # gelöscht: archiviert, Level bleibt im Verlauf
        "d": (0, "aktuell", "D"),           # neu
    }
    stand = api.get("/api/stand").json()
    assert stand["quell_commit"] == "neu"
    assert (stand["letztes_update"]["status"], stand["letztes_update"]["zusammenfassung"]) == ("fertig", "Docker überarbeitet")
    assert api.post(f"/api/updates/{update_id}/anwenden", json={"zusammenfassung": "nochmal"}).status_code == 409


def test_fehler_im_update_aendert_nichts(api, settings):
    vorher = _eintraege(settings)
    update_id = api.post("/api/updates", json={"commit_von": "alt", "commit_bis": "neu"}).json()["id"]
    for kaputt in (
        {"zusammenfassung": "x", "stark_geaendert": ["a"], "archiviert": ["gibt-es-nicht"]},
        {"zusammenfassung": "x", "stark_geaendert": ["a"], "archiviert": ["a"]},
        {"zusammenfassung": "x", "stark_geaendert": ["a"], "daten": {"eintraege": [
            {"schluessel": "e", "thema": "fehlt", "art": "aufgabe", "titel": "E", "quellpfad": "p", "quell_hash": "h"}]}},
    ):
        assert api.post(f"/api/updates/{update_id}/anwenden", json=kaputt).status_code == 422
    assert _eintraege(settings) == vorher
    stand = api.get("/api/stand").json()
    assert stand["quell_commit"] == "alt" and stand["letztes_update"]["status"] == "laeuft"


def test_wieder_aufgetauchter_eintrag_wird_aktiv(api, settings):
    conn = db.verbinden(settings.db_pfad)
    conn.execute("UPDATE eintraege SET status = 'archiviert' WHERE schluessel = 'a'")
    conn.close()
    update_id = api.post("/api/updates", json={"commit_bis": "neu"}).json()["id"]
    api.post(f"/api/updates/{update_id}/anwenden", json={"zusammenfassung": "x", "daten": {"eintraege": [
        {"schluessel": "a", "thema": "cc/docker", "art": "lernpunkt", "titel": "A", "quellpfad": "p", "quell_hash": "h"}]}})
    assert _eintraege(settings)["a"] == (3, "aktuell", "A")


def test_fehlschlag_laesst_commit_stehen(api):
    update_id = api.post("/api/updates", json={"commit_von": "alt", "commit_bis": "neu"}).json()["id"]
    assert api.post(f"/api/updates/{update_id}/fehler", json={"protokoll": "Claude abgestürzt"}).json() == {"status": "fehler"}
    stand = api.get("/api/stand").json()
    assert stand["quell_commit"] == "alt" and stand["letztes_update"]["protokoll"] == "Claude abgestürzt"
    # danach darf derselbe Commit erneut versucht werden
    assert api.post("/api/updates", json={"commit_von": "alt", "commit_bis": "neu"}).status_code == 200


def test_auswahl_alle_enthaelt_deaktivierte(api):
    assert [e["schluessel"] for e in api.get("/api/eintraege", params={"fach": "cc"}).json()] == ["a", "b"]
    alle = api.get("/api/eintraege", params={"fach": "cc", "alle": "true"}).json()
    assert [e["schluessel"] for e in alle] == ["a", "b", "c"]
