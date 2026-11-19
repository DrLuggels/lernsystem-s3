#!/usr/bin/env python3
"""Lokaler Befehl `lernen`: spricht mit der Server-API. Nur Standardbibliothek."""

import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
QUELLE = WURZEL / "dski-sources-3"
SITZUNGEN = WURZEL / "sessions"
PROMPTS = WURZEL / "prompts"
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".pdf": "application/pdf"}


class Fehler(Exception):
    pass


# ---------- Konfiguration ----------

def env_datei_lesen(pfad: Path) -> dict[str, str]:
    werte: dict[str, str] = {}
    if not pfad.exists():
        return werte
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if zeile and not zeile.startswith("#") and "=" in zeile:
            name, wert = zeile.split("=", 1)
            werte[name.strip()] = wert.strip()
    return werte


def konfiguration() -> tuple[str, str]:
    """Liefert (URL, Token). Umgebungsvariablen haben Vorrang vor der .env im Repo."""
    datei = env_datei_lesen(WURZEL / ".env")
    url = os.environ.get("LERN_URL") or datei.get("LERN_URL") or "http://localhost:8099"
    token = os.environ.get("LERN_API_TOKEN") or datei.get("LERN_API_TOKEN")
    if not token:
        raise Fehler("LERN_API_TOKEN fehlt (Umgebung oder .env)")
    return url.rstrip("/"), token


# ---------- API ----------

def api(methode: str, pfad: str, daten: dict | None = None) -> object:
    url, token = konfiguration()
    anfrage = urllib.request.Request(
        url + pfad,
        method=methode,
        data=json.dumps(daten).encode() if daten is not None else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=30) as antwort:
            return json.loads(antwort.read())
    except urllib.error.HTTPError as fehler:
        text = fehler.read().decode(errors="replace")
        raise Fehler(f"Server antwortet {fehler.code}: {text}") from fehler
    except urllib.error.URLError as fehler:
        raise Fehler(f"Server {url} nicht erreichbar: {fehler.reason}") from fehler


# ---------- Import ----------

def datei_hash(pfad: Path) -> str:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()[:16]


def anreichern(daten: dict, quelle: Path) -> dict:
    """Prüft die Extraktion gegen das Quell-Repo und ergänzt die Hashes.

    Hashes rechnet immer dieses Skript, nie das Sprachmodell.
    """
    probleme: list[str] = []
    gesehen: set[str] = set()

    for fach in daten.get("faecher", []):
        about = fach.get("about_pfad")
        if about:
            if (quelle / about).is_file():
                fach["about_hash"] = datei_hash(quelle / about)
            else:
                probleme.append(f"Fach {fach.get('slug')}: {about} existiert nicht")

    for thema in daten.get("themen", []):
        schluessel = thema.get("schluessel", "")
        if schluessel in gesehen:
            probleme.append(f"Thema doppelt: {schluessel}")
        gesehen.add(schluessel)

    for eintrag in daten.get("eintraege", []):
        schluessel = eintrag.get("schluessel", "")
        if schluessel in gesehen:
            probleme.append(f"Eintrag doppelt: {schluessel}")
        gesehen.add(schluessel)
        pfad = eintrag.get("quellpfad", "")
        if pfad and (quelle / pfad).is_file():
            eintrag["quell_hash"] = datei_hash(quelle / pfad)
        else:
            probleme.append(f"Eintrag {schluessel}: Quelle '{pfad}' existiert nicht")

    if probleme:
        raise Fehler("Extraktion ungültig:\n- " + "\n- ".join(probleme))
    return daten


