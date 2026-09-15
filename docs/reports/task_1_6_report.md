# Task 1.6 — Publish adapter

*2026-09-15*

Phase 1.6 leaves **1.6a–1.6d** (serial). No live OAuth/vendor signup, no
ops UI (1.8), no Celery/Redis. `GET /health` still starts without
`DATABASE_URL`. Sync publish only.

## Done

- **1.6a** Spike:
  [`task_1_6_publish_spike.md`](task_1_6_publish_spike.md). Lock:
  adapter interface now; **mock default**; first live vendor **Ayrshare**
  behind `PUBLISH_ADAPTER` / `AYRSHARE_API_KEY` when keys exist. Zernio
  is the swap candidate. Postiz self-host and native Meta/TikTok stay
  parked.
- **1.6b** `PublishAdapter.publish(post_job, artifact, account,
  media_paths) -> PublishResult`. `MockPublishAdapter` always succeeds
  with `mock-{platform}-{post_job.id}` and logs `media_path_count`.
  Settings: `PUBLISH_ADAPTER=mock|ayrshare` (default mock). Ayrshare
  stub constructs when a key is present but **does not send HTTP**.
- **1.6c** `POST /api/v1/publish/run/{post_job_id}`: `scheduled` (or
  `failed` retry) → in-memory `publishing` → commit `published` +
  platform fields + `published_at`, or `failed` + `last_error`. Slide
  `asset_ref` files resolved from `ARTIFACT_STORAGE_DIR`. Tests +
  `tools/smoke_1_6_publish.sh` (approve/schedule/mock publish; no
  Spotmu).
- **1.6d** This report. Leaves ticked. Live vendor is a follow-up when
  Mu adds keys.

## Locked choices

| Topic | Choice |
|---|---|
| Default adapter | `mock` (CI-safe, no keys) |
| First live vendor | Ayrshare (not wired in 1.6) |
| Fake ids | `mock-{platform}-{post_job.id}` / `https://example.invalid/...` |
| Retry | Same endpoint on `failed` (no Redis, no backoff sleep) |
| Crash during adapter | Previous committed status (usually `scheduled`) |
| Jobs | Sync in the API process (no Celery) |
| Public nginx | `/health` only |
| Tokens on `accounts` | Still not stored |

## Trade-offs

- Live Ayrshare needs publicly fetchable media URLs. Phase 1.4 files
  live on local disk (not public nginx). Hosting/upload is part of the
  vendor follow-up, not this slice.
- `publishing` is not committed mid-request. Operators see
  `scheduled` → `published`/`failed` after the call returns.
- Existing `POST /api/v1/post-jobs` remains persist-proof and does not
  go through the adapter.
- No Alembic revision (`12bk_domain_schema` stays head).

## Verified

- `python -m unittest discover -s tests` from `apps/server`: **108 tests
  OK** (none skipped against local Postgres 16). Always-on coverage:
  mock fake ids + media log, factory mock/ayrshare/unknown, media
  resolve + path escape, scheduled→published, adapter failure→failed,
  failed retry, missing media→failed, route surface, `PUBLISH_ADAPTER`
  default, `GET /health` without `DATABASE_URL`. Persist: generate →
  approve → schedule → mock publish records `mock-instagram-…` ids;
  republish is 409.
- Smoke: `tools/smoke_1_6_publish.sh` against loopback uvicorn —
  seed/generate/approve/schedule/mock publish. Job
  `64057014-812a-46a4-a7c4-95f201cdb800` became `published` with
  `platform_post_id=mock-instagram-64057014-812a-46a4-a7c4-95f201cdb800`.
  Second run HTTP 409.
- `GET /health` via TestClient **without** `DATABASE_URL` →
  `200 {"status":"ok"}`; `/api/v1` not attached in that process.
- Live SSH deploy on `twerva-server` is documented, not run here
  (same stance as 1.2l-iv / 1.3 / 1.4 / 1.5).

## Out of scope (as specified)

- Real OAuth / vendor signup / connecting live IG+TikTok accounts
- Celery/Redis
- Ops React (1.8)
- Public nginx `/api`
- Storing refresh tokens on `accounts`

## Scripts touched

- `docs/reports/task_1_6_publish_spike.md`
- `apps/server/app/publish/` (`adapter.py`, `mock.py`, `ayrshare.py`,
  `factory.py`, `media.py`, `service.py`, `errors.py`)
- `apps/server/app/api/v1/publish.py`, `router.py`
- `apps/server/app/settings.py`, `.env.example`
- `apps/server/tests/test_publish_adapter.py`, `test_publish_media.py`,
  `test_publish_service.py`, `test_publish_persist.py`, plus route /
  settings tests
- `tools/smoke_1_6_publish.sh`
- `apps/server/README.md`, root `README.md`
- `docs/planning/domain_statuses.md`, `docs/planning/task_sheet.md`,
  `docs/prompts/product.md`
- `docs/ops/deploy.md`, `docs/ops/README.md`
- this file

## Next

- Badger: sync `apps/server`, restart `twerva-api`, keep nginx `/health`
  only. Leave `PUBLISH_ADAPTER=mock`. Optional loopback
  `tools/smoke_1_6_publish.sh`.
- Live Ayrshare when Mu adds `AYRSHARE_API_KEY` and connected test
  accounts (plus a public-or-uploaded media path).
- **1.7** measure & steer stubs.
