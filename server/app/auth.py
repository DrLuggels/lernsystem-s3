"""Auth: Bearer-Token für die CLI, signiertes Session-Cookie für den Browser."""

import hashlib
import hmac
import time

from fastapi import HTTPException, Request

COOKIE = "lern_sitzung"
SITZUNG_SEKUNDEN = 30 * 24 * 3600
MAX_FEHLVERSUCHE = 5
FENSTER_SEKUNDEN = 300


def _signatur(secret: str, ablauf: str) -> str:
    return hmac.new(secret.encode(), ablauf.encode(), hashlib.sha256).hexdigest()


def cookie_erzeugen(secret: str, jetzt: float | None = None) -> str:
    ablauf = str(int((jetzt or time.time()) + SITZUNG_SEKUNDEN))
    return f"{ablauf}.{_signatur(secret, ablauf)}"


def cookie_gueltig(secret: str, wert: str | None, jetzt: float | None = None) -> bool:
    if not wert or "." not in wert:
        return False
    ablauf, signatur = wert.split(".", 1)
    if not hmac.compare_digest(signatur.encode(), _signatur(secret, ablauf).encode()):
        return False
    return ablauf.isdigit() and int(ablauf) > (jetzt or time.time())


def gleich(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def angemeldet(request: Request) -> None:
    settings = request.app.state.settings
    kopf = request.headers.get("authorization", "")
    if kopf.startswith("Bearer ") and gleich(kopf[7:], settings.api_token):
        return
    if cookie_gueltig(settings.secret, request.cookies.get(COOKIE)):
        return
    raise HTTPException(status_code=401, detail="Nicht angemeldet")


class LoginBremse:
    """Begrenzt Fehlversuche je Adresse (im Speicher, reicht für einen Benutzer)."""

    def __init__(self) -> None:
        self._fehler: dict[str, list[float]] = {}

    def gesperrt(self, adresse: str) -> bool:
        grenze = time.time() - FENSTER_SEKUNDEN
        versuche = [t for t in self._fehler.get(adresse, []) if t > grenze]
        self._fehler[adresse] = versuche
        return len(versuche) >= MAX_FEHLVERSUCHE

    def fehlversuch(self, adresse: str) -> None:
        self._fehler.setdefault(adresse, []).append(time.time())