def quell_commit(quelle: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(quelle), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


def befehl_import(args: argparse.Namespace) -> None:
    for datei in args.dateien:
        daten = anreichern(json.loads(Path(datei).read_text(encoding="utf-8")), QUELLE)
        if args.commit_setzen:
            daten["quell_commit"] = quell_commit(QUELLE)
        ergebnis = api("POST", "/api/import", daten)
        print(f"{datei}: {ergebnis}")


# ---------- Status ----------

def befehl_status(_: argparse.Namespace) -> None:
    for fach in api("GET", "/api/uebersicht"):
        prozent = round(fach["fortschritt"] * 100)
        print(f"{fach['name']:<28} {fach['beherrscht']:>3} / {fach['gesamt']:<3} beherrscht  ({prozent} %)")


# ---------- Bereich wählen ----------

def bereiche(faecher: list[dict]) -> list[dict]:
    """Flache Liste aller wählbaren Bereiche: Fächer, Themen und Unterthemen mit aktiven Einträgen."""
    liste: list[dict] = []

    def themen(fach: dict, knoten: list[dict], tiefe: int) -> None:
        for t in knoten:
            if t["aktiv"] and t["gesamt"]:
                liste.append({"fach": fach["slug"], "thema": t["schluessel"], "tiefe": tiefe,
                              "name": t["titel"], "gesamt": t["gesamt"], "beherrscht": t["beherrscht"]})
                themen(fach, t["themen"], tiefe + 1)

    for fach in faecher:
        if fach["gesamt"]:
            liste.append({"fach": fach["slug"], "thema": None, "tiefe": 0, "name": fach["name"],
                          "gesamt": fach["gesamt"], "beherrscht": fach["beherrscht"]})
            themen(fach, fach["themen"], 1)
    return liste


def bereich_finden(liste: list[dict], suche: str) -> dict:
    """Findet einen Bereich über Nummer, Fach-Slug, Themen-Schlüssel oder einen Teil des Namens."""
    if suche.isdigit() and 1 <= int(suche) <= len(liste):
        return liste[int(suche) - 1]
    klein = suche.lower()
    for b in liste:
        if klein in (b["fach"].lower() if b["thema"] is None else b["thema"].lower()):
            return b
    treffer = [b for b in liste if klein in b["name"].lower()
               or klein in (b["thema"] or b["fach"]).lower()]
    if not treffer:
        raise Fehler(f"Kein Fach oder Thema passt zu '{suche}'")
    if len(treffer) > 1 and len({b["name"].lower() for b in treffer}) > 1:
        namen = ", ".join(b["name"] for b in treffer[:6])
        raise Fehler(f"'{suche}' ist mehrdeutig: {namen}")
    return treffer[0]


def nummer_waehlen(frage: str, zeilen: list[str], mit_null: str | None = None) -> int:
    """Zeigt ein kurzes Menü und liefert die gewählte Nummer (0 nur, wenn mit_null gesetzt ist)."""
    print()
    if mit_null:
        print(f"  0  {mit_null}")
    for nummer, zeile in enumerate(zeilen, 1):
        print(f"{nummer:>3}  {zeile}")
    while True:
        eingabe = input(f"\n{frage} ").strip()
        if eingabe.isdigit() and (0 if mit_null else 1) <= int(eingabe) <= len(zeilen):
            return int(eingabe)
        print("Bitte eine der Nummern eingeben.")


def bereich_waehlen(suche: str | None) -> dict:
    """Ohne Suchwort: erst das Fach, dann eines seiner großen Themen (oder das ganze Fach)."""
    liste = bereiche(api("GET", "/api/uebersicht"))
    if not liste:
        raise Fehler("Es gibt noch keine aktiven Einträge")
    if suche:
        return bereich_finden(liste, suche)
    zeile = lambda b: f"{b['name']}  ({b['beherrscht']}/{b['gesamt']} beherrscht)"
    faecher = [b for b in liste if b["tiefe"] == 0]
    fach = faecher[nummer_waehlen("Welches Fach?", [zeile(b) for b in faecher]) - 1]
    themen = [b for b in liste if b["tiefe"] == 1 and b["fach"] == fach["fach"]]
    if len(themen) < 2:
        return fach
    wahl = nummer_waehlen("Welches Thema?", [zeile(b) for b in themen], mit_null=f"alles aus {fach['name']}")
    return fach if wahl == 0 else themen[wahl - 1]


# ---------- Quell-Repo und Claude ----------

def quelle_aktualisieren() -> None:
    ergebnis = subprocess.run(["git", "-C", str(QUELLE), "pull", "--ff-only", "--quiet"],
                              capture_output=True, text=True)
    if ergebnis.returncode != 0:
        print(f"Hinweis: git pull im Quell-Repo fehlgeschlagen: {ergebnis.stderr.strip()}", file=sys.stderr)


def quelle_unveraendert() -> None:
    status = subprocess.run(["git", "-C", str(QUELLE), "status", "--porcelain"],
                            capture_output=True, text=True, check=True).stdout.strip()
    if status:
        raise Fehler("Im Quell-Repo wurden Dateien verändert. Das darf nicht passieren, bitte prüfen:\n" + status)


def claude_starten(prompt_datei: str, auftrag: str, werkzeuge: list[str], live: bool = False) -> None:
    """Startet Claude mit einem Prompt aus prompts/.

    live=True öffnet den Chat im Terminal: man sieht Claude arbeiten und kann eingreifen.
    Sonst läuft Claude ohne Chat durch (für Korrektur und Hintergrund-Updates).
    """
    prompt = (PROMPTS / prompt_datei).read_text(encoding="utf-8") + "\n\n## Auftrag\n\n" + auftrag
    befehl = ["claude", prompt] if live else ["claude", "-p", prompt]
    ergebnis = subprocess.run(
        [*befehl, "--permission-mode", "acceptEdits", "--allowedTools", *werkzeuge], cwd=WURZEL)
    quelle_unveraendert()
    if ergebnis.returncode != 0 and not live:
        raise Fehler(f"Claude wurde mit Fehler {ergebnis.returncode} beendet")


# ---------- Quell-Update ----------

def git_quelle(*argumente: str) -> str:
    return subprocess.run(["git", "-C", str(QUELLE), *argumente],
                          check=True, capture_output=True, text=True).stdout


def geaenderte_faecher(dateien: str) -> list[str]:
    """Fach-Ordner aus der Ausgabe von `git diff --name-status`."""
    faecher: set[str] = set()
    for zeile in dateien.splitlines():
        for pfad in zeile.split("\t")[1:]:
            if "/" in pfad:
                faecher.add(pfad.split("/", 1)[0])
    return sorted(faecher)


def update_pruefen() -> None:
    """Nach dem Pull: Wenn sich das Quell-Repo geändert hat, das Update im Hintergrund starten."""
    stand = api("GET", "/api/stand")
    alt, neu = stand["quell_commit"], quell_commit(QUELLE)
    if alt is None or alt == neu:
        return
    try:
        update_id = api("POST", "/api/updates", {"commit_von": alt, "commit_bis": neu})["id"]
    except Fehler as fehler:
        if "409" in str(fehler):
            print("Hinweis: Ein Quell-Update läuft bereits im Hintergrund.")
            return
        raise
    ordner = SITZUNGEN / "updates"
    ordner.mkdir(parents=True, exist_ok=True)
    with open(ordner / f"update-{update_id}.log", "w", encoding="utf-8") as log:
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "update", "ausfuehren", str(update_id)],
                         stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
    print(f"Das Quell-Repo hat neue Inhalte ({alt[:7]} → {neu[:7]}). Update {update_id} läuft im Hintergrund;\n"
          "  ansehen mit „lernen update diff“ und „lernen update log“. Du lernst solange mit dem alten Stand.")


