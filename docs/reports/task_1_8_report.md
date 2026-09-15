# Task 1.8 — Ops console (thin)

*2026-09-15*

Phase 1.8 leaves **1.8a–1.8c** (serial). No auth, no design system, no
public nginx change. `apps/ops` drives the existing `/api/v1` loop
against a local API.

## Done

- **1.8a** Vite proxies `/api` and `/health` to
  `http://127.0.0.1:8000`. Optional `VITE_API_BASE_URL` (documented;
  proxy is the local default). Nav: Sources · Queue · Schedule ·
  Accounts · Results. No react-router (page state in `App`).
- **1.8b** Pages fetch real routes: source list/create +
  `POST /api/v1/generate/carousel`; draft queue approve/reject/PATCH
  caption; schedule + post-job list + mock
  `POST /api/v1/publish/run/{id}`; cluster/account list, cadence cap,
  steer; cluster metrics summary + markdown agent-summary + stub
  metrics. Errors show as plain text. Selects for ids when list
  endpoints exist.
- **1.8c** `apps/ops/README.md` walks API + `npm run dev` + the loop.
  Static `dist/` noted for later private nginx — **not** required
  tonight. This report. Leaves ticked.

## Locked choices

| Topic | Choice |
|---|---|
| Router | None; five-page nav state |
| API origin | Empty base URL → relative `/api` via Vite proxy |
| Override | `VITE_API_BASE_URL` stripped of trailing slash |
| Auth | None |
| Public nginx | Unchanged (`/health` only) |
| Design | Plain CSS |
| Cluster/account create | Thin forms so seed-only DBs can still walk schedule |

## Trade-offs

- No ingest UI on Sources (list + create + generate is enough; ingest
  stays CLI / `/docs`).
- Steer lives on Accounts (task 1.8b-iv); Results is median + summary
  + stub metrics so the measure step is visible without leaving the
  console.
- `vite preview` does not include the dev proxy; set
  `VITE_API_BASE_URL` at build time if preview needs the API.

## Verified

- `npm run build` from `apps/ops`: `tsc -b` + Vite production `dist/`
  succeeded.

## Out of scope (as specified)

- Auth
- Pretty design / mobile polish
- Public ops deploy / nginx locations on twerva.com
- Celery, S3, vendor publish keys

## Scripts / files touched

- `apps/ops/vite.config.ts`, `.env.example`, `README.md`
- `apps/ops/src/api/`, `apps/ops/src/pages/`, `apps/ops/src/components/`
- `apps/ops/src/App.tsx`, `apps/ops/src/index.css`, `apps/ops/src/vite-env.d.ts`
- `README.md`, `docs/planning/task_sheet.md`, `docs/ops/README.md`,
  `docs/ops/deploy.md` (ops UI stays off public nginx)
- this file

## Next

- **1.9** agent docs + batch-generate playbook + Phase 1 exit report.
  Stop after that. Do not start Phase 2.
- Badger: no nginx change. Optional later: private static `dist/` host.
