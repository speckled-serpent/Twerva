# Task 1.1 (partial) — Empty app shells

*2026-09-14*

## Done

- `apps/server`: FastAPI process with `GET /health` → `{"status":"ok"}`. `pyproject.toml` + `requirements.txt`, `app/main.py`, local README.
- `apps/ops`: Vite + React + TypeScript stub page (“Twerva ops console stub”). `package.json`, tsconfigs, `vite.config.ts`, local README.
- Root `README.md`: run steps for server + ops; layout/status updated. Strategy/docs table left intact.
- Removed `apps/.gitkeep` now that real apps exist. `packages/` and `tools/` placeholders unchanged.
- Task sheet §1.1 shells checkbox marked done.

## Trade-offs

- No SQLAlchemy, Postgres, Celery, Docker, or AWS deploy — shells only.
- No CORS, auth, or ops→API wiring. FastAPI `/docs` is the stock default.
- Python install path is `pip install -r requirements.txt` (Spotmu-familiar); `pyproject.toml` is there for the same pins and `pip install -e .`.
- Ops UI is utilitarian CSS, no Tailwind yet.

## Scripts touched

- `apps/server/app/main.py` — health route
- `apps/ops/src/App.tsx`, `apps/ops/src/main.tsx` — stub console
- `apps/server/README.md`, `apps/ops/README.md`, root `README.md`

## Next

- Healthcheck on the live Twerva URL (remaining §1.1)
- Domain model (task 1.2) when ready — do not invent ingest/carousel here
