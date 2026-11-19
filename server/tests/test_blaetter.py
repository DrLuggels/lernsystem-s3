import base64

import pytest

from app import db

STOFF = {
    "faecher": [{"slug": "cc", "name": "Cloud Computing"}],
    "themen": [
        {"schluessel": "cc/docker", "fach": "cc", "titel": "Docker"},
        {"schluessel": "cc/docker/01", "fach": "cc", "parent": "cc/docker", "titel": "Grundlagen"},
        {"schluessel": "cc/docker/02", "fach": "cc", "parent": "cc/docker", "titel": "Container"},
    ],
    "eintraege": [
        {"schluessel": "a", "thema": "cc/docker/01", "art": "lernpunkt", "titel": "A", "quellpfad": "p", "quell_hash": "h"},
        {"schluessel": "b", "thema": "cc/docker/01", "art": "aufgabe", "titel": "B", "quellpfad": "p", "quell_hash": "h"},
        {"schluessel": "c", "thema": "cc/docker/02", "art": "lernpunkt", "titel": "C", "quellpfad": "p", "quell_hash": "h"},
    ],
}

BLATT = {
    "titel": "Docker Grundlagen", "fach": "cc", "thema": "cc/docker", "quell_commit": "abc",
    "aufgaben": [
        {"nummer": 1, "format": "text", "text": "Erkläre **A**.", "punkte": 4, "eintraege": ["a"]},
        {"nummer": 2, "format": "code", "text": "Schreibe B.", "punkte": 6, "eintraege": ["a", "b"],
         "vorgabe": {"sprache": "dockerfile"}},
    ],
}


@pytest.fixture
def api(client, token):
    client.headers.update(token)
    assert client.post("/api/import", json=STOFF).status_code == 200
    return client


@pytest.fixture
def blatt_id(api):
    return api.post("/api/blaetter", json=BLATT).json()["id"]


def _level(settings):
    conn = db.verbinden(settings.db_pfad)
    try:
        return {z["schluessel"]: z["level"] for z in conn.execute("SELECT schluessel, level FROM eintraege")}
    finally:
        conn.close()


def _abgeben(api, blatt_id, werte=(60, 90)):
    blatt = api.get(f"/api/blaetter/{blatt_id}").json()
    for aufgabe, wert in zip(blatt["aufgaben"], werte):
        antwort = api.put(f"/api/blaetter/{blatt_id}/aufgaben/{aufgabe['id']}",
                          json={"antwort": f"Antwort {aufgabe['nummer']}", "user_wert": wert})
        assert antwort.status_code == 200
    assert api.post(f"/api/blaetter/{blatt_id}/abgeben").status_code == 200


def _korrektur(claude=(70, 50)):
    return {"aufgaben": [
        {"nummer": 1, "erreichte_punkte": 3, "claude_wert": claude[0], "feedback": "gut", "musterloesung": "L1",
         "quellverweis": "p#A"},
        {"nummer": 2, "erreichte_punkte": 3, "claude_wert": claude[1], "feedback": "geht", "musterloesung": "L2"},
    ]}


def test_blaetter_brauchen_auth(client):
    assert client.get("/api/blaetter").status_code == 401
    assert client.post("/api/blaetter", json=BLATT).status_code == 401


def test_anlegen_und_lesen(api, blatt_id):
    blatt = api.get(f"/api/blaetter/{blatt_id}").json()
    assert (blatt["titel"], blatt["status"], blatt["quell_commit"]) == ("Docker Grundlagen", "offen", "abc")
    assert [a["nummer"] for a in blatt["aufgaben"]] == [1, 2]
    assert blatt["aufgaben"][1]["vorgabe"] == {"sprache": "dockerfile"}
    assert [e["schluessel"] for e in blatt["aufgaben"][1]["eintraege"]] == ["a", "b"]
    eintrag = api.get("/api/blaetter").json()[0]
    assert (eintrag["aufgaben"], eintrag["punkte"], eintrag["fach"]) == (2, 10, "Cloud Computing")


def test_unbekannter_eintrag_wird_abgelehnt_und_nichts_angelegt(api):
    kaputt = {**BLATT, "aufgaben": [{**BLATT["aufgaben"][0], "eintraege": ["gibt-es-nicht"]}]}
    antwort = api.post("/api/blaetter", json=kaputt)
    assert antwort.status_code == 422 and "gibt-es-nicht" in antwort.json()["detail"]
    assert api.get("/api/blaetter").json() == []


