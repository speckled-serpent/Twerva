# Twerva server

FastAPI process for the Twerva API. `GET /health` is a liveness check and does
**not** open a database connection. Domain models start in task 1.2b+.

Requires **Python 3.11+**.

## Run locally

From this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:application --reload --host 127.0.0.1 --port 8000
```

Alternatively, install from `pyproject.toml` with `pip install -e .` instead of `pip install -r requirements.txt`.

Check the process:

```bash
curl http://127.0.0.1:8000/health
```

Expected JSON:

```json
{"status":"ok"}
```

Interactive docs (FastAPI default): [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

`GET /health` works without `DATABASE_URL`. Settings, `app.db`, and Alembic
commands that talk to Postgres require the URL below.

## Database URL

The process reads `DATABASE_URL` from the environment (or a local `.env` in
this directory). Bare `postgresql://` / `postgres://` URLs are rewritten to
the psycopg3 dialect `postgresql+psycopg://`.

Outside tests, a missing or blank `DATABASE_URL` raises at settings load
(`MissingDatabaseUrlError`). Tests may set `TWERVA_ENV=test` or
`TWERVA_TESTING=1` to use a placeholder URL.

### Local override

```bash
cp .env.example .env
# edit .env, or export instead:
export DATABASE_URL=postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva
```

`.env` is gitignored. Do not commit credentials.

### Production (`twerva-server`)

On-box file: `/opt/twerva/database_url.env` (mode 600). It provides
`DATABASE_URL` for Docker Postgres bound to `127.0.0.1:5432`. Load it into
the process environment (systemd `EnvironmentFile=` or `source` in a shell).
The app does not open that file itself.

## Alembic

Run from this directory so `alembic.ini` and `app.settings` resolve. The
revision chain is empty in 1.2a (ready for 1.2b+).

```bash
alembic heads
alembic history
```

### Smoke (`1.2a-v`) — connect with the on-box env file

SSH to `twerva-server` is optional if you already have a shell there. From
`apps/server` on that box:

```bash
set -a
source /opt/twerva/database_url.env
set +a
alembic current
```

`alembic current` opens Postgres on `127.0.0.1:5432` using `DATABASE_URL`.
With an empty revision chain it should connect and report no current
revision (or `(empty)`), not a connection error.

Local equivalent (your own `DATABASE_URL`):

```bash
export DATABASE_URL=postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva
alembic current
```
