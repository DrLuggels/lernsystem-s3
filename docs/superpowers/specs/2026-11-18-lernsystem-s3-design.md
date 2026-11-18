# Lernsystem Semester 3 — Design

Stand: 18.11.2026

## Ziel

Ein Lernsystem für die Klausuren des 3. Semesters. Der Stoff kommt ausschließlich aus dem
Quell-Repo `dski-sources-3` (github.com/OfflineBot/dski-sources-3), das regelmäßig aktualisiert
wird. Claude erzeugt lokal Übungsblätter und korrigiert sie; der Lernstand liegt auf einem Server
und ist dort im Browser einsehbar und bearbeitbar.

## Grundsätze

- **Das Quell-Repo ist die Wahrheit.** Gefragt wird nur, was dort steht. Die Datenbank speichert
  Verweise und Lernstand, keine eigene Fassung des Stoffs. Blatt-Texte werden bei der Generierung
  frisch aus dem Repo gelesen.
- **Das Quell-Repo wird nie verändert** (siehe dessen README: keine KI-Schreibzugriffe auf
  `ABOUT.md` und `origin/`; das Lernsystem schreibt dort überhaupt nicht).
- **Die Datenbank liegt auf dem Server.** Der lokale Rechner hält keinen eigenen Lernstand, er
  spricht nur über die API.
- **Claude läuft nur lokal** (dort ist Claude Code angemeldet). Der Server enthält keine KI.
- **Öffentliches Repo enthält nur Code.** Quell-Repo, Datenbank, Sessions und `.env` sind in der
  `.gitignore`.

## Komponenten

```
lernsystem-s3/                 öffentliches Repo (GitHub: DrLuggels/lernsystem-s3)
├── server/                    FastAPI-App + SQLite + Frontend, läuft im Docker-Container
│   ├── app/                   API, Level-Logik, Auth, DB-Zugriff
│   └── frontend/              Übersicht, Blatt-Ansicht, Korrektur-Ansicht (ohne Framework)
├── cli/                       lokaler Befehl `lernen` (Python), API-Client
├── prompts/ + .claude/agents/ Extraktion, Aufgabensteller, Gegenprüfer, Korrektor, Updater
├── fish/                      fish-Funktion und Completions
├── docker-compose.yml
├── dski-sources-3/            (gitignore) Klon des Quell-Repos
└── sessions/                  (gitignore) lokale Arbeitsdateien: PDFs, Musterlösungen
```

### Server

- FastAPI, SQLite in einem Docker-Volume, Frontend als statische Dateien aus derselben App.
- Deployment nach `new_website.md`: Klon nach `/mnt/.ix-apps/app_mounts/dockge/stacks/`,
  `docker compose up -d --build`, nginx-Block für `lernen.luggels.com`, DDNS-Eintrag.
  Der Port wird vor dem Start auf dem Server geprüft.
- Auth: Browser per Passwort-Login (Session-Cookie), CLI per Bearer-Token. Beide Geheimnisse
  stehen nur in der `.env` (Server) bzw. in der lokalen Konfiguration, nie im Repo.
- Für die Entwicklung läuft dieselbe App lokal (`docker compose up` oder uvicorn).

### CLI `lernen`

| Befehl | Wirkung |
|---|---|
| `lernen` / `lernen <thema>` | Pull + ggf. Update-Session, dann Thema wählen und Blatt erzeugen |
| `lernen korrigieren` | abgegebenes Blatt korrigieren, Level aktualisieren |
| `lernen status` | Überblick: offene Blätter, Stand je Fach |
| `lernen update diff` / `log` | Diff des letzten Quell-Updates und Protokoll der Update-Session |
| `lernen aus <id>` / `an <id>` | Eintrag oder Thema deaktivieren / aktivieren |

## Datenmodell

