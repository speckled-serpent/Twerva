# Task 1.9 — Agent hooks

*2026-09-15*

Phase 1.9 leaves **1.9a–1.9b** (serial). Docs + a thin localhost
script. **No new product features.** No Phase 2.

## Done

- **1.9a-i** [`docs/agents/README.md`](../agents/README.md) — agents
  draft via `POST /api/v1/generate/carousel`; humans approve on Queue /
  `POST .../approve`; agents **propose** steer from
  `GET /api/v1/clusters/{id}/agent-summary` and must not
  `POST .../steer` until a human ratifies (that route applies flags).
  Tables for `/api/v1` routes and ops pages (Sources · Queue ·
  Schedule · Accounts · Results).
- **1.9a-ii** [`docs/agents/playbook_batch_generate_spotmu_cluster.md`](../agents/playbook_batch_generate_spotmu_cluster.md)
  — dry-run: existing cluster sources, or ingest when Spotmu is up
  (fallback to seed `example` on 502/503) → generate carousels for
  cluster X (`spotmu-general`) → **stop before approve** → optional
  agent-summary.
- **1.9a-iii** [`tools/agent_batch_generate.sh`](../../tools/agent_batch_generate.sh)
  implements that dry-run against `TWERVA_API_BASE_URL` (default
  loopback). Never calls approve / schedule / publish / steer.
- **1.9b-i** This report. Leaves were ticked on the task sheet, later replaced by `docs/planning/phase_map.md`.
- **1.9b-ii** [`phase_1_exit_report.md`](phase_1_exit_report.md) for Mu
  morning review. **Phase 2 not started.**

## Locked choices

| Topic | Choice |
|---|---|
| New API / UI | None |
| Human gate | Agents stop at draft; approve is human |
| Steer | Propose from summary; POST applies |
| Cluster recipe | Brand `spotmu` / `slug=spotmu-general` |
| Offline fallback | Seed SourceItem `external_key=example` |
| Public nginx | `/health` only (unchanged) |

## Trade-offs

- Ingest stays API/CLI; ops Sources has no ingest form (1.8 lock).
- The helper creates the `spotmu-general` cluster if missing and may
  attach the fake seed row when Spotmu ingest fails. That keeps the
  dry-run runnable overnight; it is not a live interest.
- `POST .../steer` is documented as apply-not-propose so agents do not
  flip `is_active` by accident.

## Verified

- Docs match merged main at `a8e4a86` (1.8): generate 201 draft,
  approve/schedule/publish/metrics/steer/agent-summary paths as in
  `apps/server/app/api/v1/`.
- Spotmu public re-check this slice (from this environment, not via
  Twerva ingest): `GET https://spotmu.com/api/v1/interests/slug/ai-agents`
  HTTP **200**; `GET https://spotmu.com/sitemap.xml` HTTP **200**;
  `GET https://twerva.com/health` HTTP **200**. Full
  `tools/smoke_1_3_ingest.sh` still needs a migrated local/on-box API
  (this environment has no Postgres).
- Script is executable; it was not run end-to-end here (no
  `DATABASE_URL` / uvicorn `/api/v1`). Syntax: `bash -n
  tools/agent_batch_generate.sh`.

## Out of scope (as specified)

- Product features, Celery, S3, auth, public `/api`
- Phase 2 tasks (bulk ingest, live vendor publish, weekly agent steer)

## Scripts / files touched

- `docs/agents/README.md`
- `docs/agents/playbook_batch_generate_spotmu_cluster.md`
- `tools/agent_batch_generate.sh`
- `docs/reports/task_1_9_report.md`, `docs/reports/phase_1_exit_report.md`
- task sheet, 1.9 leaves + next-slice note (sheet later replaced by `docs/planning/phase_map.md`)
- `README.md`, `apps/server/README.md`, `docs/ops/README.md`,
  `docs/prompts/directory.md`, `docs/prompts/product.md` (pointers)

## Next

- Mu: read `phase_1_exit_report.md`. **Do not start Phase 2** until
  that review.
- Badger: no nginx change, no new host deps. Optional later: loopback
  `tools/agent_batch_generate.sh` after API deploy.
