# Task 1.7 — Measure & steer

*2026-09-15*

Phase 1.7 leaves **1.7a–1.7d** (serial). No Celery/Redis, no ops UI
(1.8), no real analytics vendor. `GET /health` still starts without
`DATABASE_URL`. Reuses `MetricSnapshot` + `SteerAction` (no new
Alembic revision).

## Done

- **1.7a** `POST /api/v1/post-jobs/{id}/metrics` appends a
  `metric_snapshots` row (views/likes/comments/shares, optional
  `captured_at` / `raw`). Latest-wins is unchanged. `published` /
  `failed` jobs move to `measured`. Stub:
  `POST /api/v1/post-jobs/{id}/metrics/stub` copies documented mock
  counts (`views=100`, `likes=10`, `comments=2`, `shares=1`) only when
  `platform_post_id` starts with `mock-` (409 otherwise).
- **1.7b** `GET /api/v1/clusters/{id}/metrics/summary` — median of
  latest-wins views across jobs that have a non-null views snapshot.
  Empty → `median_views: null` (not zero). Unit tests for the helper.
- **1.7c** `POST /api/v1/clusters/{id}/steer` `{action, reason?}`.
  Pause/kill set `clusters.is_active=false`; resume sets true;
  double_down is **log-only**. Account statuses are not flipped.
  Tests for those side effects.
- **1.7d** `GET /api/v1/clusters/{id}/agent-summary` JSON (default) or
  `?format=markdown`. This report. Leaves ticked.
  `tools/smoke_1_7_measure_steer.sh`.

## Locked choices

| Topic | Choice |
|---|---|
| Snapshot grain | Existing `metric_snapshots`; latest-wins by `captured_at` |
| Empty median | JSON `null`, not `0` |
| Even-length median | Mean of the two central values (may be a half) |
| Stub | Mock `platform_post_id` prefix only; documented constants |
| Pause/kill | Cluster `is_active=false` (accounts unchanged) |
| Resume | Cluster `is_active=true` |
| Double-down | Log-only (no cadence / generate bump) |
| Jobs | Sync in the API process (no Celery) |
| Public nginx | `/health` only |
| Schema | `12bk_domain_schema` stays head |

## Trade-offs

- No vendor insights API. Operators POST numbers (or the mock stub)
  until a later analytics adapter exists.
- Double-down does not raise `cadence_cap_per_day` or enqueue extra
  generates. The steer row is the record for agents/humans.
- Kill and pause share the same flag; the action string is the
  distinction in `steer_actions`.
- Snapshots can be stored on `scheduled` jobs without jumping to
  `measured` (that transition is not on the graph).

## Verified

- `python -m unittest discover -s tests` from `apps/server`: **131 tests
  OK** (none skipped against local Postgres 16). Always-on coverage:
  median helper (empty / odd / even / half), steer
  pause/kill/resume/double_down flags, stub mock-only, `published` /
  `failed` → `measured`, scheduled keeps status, route surface,
  schemas, `GET /health` without `DATABASE_URL`. Persist: latest-wins
  median 10/20/30 → 20; pause/kill/resume/double_down flags; stub 100
  views + JSON/markdown agent-summary.
- Smoke: `tools/smoke_1_7_measure_steer.sh` against loopback uvicorn —
  seed/generate/approve/schedule/mock publish ×3, metrics 10/20/30
  (median **20.0**), stub latest-wins median **30.0**, pause →
  `is_active=false`, double_down stays false, resume true. Cluster
  `ddf9bbd5-29bc-4e5e-a57c-b28abafec58a`. Jobs
  `5c904d5c-7e1d-4739-87ad-0a56cde8d87c`,
  `11549b90-2738-4efd-89a5-839554e08014`,
  `f6f5c3b0-fff6-415d-b14c-fe6b95f5d974`. Empty cluster summary
  `median_views: null`.
- `GET /health` via TestClient **without** `DATABASE_URL` →
  `200 {"status":"ok"}`; `/api/v1` not attached in that process.
- Live SSH deploy on `twerva-server` is documented, not run here
  (same stance as 1.2l-iv / 1.3–1.6).

## Out of scope (as specified)

- Celery/Redis
- Ops React (1.8)
- Real analytics vendor / platform insights pull
- Public nginx `/api`
- Cadence bump on double_down

## Scripts touched

- `apps/server/app/metrics/` (`median.py`, `service.py`, `stub.py`,
  `errors.py`)
- `apps/server/app/steer/` (`service.py`, `summary.py`)
- `apps/server/app/api/v1/metrics.py`, `steer.py`, `schemas.py`,
  `router.py`
- `apps/server/tests/test_median.py`, `test_steer.py`,
  `test_measure_persist.py`, plus route / schema tests
- `tools/smoke_1_7_measure_steer.sh`
- `apps/server/README.md`, root `README.md`
- `docs/planning/domain_statuses.md`, `docs/planning/task_sheet.md`,
  `docs/prompts/product.md`
- `docs/ops/deploy.md`, `docs/ops/README.md`
- this file

## Next

- Badger: sync `apps/server`, restart `twerva-api`, keep nginx
  `/health` only. Optional loopback `tools/smoke_1_7_measure_steer.sh`.
- **1.8** thin ops console against these routes.