| Tabelle | Inhalt |
|---|---|
| `faecher` | slug, Name, Hinweise aus `ABOUT.md` (als Verweis + Hash) |
| `themen` | Thema und Unterthema (parent_id), Quellpfad, Reihenfolge, aktiv |
| `eintraege` | Art (`aufgabe`, `klausurfrage`, `lernpunkt`), Unterthema, Titel, Kurztext, Quellpfad, Anker, Quell-Hash, Punkte, aktiv, Status (`aktuell`, `geaendert`, `archiviert`) |
| `stand` | je Eintrag: Level 0–5, letzter Claude-Wert %, letzter User-Wert %, Zeitpunkt |
| `blaetter` | Thema, Status (`offen`, `abgegeben`, `korrigiert`), Quell-Commit, Zeitpunkte |
| `blatt_aufgaben` | Aufgabentext (Markdown), Format (`text`, `tabelle`, `code`, `pdf`), zugehörige Einträge, Punkte, Antwort, User-Sicherheit %, Korrektur (Punkte, Claude-Wert %, Feedback, Musterlösung, Quellverweis) |
| `dateien` | Bilder und PDFs zu Blättern |
| `bewertungen` | Verlauf: Eintrag, Blatt, Claude %, User %, Level vorher/nachher |
| `updates` | Commit von/bis, Zusammenfassung, Protokoll, Status |
| `meta` | zuletzt verarbeiteter Quell-Commit |

Jeder Eintrag hat einen stabilen Schlüssel aus Quellpfad und Anker, damit der Lernstand
Aktualisierungen übersteht.

**Extraktion:**
- `TASKS.md` und `EXAM.md`: jede (Teil-)Aufgabe wird ein Eintrag, wortgetreu referenziert.
  Claude ordnet jeden Eintrag einem Unterthema zu.
- `topics/<thema>/<nn-unterthema>/TOPIC.md`: Claude zerlegt den Stoff in prüfbare Lernpunkte.
- `ABOUT.md` steuert Gewichtung und Klausurformat (z. B. ca. 33 % BSDS-Fragen in Systems
  Engineering).
- Claude schreibt nicht direkt in die DB, sondern liefert JSON an einen validierenden
  Import-Endpunkt.

## Level

| Level | Schwelle |
|---|---|
| 1 | 50 % |
| 2 | 65 % |
| 3 | 80 % |
| 4 | 95 % |
| 5 | 100 % |

- Neue Einträge starten auf Level 0.
- Bei der Abgabe gibt der User je Aufgabe an, wie sicher er sich ist (%), bevor er die
  Korrektur sieht. Claude vergibt bei der Korrektur seinen Wert (%).
- Liegen beide Werte auf oder über der Schwelle des nächsten Levels, steigt jeder zugehörige
  Eintrag genau eine Stufe. Sonst bleibt das Level.
- Abstieg nur durch Quell-Updates (siehe unten).
- Die Level-Logik läuft auf dem Server, damit es genau eine Stelle gibt.
- „Beherrscht" = Level ≥ 4. Themen-Fortschritt = beherrschte / aktive Einträge; zusätzlich ein
  Balken aus dem Durchschnittslevel.

## Abläufe

### Start und Quell-Update

1. `lernen` führt `git pull` in `dski-sources-3/` aus.
2. Weicht HEAD vom zuletzt verarbeiteten Commit ab, startet im Hintergrund eine
   `claude -p`-Session mit enger Werkzeugliste. Sie liest `git diff <alt>..<neu>` und meldet je
   betroffenem Eintrag an die API:
   - kleine Änderung (Tippfehler, Umformulierung): Verweis/Hash aktualisieren, Level bleibt
   - inhaltlich starke Änderung: Status `geaendert`, Level eine Stufe zurück
   - neu: Eintrag anlegen (Level 0)
   - gelöscht: Status `archiviert` (Verlauf bleibt)
3. Protokoll und Commit-Bereich landen in `updates`. Schlägt die Session fehl, bleibt der alte
   Commit als „zuletzt verarbeitet" stehen und der nächste Start versucht es erneut.
