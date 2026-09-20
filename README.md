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
| [`docs/ops/README.md`](docs/ops/README.md) | Production deploy / rollback (Badger) |
| [`docs/overview.md`](docs/overview.md) | Spotmu handoff seed |
| [`docs/prompts/style_guide.md`](docs/prompts/style_guide.md) | Code style (from Spotmu) |
| [`docs/prompts/directory.md`](docs/prompts/directory.md) | Monorepo layout rules |
| [`docs/agents/README.md`](docs/agents/README.md) | Agent hooks: draft, human gate, propose steer |
| [`docs/reports/phase_1_exit_report.md`](docs/reports/phase_1_exit_report.md) | Phase 1 close for Mu review |
| [`.cursorrules`](.cursorrules) | Agent / Cursor discipline |

## Repo layout

```
apps/server    # FastAPI API (health + /api/v1 persist-proof)
apps/ops       # React / Vite / TypeScript ops console (thin loop UI)
packages/      # shared libraries
tools/         # scripts and deploy helpers
docs/          # project, product, planning, ops, reports
```

See `docs/prompts/directory.md`.

## Status

- Domain: registered.
- Docs: strategy + product + task sheet in place.
- App host: EC2 `twerva-server` + `https://twerva.com` (ops console + cookie auth).
- Stack (Phase 1): FastAPI + React/Vite/TypeScript + Postgres — Spotmu-aligned.
- App shells: `apps/server` and `apps/ops` run locally (task sheet §1.1). Domain schema + `/api/v1` persist-proof API and Spotmu seed are in (1.2). **1.3 Spotmu ingest** (public JSON + sitemap, manual cluster attach) is in. **1.4 carousel generate** (local PNG store, draft Artifact) is in. **1.5 approval & schedule** (review queue, cadence caps, `POST /api/v1/schedule`) is in. **1.6 mock publish** (`POST /api/v1/publish/run/{post_job_id}`, `PUBLISH_ADAPTER=mock`) is in. **1.7 measure & steer** (metric snapshots, cluster median, steer, agent-summary) is in. **1.8 thin ops console** (`apps/ops`: Sources · Queue · Schedule · Accounts · Results against local `/api/v1`). **1.9 agent hooks** (docs + batch-generate dry-run; human gate). Phase 1 sheet closed pending Mu review — **do not start Phase 2**.

## Stack (Phase 1)

- **Ops UI:** `apps/ops` — React, TypeScript, Vite
- **API:** `apps/server` — FastAPI, SQLAlchemy, PostgreSQL
- **Jobs (later):** Celery + Redis for render/publish/metrics

## Run locally

`GET /health` does not need Postgres. `/api/v1` and `python -m app.seed` do.
`/api/v1` (except `/auth/login` / `/logout` / `/me`) needs a session cookie.

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
loads the Spotmu brand + example source item. Real ingest:
`python -m app.ingest.spotmu_interest ai-agents` or
`tools/smoke_1_3_ingest.sh`. Carousel generate (DB source, no Spotmu):
`python -m app.generate.carousel_cli <source_item_id>` or
`tools/smoke_1_4_carousel.sh`. Approve + schedule (offline seed/generate):
`tools/smoke_1_5_approve_schedule.sh`. Mock publish (offline approve/schedule):
`tools/smoke_1_6_publish.sh`. Measure & steer (metrics → median → steer):
`tools/smoke_1_7_measure_steer.sh`. Agent dry-run (drafts, stop before
approve): `tools/agent_batch_generate.sh` —
[`docs/agents/README.md`](docs/agents/README.md). Details:
[`apps/server/README.md`](apps/server/README.md).

**Ops console** (Node.js 20+):

```bash
cd apps/ops
npm install
npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). Vite proxies `/api` and
`/health` to the API on `:8000` (or set `VITE_API_BASE_URL`). Walk
Sources → Queue → Schedule → Accounts → Results against the local API.
Details: [`apps/ops/README.md`](apps/ops/README.md).

## Development discipline

All generated code must follow `docs/prompts/style_guide.md` and `.cursorrules`. Prefer small, task-sheet-scoped changes.
