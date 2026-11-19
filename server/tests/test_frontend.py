def test_startseite_wird_ohne_auth_ausgeliefert(client):
    antwort = client.get("/")
    assert antwort.status_code == 200
    assert "Lernstand" in antwort.text


def test_statische_dateien(client):
    assert client.get("/app.js").status_code == 200
    assert client.get("/style.css").status_code == 200


def test_api_hat_vorrang_vor_dem_frontend(client):
    assert client.get("/api/gesund").json() == {"ok": True}
    assert client.get("/api/uebersicht").status_code == 401