def test_aufgabe_ohne_eintrag_wird_abgelehnt(api):
    kaputt = {**BLATT, "aufgaben": [{**BLATT["aufgaben"][0], "eintraege": []}]}
    assert api.post("/api/blaetter", json=kaputt).status_code == 422


def test_antwort_wird_gespeichert_und_einzelne_felder_bleiben(api, blatt_id):
    aufgabe = api.get(f"/api/blaetter/{blatt_id}").json()["aufgaben"][0]
    pfad = f"/api/blaetter/{blatt_id}/aufgaben/{aufgabe['id']}"
    api.put(pfad, json={"antwort": "Entwurf"})
    api.put(pfad, json={"user_wert": 70})
    gespeichert = api.get(f"/api/blaetter/{blatt_id}").json()["aufgaben"][0]
    assert (gespeichert["antwort"], gespeichert["user_wert"]) == ("Entwurf", 70)
    assert api.put(pfad, json={"user_wert": 101}).status_code == 422
    assert api.put(f"/api/blaetter/{blatt_id}/aufgaben/9999", json={"antwort": "x"}).status_code == 404


def test_abgeben_verlangt_sicherheit_je_aufgabe(api, blatt_id):
    antwort = api.post(f"/api/blaetter/{blatt_id}/abgeben")
    assert antwort.status_code == 422 and "1, 2" in antwort.json()["detail"]
    _abgeben(api, blatt_id)
    blatt = api.get(f"/api/blaetter/{blatt_id}").json()
    assert blatt["status"] == "abgegeben"
    # Nach der Abgabe ist das Blatt gesperrt.
    pfad = f"/api/blaetter/{blatt_id}/aufgaben/{blatt['aufgaben'][0]['id']}"
    assert api.put(pfad, json={"antwort": "nachträglich"}).status_code == 409
    assert api.post(f"/api/blaetter/{blatt_id}/abgeben").status_code == 409


def test_korrektur_vor_abgabe_wird_abgelehnt(api, blatt_id):
    assert api.post(f"/api/blaetter/{blatt_id}/korrektur", json=_korrektur()).status_code == 409


def test_korrektur_hebt_level_nach_der_schwaechsten_aufgabe(api, blatt_id, settings):
    # user: Aufgabe 1 = 60, Aufgabe 2 = 90; claude: Aufgabe 1 = 70, Aufgabe 2 = 50
    _abgeben(api, blatt_id, werte=(60, 90))
    antwort = api.post(f"/api/blaetter/{blatt_id}/korrektur", json=_korrektur(claude=(70, 50)))
    assert antwort.status_code == 200
    aenderungen = {a["titel"]: a for a in antwort.json()["aenderungen"]}
    # a hängt an beiden Aufgaben: claude min(70, 50) = 50, user min(60, 90) = 60 -> Level 1
    assert (aenderungen["A"]["claude_wert"], aenderungen["A"]["user_wert"]) == (50, 60)
    assert (aenderungen["A"]["level_vorher"], aenderungen["A"]["level_nachher"]) == (0, 1)
    # b hängt nur an Aufgabe 2: claude 50, user 90 -> Level 1
    assert aenderungen["B"]["level_nachher"] == 1
    assert _level(settings) == {"a": 1, "b": 1, "c": 0}

    blatt = api.get(f"/api/blaetter/{blatt_id}").json()
    assert blatt["status"] == "korrigiert"
    assert blatt["aufgaben"][0]["musterloesung"] == "L1" and blatt["aufgaben"][0]["erreichte_punkte"] == 3
    assert len(blatt["bewertungen"]) == 2


def test_kein_aufstieg_wenn_ein_wert_unter_der_schwelle_liegt(api, blatt_id, settings):
    _abgeben(api, blatt_id, werte=(49, 100))
    api.post(f"/api/blaetter/{blatt_id}/korrektur", json=_korrektur(claude=(100, 100)))
    assert _level(settings) == {"a": 0, "b": 1, "c": 0}


def test_doppelte_korrektur_wird_abgelehnt(api, blatt_id, settings):
    _abgeben(api, blatt_id, werte=(100, 100))
    assert api.post(f"/api/blaetter/{blatt_id}/korrektur", json=_korrektur(claude=(100, 100))).status_code == 200
    assert api.post(f"/api/blaetter/{blatt_id}/korrektur", json=_korrektur(claude=(100, 100))).status_code == 409
    assert _level(settings)["a"] == 1


