import sqlite3

from fastapi import APIRouter, Depends, Response

from . import auth, blaetter, db

router = APIRouter(prefix="/api", dependencies=[Depends(auth.angemeldet)])
DB = Depends(db.get_db)


@router.get("/eintraege")
def eintraege(fach: str | None = None, thema: str | None = None, conn: sqlite3.Connection = DB):
    return blaetter.auswahl(conn, fach, thema)


@router.post("/blaetter")
def anlegen(daten: blaetter.BlattIn, conn: sqlite3.Connection = DB):
    return blaetter.anlegen(conn, daten)


@router.get("/blaetter")
def liste(conn: sqlite3.Connection = DB):
    return blaetter.liste(conn)


@router.get("/blaetter/{blatt_id}")
def lesen(blatt_id: int, conn: sqlite3.Connection = DB):
    blatt = blaetter.lesen(conn, blatt_id)
    blatt["bewertungen"] = blaetter.bewertungen(conn, blatt_id)
    return blatt


@router.delete("/blaetter/{blatt_id}")
def loeschen(blatt_id: int, conn: sqlite3.Connection = DB):
    return blaetter.loeschen(conn, blatt_id)


@router.put("/blaetter/{blatt_id}/aufgaben/{aufgabe_id}")
def antwort(blatt_id: int, aufgabe_id: int, daten: blaetter.AntwortIn, conn: sqlite3.Connection = DB):
    return blaetter.antwort_speichern(conn, blatt_id, aufgabe_id, daten)


@router.post("/blaetter/{blatt_id}/abgeben")
def abgeben(blatt_id: int, conn: sqlite3.Connection = DB):
    return blaetter.abgeben(conn, blatt_id)


@router.post("/blaetter/{blatt_id}/korrektur")
def korrektur(blatt_id: int, daten: blaetter.KorrekturIn, conn: sqlite3.Connection = DB):
    return blaetter.korrigieren(conn, blatt_id, daten)


@router.post("/blaetter/{blatt_id}/dateien")
def datei_hochladen(blatt_id: int, daten: blaetter.DateiIn, conn: sqlite3.Connection = DB):
    return blaetter.datei_speichern(conn, blatt_id, daten)


@router.get("/blaetter/{blatt_id}/dateien/{name}")
def datei(blatt_id: int, name: str, conn: sqlite3.Connection = DB):
    mime, inhalt = blaetter.datei_lesen(conn, blatt_id, name)
    return Response(content=inhalt, media_type=mime, headers={"X-Content-Type-Options": "nosniff"})