def update_ausfuehren(update_id: int) -> None:
    lauf = next((u for u in api("GET", "/api/updates") if u["id"] == update_id), None)
    if lauf is None or lauf["status"] != "laeuft":
        raise Fehler(f"Update {update_id} läuft nicht")
    bereich = f"{lauf['commit_von']}..{lauf['commit_bis']}"
    sitzung = SITZUNGEN / "updates" / f"update-{update_id}"
    sitzung.mkdir(parents=True, exist_ok=True)
    try:
        dateien = git_quelle("diff", "--name-status", bereich)
        (sitzung / "dateien.txt").write_text(dateien, encoding="utf-8")
        (sitzung / "diff.patch").write_text(
            git_quelle("diff", bereich, "--", "*.md", ":(exclude)*/origin/*"), encoding="utf-8")
        vorhandene = {f["slug"] for f in api("GET", "/api/uebersicht")}
        eintraege = []
        for fach in geaenderte_faecher(dateien):
            if fach in vorhandene:
                eintraege += api("GET", f"/api/eintraege?{urllib.parse.urlencode({'fach': fach, 'alle': 'true'})}")
        (sitzung / "eintraege.json").write_text(json.dumps(eintraege, ensure_ascii=False, indent=1), encoding="utf-8")
        (sitzung / "update.json").unlink(missing_ok=True)

        relativ = sitzung.relative_to(WURZEL)
        claude_starten("UPDATE.md", f"Sitzungsordner: `{relativ}`\nCommits: `{bereich}`",
                       ["Read", "Glob", "Grep", "Write"])
        if not (sitzung / "update.json").is_file():
            raise Fehler("Claude hat kein update.json geschrieben")
        update = json.loads((sitzung / "update.json").read_text(encoding="utf-8"))
        update["daten"] = anreichern(update.get("daten") or {}, QUELLE)
        print(api("POST", f"/api/updates/{update_id}/anwenden", update))
    except Exception as fehler:
        api("POST", f"/api/updates/{update_id}/fehler", {"protokoll": f"{type(fehler).__name__}: {fehler}"[:4000]})
        raise


