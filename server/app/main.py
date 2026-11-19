import sqlite3
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import auth, db, importer, uebersicht
from .config import Settings

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    conn = db.verbinden(request.app.state.settings.db_pfad)
    try:
        yield conn
    finally:
        conn.close()


class LoginIn(BaseModel):
    passwort: str


class AktivIn(BaseModel):
    aktiv: bool


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.aus_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        conn = db.verbinden(settings.db_pfad)
        db.initialisieren(conn)
        conn.close()
        yield

    app = FastAPI(title="Lernsystem S3", lifespan=lifespan)
    app.state.settings = settings
    app.state.bremse = auth.LoginBremse()

    @app.get("/api/gesund")
    def gesund():
        return {"ok": True}

    @app.post("/api/login")
    def login(daten: LoginIn, request: Request, response: Response):
        adresse = request.headers.get("x-real-ip") or (request.client.host if request.client else "?")
        bremse: auth.LoginBremse = request.app.state.bremse
        if bremse.gesperrt(adresse):
            raise HTTPException(status_code=429, detail="Zu viele Fehlversuche, später erneut versuchen")
        if not auth.gleich(daten.passwort, settings.passwort):
            bremse.fehlversuch(adresse)
            raise HTTPException(status_code=401, detail="Falsches Passwort")
        response.set_cookie(
            auth.COOKIE,
            auth.cookie_erzeugen(settings.secret),
            max_age=auth.SITZUNG_SEKUNDEN,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
        )
        return {"angemeldet": True}

    @app.post("/api/logout")
    def logout(response: Response):
        response.delete_cookie(auth.COOKIE)
        return {"angemeldet": False}

    @app.get("/api/ich", dependencies=[Depends(auth.angemeldet)])
    def ich():
        return {"angemeldet": True}

    @app.post("/api/import", dependencies=[Depends(auth.angemeldet)])
    def import_(daten: importer.ImportIn, conn: sqlite3.Connection = Depends(get_db)):
        try:
            return importer.importieren(conn, daten)
        except importer.ImportFehler as fehler:
            raise HTTPException(status_code=422, detail=str(fehler)) from fehler

    @app.get("/api/uebersicht", dependencies=[Depends(auth.angemeldet)])
    def uebersicht_(conn: sqlite3.Connection = Depends(get_db)):
        return uebersicht.baum(conn)

    def _aktiv_setzen(conn: sqlite3.Connection, tabelle: str, id_: int, aktiv: bool) -> dict:
        geaendert = conn.execute(f"UPDATE {tabelle} SET aktiv = ? WHERE id = ?", (int(aktiv), id_)).rowcount
        if not geaendert:
            raise HTTPException(status_code=404, detail="Nicht gefunden")
        return {"id": id_, "aktiv": aktiv}

    @app.patch("/api/eintraege/{id_}", dependencies=[Depends(auth.angemeldet)])
    def eintrag_aktiv(id_: int, daten: AktivIn, conn: sqlite3.Connection = Depends(get_db)):
        return _aktiv_setzen(conn, "eintraege", id_, daten.aktiv)

    @app.patch("/api/themen/{id_}", dependencies=[Depends(auth.angemeldet)])
    def thema_aktiv(id_: int, daten: AktivIn, conn: sqlite3.Connection = Depends(get_db)):
        return _aktiv_setzen(conn, "themen", id_, daten.aktiv)

    # Zuletzt, damit die API-Routen Vorrang haben.
    if FRONTEND.is_dir():
        app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")

    return app
