# Lernsystem S3

Lernsystem für die Klausuren des 3. Semesters. Der Stoff kommt ausschließlich aus einem
getrennten Quell-Repo (`dski-sources-3`); dieses Repo enthält nur den Code.

```
Lokal (Claude Code angemeldet)              Server
┌───────────────────────────────┐          ┌──────────────────────────────┐
│ lernen            Blatt erzeugen │  HTTPS  │ API + SQLite (einzige DB)    │
│ lernen korrigieren Korrektur    │ ───────▶ │ Übersicht, Blätter, Login    │
│ dski-sources-3/   (git pull)    │  Token  │ Docker, kein Claude          │
└───────────────────────────────┘          └──────────────────────────────┘
```

- `server/` — API, Datenbank und Frontend (FastAPI + SQLite)
- `cli/lernen.py` — lokaler Befehl, spricht nur über die API mit dem Server
- `prompts/` — Anweisungen für Claude: Extraktion, Blatt, Korrektur, Quell-Update
- `docs/superpowers/specs/` — Design

## Ablauf

```fish
lernen                 # Quell-Repo aktualisieren, Thema wählen, Blatt erzeugen
lernen blatt docker    # dasselbe mit Thema (Name, Teil davon oder Nummer)
lernen korrigieren     # abgegebenes Blatt korrigieren, Level aktualisieren
lernen status          # Stand je Fach
lernen update diff     # was hat sich im Quell-Repo geändert?
lernen update log      # was hat das Update daraus gemacht?
lernen aus 42          # Eintrag 42 deaktivieren (nicht klausurrelevant); --thema für Themen
```

1. `lernen` zieht das Quell-Repo. Gibt es neue Commits, startet im Hintergrund eine
   Claude-Session, die die Einträge anpasst.
2. Claude erzeugt ein Blatt zu deinem Thema, bevorzugt aus den Einträgen mit dem niedrigsten
   Level, und schickt es an den Server.
3. Du bearbeitest das Blatt im Browser. Aufgaben zum Zeichnen kommen als PDF für Xournal++.
   Zu jeder Aufgabe gibst du an, wie sicher du dir bist, und gibst ab.
4. `lernen korrigieren` bewertet jede Aufgabe. Liegen Claudes Wert und dein Wert beide auf
   oder über der Schwelle des nächsten Levels, steigt der Eintrag eine Stufe.

| Level | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Schwelle | 50 % | 65 % | 80 % | 95 % | 100 % |

Als beherrscht zählt ein Eintrag ab Level 4.

## Einrichten (lokal)

```fish
git clone https://github.com/OfflineBot/dski-sources-3.git   # Quell-Repo, liegt im .gitignore
cp .env.example .env                                         # Werte setzen
fish fish/setup.fish                                         # Befehl `lernen` einhängen
```

In der lokalen `.env` stehen `LERN_URL` (Adresse des Servers) und `LERN_API_TOKEN`.

Für Tests und Entwicklung läuft der Server auch lokal:

```fish
docker compose up -d --build          # http://localhost:8099, LERN_COOKIE_SECURE=0 setzen
cd server; python3 -m venv .venv; .venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q                   # Server-Tests
cd ../cli; ../server/.venv/bin/pytest -q
```

## Server

```sh
git clone https://github.com/DrLuggels/lernsystem-s3.git && cd lernsystem-s3
cp .env.example .env     # LERN_API_TOKEN, LERN_PASSWORT, LERN_SECRET setzen
docker compose up -d --build
```

Der Container lauscht auf `LERN_PORT` (Standard 8099) und gehört hinter einen HTTPS-Proxy.
Die Datenbank liegt in `./data/`.

## Stoff einlesen

Die Erst-Extraktion macht Claude nach `prompts/EXTRAKTION.md`, je Fach eine JSON-Datei unter
`extraktion/`. Danach:

```fish
lernen import --commit-setzen extraktion/*.json
```

Der Import prüft jeden Quellpfad gegen das Quell-Repo und ändert nie einen Lernstand.