def befehl_update(args: argparse.Namespace) -> None:
    if args.aktion == "ausfuehren":
        if args.id is None:
            raise Fehler("Update-Nummer fehlt")
        update_ausfuehren(args.id)
        return
    updates = api("GET", "/api/updates")
    if not updates:
        print("Bisher gab es kein Quell-Update.")
        return
    if args.aktion == "diff":
        lauf = next((u for u in updates if u["id"] == args.id), None) if args.id else updates[0]
        if lauf is None:
            raise Fehler(f"Update {args.id} nicht gefunden")
        subprocess.run(["git", "-C", str(QUELLE), "diff", f"{lauf['commit_von']}..{lauf['commit_bis']}",
                        "--", ".", ":(exclude)*/origin/*"])
        return
    for u in updates[:1] if args.id is None else [x for x in updates if x["id"] == args.id]:
        print(f"Update {u['id']} · {u['am']} · {(u['commit_von'] or '')[:7]} → {u['commit_bis'][:7]} · {u['status']}")
        print(f"\n{u['zusammenfassung'] or '(noch keine Zusammenfassung)'}\n\n{u['protokoll'] or ''}")


# ---------- Blatt ----------

def blatt_dateien(sitzung: Path, blatt: dict) -> list[tuple[str, Path]]:
    """Dateien des Blatts als (Name, Pfad). Quellen müssen im Quell-Repo liegen."""
    dateien = []
    for d in blatt.get("dateien", []):
        pfad = (QUELLE / d["quelle"]).resolve()
        if not pfad.is_relative_to(QUELLE.resolve()) or not pfad.is_file():
            raise Fehler(f"Datei '{d['quelle']}' liegt nicht im Quell-Repo")
        dateien.append((d["name"], pfad))
    if (sitzung / "blatt.pdf").is_file():
        dateien.append(("blatt.pdf", sitzung / "blatt.pdf"))
    for name, pfad in dateien:
        if pfad.suffix.lower() not in MIME:
            raise Fehler(f"Dateityp von '{name}' wird nicht unterstützt")
    return dateien


