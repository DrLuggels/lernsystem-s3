# Lernsystem S3

Lernsystem für die Klausuren des 3. Semesters. Der Stoff kommt aus einem getrennten
Quell-Repo; dieses Repo enthält nur den Code.

- `server/` — API, Datenbank und Frontend (FastAPI + SQLite)
- `docs/superpowers/specs/` — Design

## Lokal starten

    cp .env.example .env      # Werte setzen, LERN_COOKIE_SECURE=0
    docker compose up -d --build
    curl localhost:8099/api/gesund

## Tests

    cd server
    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
    .venv/bin/pytest -q
