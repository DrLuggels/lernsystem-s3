# Extraktion eines Fachs

Du liest ein Fach aus dem Quell-Repo `dski-sources-3/` und schreibst eine JSON-Datei, die das
Lernsystem importiert. Lies zuerst `dski-sources-3/README.md` (Aufbau des Repos).

## Regeln

- **Nur lesen.** Im Ordner `dski-sources-3/` wird nichts geändert, angelegt oder gelöscht.
- **Nichts erfinden.** Jeder Eintrag verweist auf eine existierende Datei und beschreibt nur,
  was dort steht. Kein Wissen von außerhalb des Repos.
- Lies nur Markdown-Dateien (`ABOUT.md`, `TOPIC.md`, `TASKS.md`, `EXAM.md`, `SOLUTION.md`).
  Der Ordner `origin/` wird nicht gelesen.
- Alle Pfade sind relativ zu `dski-sources-3/`, mit `/` getrennt.
- Alle Texte sind deutsch.
- Hashes trägst du nicht ein; die rechnet das Import-Skript.

## Ausgabe

Genau eine JSON-Datei am vorgegebenen Pfad, mit diesem Aufbau:

```json
{
  "faecher": [
    {"slug": "<ordnername>", "name": "<lesbarer Name>", "about_pfad": "<fach>/ABOUT.md"}
  ],
  "themen": [
    {"schluessel": "...", "fach": "<slug>", "parent": null, "titel": "...", "reihenfolge": 1}
  ],
  "eintraege": [
    {"schluessel": "...", "thema": "<schluessel eines Themas>", "art": "lernpunkt",
     "titel": "...", "kurztext": "...", "quellpfad": "...", "anker": "...", "punkte": null}
  ]
}
```

Ein Thema muss in der Liste **nach** seinem `parent` stehen.

## Themen

- Für jeden Ordner `<fach>/topics/<thema>/`: ein Thema mit `schluessel` = dieser Pfad,
  `parent` = null, `titel` aus der Überschrift der dortigen `TOPIC.md`.
- Für jeden Unterordner `<fach>/topics/<thema>/<nn-unterthema>/`: ein Unterthema mit
  `schluessel` = dieser Pfad, `parent` = Schlüssel des Themas, `reihenfolge` = die Zahl `nn`.
- Aufgaben und Klausurfragen, die zu keinem Unterthema passen, kommen unter das Thema
  `<fach>/ohne-thema` (Titel „Ohne Themenzuordnung", `reihenfolge` 999) und dort in ein
  Unterthema je Quellordner, z. B. `<fach>/ohne-thema/task-1` (Titel „Aufgabenblatt 1") oder
  `<fach>/ohne-thema/exam-6-2025` (Titel „Klausur 2025"). Lege diese Themen nur an, wenn sie
  gebraucht werden.

## Einträge

Der `schluessel` ist immer `<quellpfad>#<anker>` und muss eindeutig sein.

### `art: "aufgabe"` — aus `origin-tasks/<task>/TASKS.md`

- Ein Eintrag je Teilaufgabe (z. B. 1, 2a, 2b). Eine Aufgabe ohne Teilaufgaben ist ein Eintrag.
- `anker`: die Nummer der Teilaufgabe, z. B. `1` oder `2a`.
- `titel`: „Blatt <n>, Aufgabe <nummer>: <worum es geht, höchstens 8 Wörter>".
- `kurztext`: der Anfang der Aufgabenstellung, wortgetreu, höchstens 300 Zeichen.
- `thema`: das Unterthema, dessen Stoff die Aufgabe prüft. Passt keines, siehe oben.

### `art: "klausurfrage"` — aus `origin-exams/<exam>/EXAM.md`

- Ein Eintrag je Teilaufgabe, `anker` z. B. `1a`.
- `titel`: „Klausur <jahr>, <nummer>: <worum es geht>".
- `kurztext`: die Frage wortgetreu, höchstens 300 Zeichen.
- `punkte`: die Punktzahl aus der Klausur.
- `thema` wie bei Aufgaben.

### `art: "lernpunkt"` — aus `topics/<thema>/<nn-unterthema>/TOPIC.md`

- Zerlege jedes Unterthema in 3 bis 8 prüfbare Lernpunkte. Ein Lernpunkt ist eine Fähigkeit,
  die sich in einer Klausur abfragen lässt („… erklären", „… berechnen", „… unterscheiden").
- Zusammen decken die Lernpunkte den ganzen Stoff des Unterthemas ab, ohne Überschneidung.
- `anker`: die Überschrift in der `TOPIC.md`, unter der der Stoff steht, plus eine laufende
  Nummer, falls mehrere Lernpunkte dieselbe Überschrift haben (z. B. `Motivation-2`).
- `titel`: die Fähigkeit in höchstens 12 Wörtern.
- `kurztext`: ein Satz, was genau gewusst oder gekonnt werden muss.
- `thema`: der Schlüssel des Unterthemas. `punkte`: null.

## `ABOUT.md`

Steht in der `ABOUT.md`, dass etwas nicht klausurrelevant ist, lässt du die Einträge trotzdem
drin und hängst an den `kurztext` den Hinweis „(laut ABOUT.md nicht klausurrelevant)" an.

## Zum Schluss

Prüfe selbst: gültiges JSON, jeder `thema`- und `parent`-Verweis existiert, jeder `quellpfad`
existiert, kein `schluessel` doppelt. Antworte mit einer Zeile je Art: wie viele Themen,
Aufgaben, Klausurfragen und Lernpunkte.
