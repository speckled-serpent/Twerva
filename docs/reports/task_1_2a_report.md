# Task 1.2a (leaves i–iv) — DB plumbing

*2026-09-15*

## Done

- **1.2a-i** Pinned `sqlalchemy`, `psycopg[binary]` (psycopg3), `alembic`, and
  `pydantic-settings` in both `apps/server/requirements.txt` and
  `apps/server/pyproject.toml`, same range style as FastAPI/uvicorn.
- **1.2a-ii** `app/settings.py` reads `DATABASE_URL` (env or local `.env`).
  Missing/blank URL raises `MissingDatabaseUrlError` outside tests. Test
  escape hatch: `TWERVA_ENV=test` / `TWERVA_TESTING=1` / `PYTEST_CURRENT_TEST`.
  Bare `postgresql://` and `postgres://` URLs are rewritten to
  `postgresql+psycopg://`. Local override documented in `apps/server/README.md`
  and `.env.example`.
- **1.2a-iii** `app/db.py`: `our_database_engine` / `engine`, `SessionLocal`,
  `get_our_database_session()` for FastAPI `Depends`. Empty models package
  (`app/models`, declarative `Base` only).
- **1.2a-iv** Alembic under `apps/server` (`alembic.ini`, `alembic/env.py`
  uses the same settings/`DATABASE_URL`). `alembic/versions/` is empty —
  ready for 1.2b+.
- **1.2a-v** Not executed against live EC2 Postgres. README documents
  `alembic current` with `/opt/twerva/database_url.env` and a local
  `DATABASE_URL` equivalent.

`GET /health` is unchanged and does not import settings or the engine.

Task sheet checkboxes left unchecked (this PR implements 1.2a-i…iv; 1.2a-v
is README-only).

## Trade-offs

- Engine is created at `app.db` import time (standard FastAPI). Health does
  not import `app.db`, so liveness still works without a URL.
- No live `alembic current` against `twerva-server` in this slice (1.2a-v).
- No Celery/Redis/S3/auth, no domain tables.

## Scripts touched

- `apps/server/requirements.txt`, `apps/server/pyproject.toml`
- `apps/server/app/settings.py`, `apps/server/app/db.py`
- `apps/server/app/models/__init__.py`, `apps/server/app/models/base.py`
- `apps/server/alembic.ini`, `apps/server/alembic/env.py`,
  `apps/server/alembic/script.py.mako`, `apps/server/alembic/versions/.gitkeep`
- `apps/server/README.md`, `apps/server/.env.example`
- `apps/server/tests/test_health.py`, `test_settings.py`, `test_db.py`

## Next

- 1.2a-v: run `alembic current` on `twerva-server` with the on-box env file
- 1.2b+: enums, domain models, first Alembic revision
