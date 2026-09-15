# Task 1.5 — Approval & schedule

*2026-09-15*

Phase 1.5 leaves **1.5a–1.5d** (serial). No real publish (1.6), no ops
UI (1.8), no Celery. `GET /health` still starts without `DATABASE_URL`.
Sync schedule create only.

## Done

- **1.5a** Review queue: `GET /api/v1/artifacts?status=draft`.
  `POST .../approve` (`approved` + `approved_at`; optional `{caption}`).
  `POST .../reject` (terminal). `PATCH` caption/`cta_url` while draft or
  approved. Reject reason is accepted and **ignored** (no column).
  Transitions reuse `ARTIFACT_STATUS_TRANSITIONS`; rejected cannot be
  re-approved (new Artifact).
- **1.5b** Cadence helper counts non-`failed` `post_jobs` on the **UTC**
  calendar day of `scheduled_for` vs `accounts.cadence_cap_per_day`
  (null = no cap). `POST /api/v1/schedule` returns **409** at/over cap.
- **1.5c** `POST /api/v1/schedule` `{artifact_id, account_id,
  scheduled_for}` creates `post_job` `scheduled` from an `approved`
  artifact. Brand match always; cluster match when Artifact
  `cluster_id` is set. README recipe + `tools/smoke_1_5_approve_schedule.sh`
  (seed/generate path; no Spotmu).
- **1.5d** This report. Leaves ticked. Badger: restart only; no new
  host deps / Alembic / nginx `/api`.

## Locked choices

| Topic | Choice |
|---|---|
| Cadence day | UTC calendar day of `scheduled_for` (naive = UTC) |
| Cap count | Non-`failed` jobs that day; `failed` does not consume a slot |
| Cap null | No limit |
| At/over cap | HTTP 409 |
| Reject reason | Accepted, not stored |
| Cluster coherence | Brand always; cluster iff Artifact `cluster_id` is set |
| Jobs | Sync in the API process (no Celery) |
| Public nginx | `/health` only |

## Trade-offs

- Existing `POST /api/v1/post-jobs` remains persist-proof and does **not**
  enforce approval or cadence (1.2l). The 1.5 gate is `POST /api/v1/schedule`.
- No Alembic revision (`12bk_domain_schema` stays head).
- Live SSH deploy / smoke on `twerva-server` is documented, not run
  here (same stance as 1.2l-iv / 1.3 / 1.4).

## Verified

- `python -m unittest discover -s tests` from `apps/server`: **87 tests OK**
  (7 skipped without Postgres — same stance as 1.2l/1.4 persist). Always-on
  coverage: draft→approved/rejected, rejected cannot re-approve, cadence
  under/at/over/null, UTC day bounds, brand/cluster coherence, route
  surface, schemas, `GET /health` without `DATABASE_URL`.
- `GET /health` via TestClient **without** `DATABASE_URL` →
  `200 {"status":"ok"}`; `/api/v1` not attached in that process.
- Live SSH deploy on `twerva-server` is documented, not run here.

## Out of scope (as specified)

- Real social publish (1.6)
- Ops React calendar UI (1.8)
- Celery beat
- Public nginx `/api`

## Scripts touched

- `apps/server/app/approval/` (`errors.py`, `service.py`)
- `apps/server/app/schedule/` (`cadence.py`, `service.py`, `errors.py`)
- `apps/server/app/api/v1/artifacts.py`, `schedule.py`, `router.py`,
  `schemas.py`
- `apps/server/tests/test_artifact_transitions.py`, `test_cadence.py`,
  `test_approve_schedule_persist.py`, plus route / schema tests
- `tools/smoke_1_5_approve_schedule.sh`
- `apps/server/README.md`, root `README.md`
- `docs/planning/domain_statuses.md`, `docs/planning/task_sheet.md`
- `docs/ops/deploy.md`, `docs/ops/README.md`
- this file

## Next

- Badger: sync `apps/server`, restart `twerva-api`, keep nginx `/health`
  only. Optional loopback `tools/smoke_1_5_approve_schedule.sh`.
- **1.6** mock PublishAdapter + buy-vs-build spike.
