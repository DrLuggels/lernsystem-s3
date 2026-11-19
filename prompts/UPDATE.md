# Quell-Update einarbeiten

Das Quell-Repo `dski-sources-3/` hat neue Commits. Du gleichst die Einträge des Lernsystems mit
dem neuen Stand ab. Der Sitzungsordner steht im Auftrag am Ende dieses Textes. Arbeite ohne
Rückfragen.

## Regeln

- **Das Quell-Repo ist die Wahrheit.** Was dort jetzt steht, gilt; die Datenbank folgt.
- Im Ordner `dski-sources-3/` wird nichts geändert. Du schreibst nur `<sitzung>/update.json`.
- Lies zuerst `prompts/EXTRAKTION.md`: Für neue Themen und Einträge gelten genau dieselben
  Regeln (Schlüssel, Anker, Titel, Kurztext, Zuordnung).
- Der Ordner `origin/` wird nicht gelesen.

## Eingabe

- `<sitzung>/dateien.txt`: geänderte Dateien (`git diff --name-status`): `A` neu, `M`
  geändert, `D` gelöscht, `R` umbenannt.
- `<sitzung>/diff.patch`: der Diff aller geänderten Markdown-Dateien.
- `<sitzung>/eintraege.json`: alle vorhandenen Einträge der betroffenen Fächer mit
  `schluessel`, `art`, `titel`, `kurztext`, `quellpfad`, `anker`, `thema`, `level`.

Lies den Diff und zu jeder geänderten Markdown-Datei den neuen Stand der Datei.

## Entscheidung je betroffenem Eintrag

Betroffen ist ein Eintrag, wenn sich seine Quelldatei an der Stelle seines Ankers geändert hat
oder die Datei gelöscht oder umbenannt wurde.

| Fall | Was du tust |
|---|---|
| Tippfehler, Formatierung, Umformulierung ohne neuen Inhalt | Eintrag mit aktualisiertem Titel/Kurztext unter `daten.eintraege`. Level bleibt. |
| Inhalt stark geändert: andere Aussage, andere Zahlen, andere Formel, Stoff deutlich erweitert oder gekürzt | Eintrag mit neuem Titel/Kurztext unter `daten.eintraege` **und** Schlüssel unter `stark_geaendert`. Level fällt eine Stufe. |
| Stelle oder Datei gibt es nicht mehr | Schlüssel unter `archiviert`. |
| Datei umbenannt oder verschoben, Inhalt gleich | alten Schlüssel unter `archiviert`, neuen Eintrag unter `daten.eintraege`. Vermerke das im Protokoll, weil der Lernstand dabei neu beginnt. |
| Neuer Stoff, neue Aufgabe, neue Klausur | neue Einträge (und nötige Themen) unter `daten`. |
| Änderung betrifft den Eintrag nicht | nichts. |

Im Zweifel zwischen „klein" und „stark": Müsste jemand, der die alte Fassung sicher konnte,
etwas neu lernen? Dann ist es stark.

Ändert sich eine `ABOUT.md`, prüfe, ob Einträge dadurch klausurrelevant oder nicht mehr
klausurrelevant werden, und passe den Hinweis im `kurztext` an (kleine Änderung). Bei einem
neuen Fach trägst du es unter `daten.faecher` ein.

## Ausgabe: `<sitzung>/update.json`

```json
{
  "zusammenfassung": "Zwei bis vier Sätze: was sich im Quell-Repo geändert hat und was das für den Lernstand heißt.",
  "protokoll": "Eine Zeile je Entscheidung: <schluessel> — klein | stark | archiviert | neu — Begründung",
  "daten": {
    "faecher": [],
    "themen": [],
    "eintraege": []
  },
  "stark_geaendert": ["<schluessel>"],
  "archiviert": ["<schluessel>"]
}
```

`daten` hat denselben Aufbau wie die Extraktion (ohne Hashes). Ein Thema steht nach seinem
`parent`; vorhandene Themen musst du nicht wiederholen. Kein Schlüssel steht zugleich unter
`stark_geaendert` und `archiviert`.

## Zum Schluss

Prüfe: gültiges JSON; jeder Schlüssel unter `stark_geaendert` und `archiviert` existiert in
`eintraege.json`; jeder `quellpfad` existiert im Quell-Repo; jede geänderte Markdown-Datei aus
`dateien.txt` kommt im Protokoll vor (auch mit „keine Auswirkung"). Antworte mit der
Zusammenfassung.
