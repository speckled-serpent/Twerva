# Twerva

*Pronunciation: TWER-vuh*

Bootstrap **distribution control plane** — middle node between product/brand content and social platforms.

```
source → generate → approve → publish → measure → steer
```

Not a social network. Not an ads bidder. Not an autoposter that only feeds empty personal accounts.

- **Phase 1–2:** Spotmu as customer zero (media content hose).
- **Phase 3:** Internal brands / internal projects (real PoC).
- **Phase 4 (optional):** External brands / spin-off — not required for “worth it.”

Sibling to Spotmu: **separate service and URL**, same Spotmu AWS account for billing until a real spin-off.

## Docs

| Doc | Role |
|---|---|
| [`docs/prompts/project.md`](docs/prompts/project.md) | Strategy, SWOT, roadmap |
| [`docs/prompts/product.md`](docs/prompts/product.md) | Product design, build vs buy |
| [`docs/planning/task_sheet.md`](docs/planning/task_sheet.md) | Build tasks |
| [`docs/overview.md`](docs/overview.md) | Spotmu handoff seed |
| [`docs/prompts/style_guide.md`](docs/prompts/style_guide.md) | Code style (from Spotmu) |
| [`docs/prompts/directory.md`](docs/prompts/directory.md) | Monorepo layout rules |
| [`.cursorrules`](.cursorrules) | Agent / Cursor discipline |

## Repo layout

```
apps/server    # FastAPI API (health + /api/v1 persist-proof)
apps/ops       # React / Vite / TypeScript ops console (stub)
packages/      # shared libraries
tools/         # scripts and deploy helpers
docs/          # project, product, planning, reports
```

See `docs/prompts/directory.md`.

## Status

- Domain: registered.
- Docs: strategy + product + task sheet in place.
- App host: EC2 `twerva-server` + `https://twerva.com` (stub).
- Stack (Phase 1): FastAPI + React/Vite/TypeScript + Postgres — Spotmu-aligned.
- App shells: `apps/server` and `apps/ops` run locally (task sheet §1.1). Domain schema + `/api/v1` persist-proof API and Spotmu seed are in (1.2). Ingest / generate / ops UI are not built yet.

## Stack (Phase 1)

- **Ops UI:** `apps/ops` — React, TypeScript, Vite
- **API:** `apps/server` — FastAPI, SQLAlchemy, PostgreSQL
- **Jobs (later):** Celery + Redis for render/publish/metrics

## Run locally

`GET /health` does not need Postgres. `/api/v1` and `python -m app.seed` do.

**API** (Python 3.11+):

```bash
cd apps/server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:application --reload --host 127.0.0.1 --port 8000
```

`GET http://127.0.0.1:8000/health` returns `{"status":"ok"}` without
`DATABASE_URL`. With a URL, `/api/v1` mounts and `python -m app.seed`
loads the Spotmu brand + example source item. Smoke:
`tools/smoke_1_2l_api.sh`. Details: [`apps/server/README.md`](apps/server/README.md).

**Ops console** (Node.js 20+):

```bash
cd apps/ops
npm install
npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). Details: [`apps/ops/README.md`](apps/ops/README.md).

## Development discipline

All generated code must follow `docs/prompts/style_guide.md` and `.cursorrules`. Prefer small, task-sheet-scoped changes.
