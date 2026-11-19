# Übungsblatt erzeugen

Du erzeugst ein Übungsblatt für das Lernsystem. Der Sitzungsordner steht im Auftrag am Ende
dieses Textes. Arbeite ohne Rückfragen.

## Regeln

- **Das Quell-Repo `dski-sources-3/` ist die einzige Wahrheit.** Jede Aufgabe muss sich allein
  mit dem beantworten lassen, was dort steht. Kein Wissen von außerhalb, keine eigenen
  Ergänzungen des Stoffs. Lies die Dateien jetzt frisch; verlasse dich nicht auf Kurztexte.
- **Im Ordner `dski-sources-3/` wird nichts geändert.** Du schreibst ausschließlich in den
  Sitzungsordner.
- Alle Texte sind deutsch, in der Fachsprache und Notation der Quelle.

## Eingabe

`<sitzung>/auftrag.json` enthält:

- `bereich`: das gewählte Fach oder Thema
- `fach`: der Fach-Ordner; lies `dski-sources-3/<fach>/ABOUT.md` vollständig. Sie beschreibt
  Klausurformat und Schwerpunkte und hat Vorrang (z. B. Anteil bestimmter Fragetypen, was
  nicht drankommt).
- `anzahl`: gewünschte Zahl der Aufgaben
- `eintraege`: alle aktiven Einträge des Bereichs, schwächste zuerst. Jeder hat `schluessel`,
  `art` (`aufgabe`, `klausurfrage`, `lernpunkt`), `quellpfad`, `anker`, `level` (0–5) und
  `status`.

## Auswahl

- Nimm bevorzugt Einträge mit niedrigem Level und solche mit `status: "geaendert"`.
- Mische die Arten so, wie es die `ABOUT.md` für die Klausur beschreibt. Steht dort nichts
  dazu, mische Lernpunkte, Aufgaben und Klausurfragen.
- Eine Aufgabe darf mehrere eng verwandte Einträge abdecken (höchstens drei). Jede Aufgabe
  nennt mindestens einen Eintrag.
- Lies zu jedem gewählten Eintrag die Quelldatei an der Stelle des Ankers.

## Schwierigkeit nach Level

| Level des Eintrags | Art der Aufgabe |
|---|---|
| 0–1 | Wiedergeben: nennen, erläutern, definieren. Bei `aufgabe` und `klausurfrage` die Originalfrage wortgetreu. |
| 2–3 | Anwenden: vergleichen, einordnen, an einem Fall aus der Quelle durchführen; bei Rechenaufgaben dieselbe Aufgabe mit geänderten Zahlen. |
| 4 | Klausurniveau: mehrere Lernpunkte verbinden, begründen, Fehler finden; Formulierung wie in den Altklausuren. |

## Format je Aufgabe

- `text`: Antwort in Sätzen oder Stichpunkten. Der Normalfall.
- `tabelle`: Antwort als Tabelle. Gib in `vorgabe` die Spalten und entweder `zeilenkoepfe`
  oder `zeilen` (Anzahl) an: `{"spalten": ["Soll", "Haben", "Betrag"], "zeilen": 4}`.
- `code`: Befehle, Dockerfile, SQL. `vorgabe`: `{"sprache": "dockerfile"}`.
- `pdf`: nur wenn gezeichnet werden muss (Diagramme, Skizzen) oder eine längere Rechnung
  handschriftlich sinnvoller ist. So selten wie möglich.

Der Aufgabentext ist Markdown (Listen, Tabellen, Codeblöcke, `**fett**`). Braucht eine Aufgabe
eine Abbildung aus dem Quell-Repo, trage sie unter `dateien` ein und binde sie mit
`![Beschreibung](bild-1.png)` ein.

Punkte: wie in den Altklausuren des Fachs, sonst 2 Punkte je erwartetem Kernpunkt.

## Ausgabe

### `<sitzung>/blatt.json`

```json
{
  "titel": "<Thema> – <kurzer Schwerpunkt>",
  "aufgaben": [
    {"nummer": 1, "format": "text", "punkte": 4,
     "text": "Erläutern Sie …",
     "vorgabe": null,
     "eintraege": ["<schluessel>", "<schluessel>"]}
  ],
  "dateien": [
    {"name": "bild-1.png", "quelle": "<pfad relativ zu dski-sources-3/>"}
  ]
}
```

`dateien` darf leer sein. Namen bestehen nur aus Buchstaben, Ziffern, `.`, `-` und `_`.

### `<sitzung>/.loesung/LOESUNG.md`

Je Aufgabe ein Abschnitt `## Aufgabe <n>` mit:

- der vollständigen Musterlösung, Schritt für Schritt
- einem Bewertungsschlüssel: wofür es welche Punkte gibt
- der Quelle: Dateipfad und Überschrift, aus der die Lösung stammt

### `<sitzung>/blatt.pdf` — nur wenn es `pdf`-Aufgaben gibt

Schreibe `<sitzung>/blatt.tex` (A4, deutsch, `\usepackage[utf8]{inputenc}`, `babel` mit
`ngerman`) mit **nur** den `pdf`-Aufgaben, jeweils mit Nummer, Text und viel freiem Platz zum
Schreiben (mindestens eine halbe Seite). Übersetze mit
`pdflatex -interaction=nonstopmode -output-directory <sitzung> <sitzung>/blatt.tex` und prüfe,
dass `blatt.pdf` entstanden ist.

## Gegenprüfung

Starte danach einen Subagent und gib ihm die Pfade von `blatt.json` und `LOESUNG.md`. Er prüft
jede Aufgabe gegen die Quelldateien:

1. Lässt sie sich allein mit dem Quell-Repo beantworten?
2. Ist die Musterlösung richtig und vollständig, stimmt der Quellverweis?
3. Ist die Aufgabe eindeutig formuliert, passen Punkte und Format?

Behebe jede Beanstandung und prüfe die geänderten Aufgaben erneut.

## Zum Schluss

Prüfe, dass `blatt.json` gültiges JSON ist, jede Aufgabe mindestens einen `schluessel` aus dem
Auftrag nennt und die Nummern fortlaufend sind. Antworte mit einer Zeile je Aufgabe: Nummer,
Format, Punkte, Thema.
