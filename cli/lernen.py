#!/usr/bin/env python3
"""Lokaler Befehl `lernen`: spricht mit der Server-API. Nur Standardbibliothek."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
QUELLE = WURZEL / "dski-sources-3"


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lernen", description="Lernsystem S3")
    unter = parser.add_subparsers(dest="befehl", required=True)

    p_import = unter.add_parser("import", help="Extraktions-JSON prüfen und an den Server schicken")
    p_import.add_argument("dateien", nargs="+")
    p_import.add_argument("--commit-setzen", action="store_true",
                          help="aktuellen Quell-Commit als verarbeitet vermerken")
    p_import.set_defaults(funktion=befehl_import)

    unter.add_parser("status", help="Stand je Fach").set_defaults(funktion=befehl_status)

    args = parser.parse_args(argv)
    try:
        args.funktion(args)
    except Fehler as fehler:
        print(f"Fehler: {fehler}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
