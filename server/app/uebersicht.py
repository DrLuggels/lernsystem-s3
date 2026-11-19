"""Baum Fach → Thema → Unterthema → Einträge mit Zählern für die Übersicht."""

import sqlite3

from . import level


def _zaehler(gesamt: int, beherrscht: int, level_summe: int) -> dict:
    fortschritt = round(level_summe / (level.MAX_LEVEL * gesamt), 2) if gesamt else 0.0
    return {"gesamt": gesamt, "beherrscht": beherrscht, "fortschritt": fortschritt}


def baum(conn: sqlite3.Connection) -> list[dict]:
    eintraege_je_thema: dict[int, list[dict]] = {}
    for z in conn.execute(
        "SELECT id, thema_id, art, titel, kurztext, quellpfad, anker, punkte, aktiv, status,"
        " level, claude_wert, user_wert FROM eintraege WHERE status != 'archiviert' ORDER BY id"
    ):
        eintrag = dict(z)
        eintrag["aktiv"] = bool(eintrag["aktiv"])
        eintraege_je_thema.setdefault(eintrag.pop("thema_id"), []).append(eintrag)

    kinder: dict[tuple[int, int | None], list[sqlite3.Row]] = {}
    for z in conn.execute("SELECT id, fach_id, parent_id, titel, aktiv FROM themen ORDER BY reihenfolge, id"):
        kinder.setdefault((z["fach_id"], z["parent_id"]), []).append(z)

    def knoten(zeile: sqlite3.Row) -> tuple[dict, int, int, int]:
        eintraege = eintraege_je_thema.get(zeile["id"], [])
        aktive = [e for e in eintraege if e["aktiv"]]
        gesamt = len(aktive)
        beherrscht = sum(1 for e in aktive if level.ist_beherrscht(e["level"]))
        summe = sum(e["level"] for e in aktive)
        unterthemen = []
        for kind in kinder.get((zeile["fach_id"], zeile["id"]), []):
            unter, g, b, s = knoten(kind)
            unterthemen.append(unter)
            gesamt, beherrscht, summe = gesamt + g, beherrscht + b, summe + s
        if not zeile["aktiv"]:
            gesamt = beherrscht = summe = 0
        thema = {
            "id": zeile["id"],
            "titel": zeile["titel"],
            "aktiv": bool(zeile["aktiv"]),
            **_zaehler(gesamt, beherrscht, summe),
            "themen": unterthemen,
            "eintraege": eintraege,
        }
        return thema, gesamt, beherrscht, summe

    ergebnis = []
    for fach in conn.execute("SELECT id, slug, name FROM faecher ORDER BY name"):
        gesamt = beherrscht = summe = 0
        themen = []
        for wurzel in kinder.get((fach["id"], None), []):
            thema, g, b, s = knoten(wurzel)
            themen.append(thema)
            gesamt, beherrscht, summe = gesamt + g, beherrscht + b, summe + s
        ergebnis.append({
            "id": fach["id"], "slug": fach["slug"], "name": fach["name"],
            **_zaehler(gesamt, beherrscht, summe), "themen": themen,
        })
    return ergebnis