def test_unvollstaendige_korrektur_aendert_nichts(api, blatt_id, settings):
    _abgeben(api, blatt_id, werte=(100, 100))
    halb = {"aufgaben": _korrektur()["aufgaben"][:1]}
    assert api.post(f"/api/blaetter/{blatt_id}/korrektur", json=halb).status_code == 422
    zu_viel = _korrektur()
    zu_viel["aufgaben"][0]["erreichte_punkte"] = 5
    assert api.post(f"/api/blaetter/{blatt_id}/korrektur", json=zu_viel).status_code == 422
    assert api.get(f"/api/blaetter/{blatt_id}").json()["status"] == "abgegeben"
    assert _level(settings)["a"] == 0


def test_korrektur_setzt_geaendert_zurueck(api, blatt_id, settings):
    conn = db.verbinden(settings.db_pfad)
    conn.execute("UPDATE eintraege SET status = 'geaendert' WHERE schluessel = 'a'")
    conn.close()
    _abgeben(api, blatt_id)
    api.post(f"/api/blaetter/{blatt_id}/korrektur", json=_korrektur())
    conn = db.verbinden(settings.db_pfad)
    assert conn.execute("SELECT status FROM eintraege WHERE schluessel = 'a'").fetchone()["status"] == "aktuell"
    conn.close()


def test_loeschen_nur_vor_der_korrektur(api, blatt_id):
    zweites = api.post("/api/blaetter", json=BLATT).json()["id"]
    assert api.delete(f"/api/blaetter/{zweites}").status_code == 200
    assert api.get(f"/api/blaetter/{zweites}").status_code == 404
    _abgeben(api, blatt_id)
    api.post(f"/api/blaetter/{blatt_id}/korrektur", json=_korrektur())
    assert api.delete(f"/api/blaetter/{blatt_id}").status_code == 409


def test_dateien(api, blatt_id):
    inhalt = b"\x89PNG fake"
    daten = {"name": "bild-1.png", "mime": "image/png", "inhalt_base64": base64.b64encode(inhalt).decode()}
    assert api.post(f"/api/blaetter/{blatt_id}/dateien", json=daten).json() == {"name": "bild-1.png", "bytes": 9}
    antwort = api.get(f"/api/blaetter/{blatt_id}/dateien/bild-1.png")
    assert antwort.content == inhalt and antwort.headers["content-type"] == "image/png"
    assert api.get(f"/api/blaetter/{blatt_id}").json()["dateien"] == ["bild-1.png"]
    assert api.get(f"/api/blaetter/{blatt_id}/dateien/fehlt.png").status_code == 404
    assert api.post(f"/api/blaetter/{blatt_id}/dateien", json={**daten, "mime": "text/html"}).status_code == 422
    assert api.post(f"/api/blaetter/{blatt_id}/dateien", json={**daten, "name": "../x.png"}).status_code == 422
    assert api.post(f"/api/blaetter/{blatt_id}/dateien", json={**daten, "inhalt_base64": "###"}).status_code == 422


def test_auswahl_nach_fach_und_thema(api, settings):
    assert [e["schluessel"] for e in api.get("/api/eintraege", params={"fach": "cc"}).json()] == ["a", "b", "c"]
    nur = api.get("/api/eintraege", params={"thema": "cc/docker/02"}).json()
    assert [(e["schluessel"], e["thema"]) for e in nur] == [("c", "cc/docker/02")]
    assert api.get("/api/eintraege", params={"thema": "gibt/es/nicht"}).status_code == 404
    assert api.get("/api/eintraege").status_code == 422


def test_auswahl_schwaechste_zuerst_und_ohne_deaktivierte(api, settings):
    conn = db.verbinden(settings.db_pfad)
    conn.execute("UPDATE eintraege SET level = 3 WHERE schluessel = 'a'")
    conn.execute("UPDATE eintraege SET aktiv = 0 WHERE schluessel = 'b'")
    conn.close()
    assert [e["schluessel"] for e in api.get("/api/eintraege", params={"fach": "cc"}).json()] == ["c", "a"]
    conn = db.verbinden(settings.db_pfad)
    conn.execute("UPDATE themen SET aktiv = 0 WHERE schluessel = 'cc/docker/02'")
    conn.close()
    assert [e["schluessel"] for e in api.get("/api/eintraege", params={"fach": "cc"}).json()] == ["a"]


def test_alte_datenbank_bekommt_neue_spalte(tmp_path):
    conn = db.verbinden(str(tmp_path / "alt.db"))
    conn.execute("CREATE TABLE blatt_aufgaben (id INTEGER PRIMARY KEY, blatt_id INTEGER, nummer INTEGER,"
                 " format TEXT, text TEXT, punkte REAL)")
    db.initialisieren(conn)
    assert "vorgabe" in {z["name"] for z in conn.execute("PRAGMA table_info(blatt_aufgaben)")}
