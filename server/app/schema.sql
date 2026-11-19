CREATE TABLE IF NOT EXISTS faecher (
    id INTEGER PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    about_pfad TEXT,
    about_hash TEXT
);

CREATE TABLE IF NOT EXISTS themen (
    id INTEGER PRIMARY KEY,
    fach_id INTEGER NOT NULL REFERENCES faecher(id),
    parent_id INTEGER REFERENCES themen(id),
    schluessel TEXT NOT NULL UNIQUE,
    titel TEXT NOT NULL,
    reihenfolge INTEGER NOT NULL DEFAULT 0,
    aktiv INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS eintraege (
    id INTEGER PRIMARY KEY,
    schluessel TEXT NOT NULL UNIQUE,
    thema_id INTEGER NOT NULL REFERENCES themen(id),
    art TEXT NOT NULL CHECK (art IN ('aufgabe', 'klausurfrage', 'lernpunkt')),
    titel TEXT NOT NULL,
    kurztext TEXT NOT NULL DEFAULT '',
    quellpfad TEXT NOT NULL,
    anker TEXT NOT NULL DEFAULT '',
    quell_hash TEXT NOT NULL,
    punkte REAL,
    aktiv INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'aktuell' CHECK (status IN ('aktuell', 'geaendert', 'archiviert')),
    level INTEGER NOT NULL DEFAULT 0 CHECK (level BETWEEN 0 AND 5),
    claude_wert INTEGER,
    user_wert INTEGER,
    bewertet_am TEXT
);

CREATE TABLE IF NOT EXISTS blaetter (
    id INTEGER PRIMARY KEY,
    titel TEXT NOT NULL,
    thema_id INTEGER REFERENCES themen(id),
    fach_id INTEGER REFERENCES faecher(id),
    status TEXT NOT NULL DEFAULT 'offen' CHECK (status IN ('offen', 'abgegeben', 'korrigiert')),
    quell_commit TEXT,
    erstellt_am TEXT NOT NULL DEFAULT (datetime('now')),
    abgegeben_am TEXT,
    korrigiert_am TEXT
);

CREATE TABLE IF NOT EXISTS blatt_aufgaben (
    id INTEGER PRIMARY KEY,
    blatt_id INTEGER NOT NULL REFERENCES blaetter(id) ON DELETE CASCADE,
    nummer INTEGER NOT NULL,
    format TEXT NOT NULL CHECK (format IN ('text', 'tabelle', 'code', 'pdf')),
    text TEXT NOT NULL,
    punkte REAL NOT NULL DEFAULT 0,
    vorgabe TEXT,
    antwort TEXT,
    user_wert INTEGER,
    erreichte_punkte REAL,
    claude_wert INTEGER,
    feedback TEXT,
    musterloesung TEXT,
    quellverweis TEXT
);

CREATE TABLE IF NOT EXISTS blatt_aufgabe_eintraege (
    aufgabe_id INTEGER NOT NULL REFERENCES blatt_aufgaben(id) ON DELETE CASCADE,
    eintrag_id INTEGER NOT NULL REFERENCES eintraege(id),
    PRIMARY KEY (aufgabe_id, eintrag_id)
);

CREATE TABLE IF NOT EXISTS dateien (
    id INTEGER PRIMARY KEY,
    blatt_id INTEGER NOT NULL REFERENCES blaetter(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    mime TEXT NOT NULL,
    inhalt BLOB NOT NULL,
    UNIQUE (blatt_id, name)
);

CREATE TABLE IF NOT EXISTS bewertungen (
    id INTEGER PRIMARY KEY,
    eintrag_id INTEGER NOT NULL REFERENCES eintraege(id),
    blatt_id INTEGER REFERENCES blaetter(id),
    claude_wert INTEGER NOT NULL,
    user_wert INTEGER NOT NULL,
    level_vorher INTEGER NOT NULL,
    level_nachher INTEGER NOT NULL,
    am TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS updates (
    id INTEGER PRIMARY KEY,
    commit_von TEXT,
    commit_bis TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'laeuft' CHECK (status IN ('laeuft', 'fertig', 'fehler')),
    zusammenfassung TEXT,
    protokoll TEXT,
    am TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS meta (
    schluessel TEXT PRIMARY KEY,
    wert TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_eintraege_thema ON eintraege(thema_id);
CREATE INDEX IF NOT EXISTS idx_themen_fach ON themen(fach_id);