def blatt_hochladen(sitzung: Path, bereich: dict) -> int:
    blatt = json.loads((sitzung / "blatt.json").read_text(encoding="utf-8"))
    dateien = blatt_dateien(sitzung, blatt)
    hat_pdf = any(a.get("format") == "pdf" for a in blatt.get("aufgaben", []))
    if hat_pdf and not (sitzung / "blatt.pdf").is_file():
        raise Fehler("Das Blatt hat PDF-Aufgaben, aber blatt.pdf fehlt")
    blatt_id = api("POST", "/api/blaetter", {
        "titel": blatt["titel"], "fach": bereich["fach"], "thema": bereich["thema"],
        "quell_commit": quell_commit(QUELLE), "aufgaben": blatt["aufgaben"],
    })["id"]
    for name, pfad in dateien:
        api("POST", f"/api/blaetter/{blatt_id}/dateien", {
            "name": name, "mime": MIME[pfad.suffix.lower()],
            "inhalt_base64": base64.b64encode(pfad.read_bytes()).decode(),
        })
    return blatt_id


def sitzung_hochladen(sitzung: Path, still: bool = False) -> int:
    """Schickt das Blatt einer Sitzung an den Server und benennt den Ordner in blatt-<id> um."""
    if not (sitzung / "blatt.json").is_file():
        raise Fehler(f"In {sitzung} liegt kein blatt.json")
    if (sitzung / "blatt_id").is_file():
        raise Fehler(f"Dieses Blatt ist schon hochgeladen (Blatt {(sitzung / 'blatt_id').read_text().strip()})")
    auftrag = json.loads((sitzung / "auftrag.json").read_text(encoding="utf-8"))
    blatt_id = blatt_hochladen(sitzung, {"fach": auftrag["fach"], "thema": auftrag.get("thema")})
    (sitzung / "blatt_id").write_text(str(blatt_id), encoding="utf-8")
    ziel = SITZUNGEN / f"blatt-{blatt_id}"
    sitzung.rename(ziel)
    url, _ = konfiguration()
    adresse = f"{url}/#/blatt/{blatt_id}"
    print(f"Blatt {blatt_id} liegt bereit: {adresse}")
    if not still and shutil.which("xdg-open"):
        subprocess.Popen(["xdg-open", adresse], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    if (ziel / "blatt.pdf").is_file():
        (ziel / "abgabe").mkdir(exist_ok=True)
        print(f"PDF-Teil: {ziel / 'blatt.pdf'}\n"
              f"  In Xournal++ ausfüllen und als {ziel / 'abgabe' / 'blatt.xopp'} speichern.")
        if shutil.which("xournalpp") and not still:
            subprocess.Popen(["xournalpp", str(ziel / "blatt.pdf")],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return blatt_id


def befehl_hochladen(args: argparse.Namespace) -> None:
    sitzung = (WURZEL / args.sitzung).resolve()
    if not sitzung.is_relative_to(SITZUNGEN.resolve()) or not sitzung.is_dir():
        raise Fehler(f"'{args.sitzung}' ist kein Sitzungsordner unter sessions/")
    sitzung_hochladen(sitzung, args.still)


def befehl_blatt(args: argparse.Namespace) -> None:
    quelle_aktualisieren()
    update_pruefen()
    bereich = bereich_waehlen(" ".join(args.bereich) or None)
    abfrage = urllib.parse.urlencode(
        {"thema": bereich["thema"]} if bereich["thema"] else {"fach": bereich["fach"]})
    eintraege = api("GET", f"/api/eintraege?{abfrage}")
    if not eintraege:
        raise Fehler(f"'{bereich['name']}' hat keine aktiven Einträge")

    sitzung = SITZUNGEN / f"neu-{time.strftime('%Y%m%d-%H%M%S')}"
    (sitzung / ".loesung").mkdir(parents=True)
    (sitzung / "auftrag.json").write_text(json.dumps({
        "bereich": bereich["name"], "fach": bereich["fach"], "thema": bereich["thema"],
        "anzahl": args.anzahl, "eintraege": eintraege,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    relativ = sitzung.relative_to(WURZEL)
    hochladen = f"python3 cli/lernen.py hochladen {relativ}" + (" --still" if args.still else "")
    print(f"\nClaude erstellt jetzt das Blatt zu „{bereich['name']}“ ({len(eintraege)} Einträge zur Auswahl).\n"
          "Der Chat öffnet sich; du kannst zusehen und eingreifen. Beenden mit /exit.\n")
    claude_starten(
        "AUFGABEN.md", f"Sitzungsordner: `{relativ}`\nBefehl zum Hochladen: `{hochladen}`",
        ["Read", "Glob", "Grep", "Write", "Edit", "Agent", "Bash(pdflatex:*)",
         "Bash(python3 cli/lernen.py hochladen:*)"],
        live=not args.ohne_chat)

    # Hat Claude das Blatt nicht selbst hochgeladen, holt das Skript es nach.
    if sitzung.is_dir():
        if not (sitzung / "blatt.json").is_file():
            raise Fehler(f"Es ist kein Blatt entstanden (Sitzung: {relativ})")
        sitzung_hochladen(sitzung, args.still)


# ---------- Korrektur ----------

def abgabe_exportieren(sitzung: Path) -> None:
    """Xournal++-Datei nach PDF exportieren, falls vorhanden."""
    xopp = sitzung / "abgabe" / "blatt.xopp"
    if xopp.is_file() and shutil.which("xournalpp"):
        subprocess.run(["xournalpp", str(xopp), "-p", str(sitzung / "abgabe" / "ausgefuellt.pdf")],
                       check=True, capture_output=True)


def befehl_korrigieren(args: argparse.Namespace) -> None:
    if args.blatt is None:
        wartend = [b for b in api("GET", "/api/blaetter") if b["status"] == "abgegeben"]
        if not wartend:
            raise Fehler("Kein abgegebenes Blatt gefunden. Erst auf der Seite „Blatt abgeben“ klicken.")
        blatt_id = wartend[-1]["id"]          # das älteste zuerst
    else:
        blatt_id = args.blatt
    blatt = api("GET", f"/api/blaetter/{blatt_id}")
    if blatt["status"] != "abgegeben":
        raise Fehler(f"Blatt {blatt_id} ist {blatt['status']}, nicht abgegeben")

    sitzung = SITZUNGEN / f"blatt-{blatt_id}"
    sitzung.mkdir(parents=True, exist_ok=True)
    abgabe_exportieren(sitzung)
    hat_pdf = any(a["format"] == "pdf" for a in blatt["aufgaben"])
    if hat_pdf and not (sitzung / "abgabe" / "ausgefuellt.pdf").is_file():
        print("Hinweis: Das Blatt hat PDF-Aufgaben, aber es liegt keine handschriftliche Abgabe vor "
              f"({sitzung / 'abgabe' / 'blatt.xopp'}). Diese Aufgaben werden mit 0 bewertet.")
        if not args.ja and input("Trotzdem korrigieren? [j/N] ").strip().lower() != "j":
            raise Fehler("Abgebrochen")
    (sitzung / "abgabe.json").write_text(json.dumps(blatt, ensure_ascii=False, indent=1), encoding="utf-8")
    (sitzung / "korrektur.json").unlink(missing_ok=True)

    relativ = sitzung.relative_to(WURZEL)
    print(f"Korrigiere Blatt {blatt_id} „{blatt['titel']}“ …")
    claude_starten("KORREKTUR.md", f"Sitzungsordner: `{relativ}`", ["Read", "Glob", "Grep", "Write"])
    if not (sitzung / "korrektur.json").is_file():
        raise Fehler(f"Claude hat kein korrektur.json geschrieben (siehe {relativ})")

    korrektur = json.loads((sitzung / "korrektur.json").read_text(encoding="utf-8"))
    ergebnis = api("POST", f"/api/blaetter/{blatt_id}/korrektur", {"aufgaben": korrektur["aufgaben"]})
    print()
    for a in ergebnis["aenderungen"]:
        pfeil = (f"Level {a['level_vorher']} → {a['level_nachher']}" if a["level_nachher"] > a["level_vorher"]
                 else f"bleibt Level {a['level_nachher']}")
        print(f"  {pfeil:<16} Claude {a['claude_wert']:>3} %  Ich {a['user_wert']:>3} %  {a['titel']}")
    url, _ = konfiguration()
    print(f"\nKorrektur: {url}/#/blatt/{blatt_id}")


# ---------- Deaktivieren ----------

def befehl_aktiv(args: argparse.Namespace) -> None:
    tabelle = "themen" if args.thema else "eintraege"
    api("PATCH", f"/api/{tabelle}/{args.id}", {"aktiv": args.befehl == "an"})
    print(f"{'Thema' if args.thema else 'Eintrag'} {args.id} ist jetzt {'aktiv' if args.befehl == 'an' else 'deaktiviert'}.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lernen", description="Lernsystem S3")
    unter = parser.add_subparsers(dest="befehl", required=True)

    p_import = unter.add_parser("import", help="Extraktions-JSON prüfen und an den Server schicken")
    p_import.add_argument("dateien", nargs="+")
    p_import.add_argument("--commit-setzen", action="store_true",
                          help="aktuellen Quell-Commit als verarbeitet vermerken")
    p_import.set_defaults(funktion=befehl_import)

    unter.add_parser("status", help="Stand je Fach").set_defaults(funktion=befehl_status)

    p_blatt = unter.add_parser("blatt", help="Thema wählen und Übungsblatt erzeugen")
    p_blatt.add_argument("bereich", nargs="*", help="Fach oder Thema (Name, Teil davon oder Nummer)")
    p_blatt.add_argument("--anzahl", type=int, default=8, help="Zahl der Aufgaben (Standard: 8)")
    p_blatt.add_argument("--still", action="store_true", help="Browser und Xournal++ nicht öffnen")
    p_blatt.add_argument("--ohne-chat", action="store_true", help="Claude ohne Live-Chat durchlaufen lassen")
    p_blatt.set_defaults(funktion=befehl_blatt)

    p_hoch = unter.add_parser("hochladen", help="fertiges Blatt einer Sitzung an den Server schicken")
    p_hoch.add_argument("sitzung", help="Sitzungsordner, z. B. sessions/neu-20261119-101500")
    p_hoch.add_argument("--still", action="store_true", help="Browser und Xournal++ nicht öffnen")
    p_hoch.set_defaults(funktion=befehl_hochladen)

    p_korr = unter.add_parser("korrigieren", help="abgegebenes Blatt korrigieren")
    p_korr.add_argument("blatt", nargs="?", type=int, help="Blatt-Nummer (Standard: ältestes abgegebenes)")
    p_korr.add_argument("--ja", action="store_true", help="Rückfragen mit Ja beantworten")
    p_korr.set_defaults(funktion=befehl_korrigieren)

    for name, hilfe in (("aus", "Eintrag oder Thema deaktivieren"), ("an", "Eintrag oder Thema aktivieren")):
        p_aktiv = unter.add_parser(name, help=hilfe)
        p_aktiv.add_argument("id", type=int)
        p_aktiv.add_argument("--thema", action="store_true", help="die Nummer meint ein Thema")
        p_aktiv.set_defaults(funktion=befehl_aktiv)

    p_update = unter.add_parser("update", help="Quell-Updates ansehen")
    p_update.add_argument("aktion", choices=["diff", "log", "ausfuehren"],
                          help="diff: Änderungen im Quell-Repo · log: Protokoll · ausfuehren: intern")
    p_update.add_argument("id", nargs="?", type=int, help="Update-Nummer (Standard: das letzte)")
    p_update.set_defaults(funktion=befehl_update)

    # Ohne Befehl: Blatt erzeugen.
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        argv = ["blatt"]
    args = parser.parse_args(argv)
    try:
        args.funktion(args)
    except Fehler as fehler:
        print(f"Fehler: {fehler}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as fehler:
        print(f"Fehler: Eine von Claude geschriebene Datei ist kein gültiges JSON ({fehler})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
