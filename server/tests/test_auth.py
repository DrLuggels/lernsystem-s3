def test_gesund_ohne_auth(client):
    assert client.get("/api/gesund").json() == {"ok": True}


def test_ohne_auth_401(client):
    assert client.get("/api/ich").status_code == 401


def test_bearer_token(client, token):
    assert client.get("/api/ich", headers=token).json() == {"angemeldet": True}


def test_falscher_token_401(client):
    assert client.get("/api/ich", headers={"Authorization": "Bearer falsch"}).status_code == 401


def test_login_setzt_cookie_und_logout_entfernt_es(client):
    assert client.post("/api/login", json={"passwort": "falsch"}).status_code == 401
    antwort = client.post("/api/login", json={"passwort": "geheim"})
    assert antwort.status_code == 200
    assert "httponly" in antwort.headers["set-cookie"].lower()
    assert client.get("/api/ich").status_code == 200
    client.post("/api/logout")
    assert client.get("/api/ich").status_code == 401


def test_manipuliertes_cookie_401(client):
    client.cookies.set("lern_sitzung", "9999999999.abcdef")
    assert client.get("/api/ich").status_code == 401


def test_login_bremse_nach_fuenf_fehlversuchen(client):
    for _ in range(5):
        assert client.post("/api/login", json={"passwort": "x"}).status_code == 401
    assert client.post("/api/login", json={"passwort": "geheim"}).status_code == 429
