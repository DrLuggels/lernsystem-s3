import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path):
    return Settings(
        db_pfad=str(tmp_path / "test.db"),
        api_token="test-token",
        passwort="geheim",
        secret="test-secret",
        cookie_secure=False,
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def token():
    return {"Authorization": "Bearer test-token"}