4. Währenddessen kann mit dem bisherigen Stand weitergelernt werden.

### Blatt erzeugen

1. User wählt Fach, Thema oder Unterthema.
2. Die CLI holt die aktiven Einträge des Bereichs mit Level von der API. Der Aufgabensteller
   wählt bevorzugt die niedrigsten Level, liest die Quelldateien und erzeugt das Blatt als JSON.
3. Ein Gegenprüfer-Agent prüft jede Aufgabe gegen die Quelle (nichts außerhalb des Repos, keine
   Fehler). Die Musterlösung bleibt lokal in `sessions/<blatt>/.loesung/`.
4. Das Blatt wird samt Bildern an den Server geschickt.

### Bearbeiten

- **Format `text`, `tabelle`, `code`:** auf der Server-Seite. Eine generische Blatt-Ansicht
  rendert die Aufgaben und speichert Antworten automatisch. Bearbeitung von jedem Gerät möglich.
- **Format `pdf`** (Diagramme, handschriftliche Rechnungen): LaTeX-PDF, lokal in Xournal++ oder
  auf dem reMarkable. Die Abgabe bleibt lokal; das PDF ist zusätzlich auf dem Server abrufbar.
- Abgabe: je Aufgabe Sicherheit in % angeben, dann „Abgeben".

### Korrigieren

`lernen korrigieren` holt Antworten und User-Werte von der API (und exportiert ggf. die
Xournal++-Datei), der Korrektor bewertet je Aufgabe: Punkte, Claude-Wert %, Fehleranalyse,
Musterlösung mit Quellverweis. Das Ergebnis geht an die API; der Server berechnet die Level und
zeigt die Korrektur-Ansicht.

### Deaktivieren

Einträge und ganze Themen lassen sich im Frontend oder per CLI deaktivieren (nicht
klausurrelevant). Deaktiviertes erscheint in keinem Blatt und zählt nicht im Score.

## Frontend

- **Übersicht:** eine Karte je Fach mit „x von y beherrscht" und Balken. Aufklappbar: Themen →
  Unterthemen → Einträge mit Level, beiden Prozentwerten, Status und Schalter zum Deaktivieren.
- **Blätter:** Liste offener, abgegebener und korrigierter Blätter; Blatt-Ansicht zum
  Bearbeiten; Korrektur-Ansicht.
- **Updates:** Liste der Quell-Updates mit Zusammenfassung.
- Neues Design für textlastige Fächer (BWL, Systems Engineering, Cloud Computing), auch am
  Handy gut bedienbar.

## Fehlerfälle

- Server nicht erreichbar: `lernen` bricht mit klarer Meldung ab; lokal erzeugte, noch nicht
  hochgeladene Blätter bleiben in `sessions/` und werden beim nächsten Aufruf nachgereicht.
- Import mit ungültigem JSON oder unbekanntem Quellpfad: wird abgelehnt, nichts wird teilweise
  geschrieben.
- Doppelte Korrektur desselben Blatts: wird abgelehnt (Level steigen nur einmal je Blatt).

## Tests

- pytest für Level-Logik, Import-Validierung, Update-Regeln, Auth und die API-Endpunkte.
- Ein Durchlauf von Hand mit einem echten Blatt je Format vor dem Deployment.

## Umsetzungsreihenfolge

1. Repo, Server-Grundgerüst, DB-Schema, Level-Logik, Auth
2. Import-Endpunkt und Erst-Extraktion aller Fächer
3. Frontend: Übersicht
4. Blatt-Ablauf: erzeugen, bearbeiten (Web + PDF), korrigieren
5. Deployment auf dem Server
6. Update-Automatik

## Nicht enthalten

- Tagesplan, Kalender und Vorrat des alten Systems
- Mehrere Benutzer
- Blatt-Generierung auf dem Server
