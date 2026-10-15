# Task 1.3 — Spotmu ingest

*2026-09-15*

Phase 1.3 leaves **1.3a–1.3f** (serial). No carousel, publish, auth, or
public nginx `/api` change. `GET /health` still starts without
`DATABASE_URL`.

## Done

- **1.3a** Spike + lock: public JSON
  `GET https://spotmu.com/api/v1/interests/slug/{slug}` and sitemap
  `GET https://spotmu.com/sitemap.xml`. Live `/interests/slug/{slug}`
  (no `/api/v1`) is the SPA shell. `SPOTMU_API_BASE_URL` defaults to
  `https://spotmu.com`. `app.spotmu.com` served the same JSON in the
  spike. Product open question updated.
  Report: [`task_1_3_ingest_spike.md`](task_1_3_ingest_spike.md).
- **1.3b** `app/ingest/spotmu.py`: typed fetch, newline-bullet split,
  constructed `/interest/{slug}` canonical URL, `raw_payload`, clear
  404 / non-JSON / timeout errors. Mocked unit tests.
- **1.3c** Idempotent upsert onto Brand `spotmu` /
  `source_type=spotmu_interest` / `external_key=slug`.
  `POST /api/v1/ingest/spotmu/interests/{slug}`. CLI
  `python -m app.ingest.spotmu_interest <slug>`. Mocked idempotency
  test (second pull updates fields, same id).
- **1.3d** Sitemap slug list (default cap 20).
  `POST /api/v1/ingest/spotmu/sync` with optional `slugs` or `limit`.
  No scheduler.
- **1.3e** `POST/DELETE /api/v1/clusters/{id}/source-items/{source_item_id}`.
  Cluster read/list include `source_item_ids`. README + smoke recipe
  for cluster `spotmu-general`.
- **1.3f** `tools/smoke_1_3_ingest.sh` (production slug `ai-agents`).
  This report. Leaves ticked. Badger note in `docs/ops/deploy.md`.

## Locked choices

| Topic | Choice |
|---|---|
| Origin | `https://spotmu.com` (`SPOTMU_API_BASE_URL`) |
| JSON path | `/api/v1/interests/slug/{slug}` (not origin `/interests/slug/{slug}`) |
| Discovery | `/sitemap.xml` (`/interest/{slug}` locs) |
| `overview_bullets` | Live string, split on newlines → JSONB `list[str]` |
| `brand_kit_refs` | `null` (no logo/kit on public payload) |
| Cluster recipe | `slug=spotmu-general` under Brand `spotmu` |

## Trade-offs

- New runtime dep: `httpx` (explicit; FastAPI TestClient is not enough
  to import in the app).
- No Alembic revision (reuse `cluster_source_items` + `SourceType`).
- Sync commits per slug so one failure does not roll back successes.
- Attach requires the same `brand_id`; detach of a missing pair is 404.
- Live SSH deploy / smoke on `twerva-server` is documented, not run
  here (same stance as 1.2l-iv).

## Verified

- `python -m unittest discover -s tests` from `apps/server` (client,
  upsert idempotency, cluster `source_item_ids`, route surface, health
  without `DATABASE_URL`). Persist attach/detach runs when Postgres is
  reachable and skips otherwise.
- `GET /health` still does not import settings/models/`app.db` at
  module load.
- Spike curls: sitemap 436 interest URLs; `ai-agents` and `amazon`
  public JSON 200; unknown slug 404 `Interest not found`.
- Live typed client (no DB): `fetch_spotmu_interest_by_slug("ai-agents")`
  → title/heading/5 bullets/canonical
  `https://spotmu.com/interest/ai-agents`; sitemap helper returned the
  first five locs. `GET /health` via TestClient **without**
  `DATABASE_URL` → `200 {"status":"ok"}`; `/api/v1/brands` is `404` in
  that health-only process.

## Out of scope (as specified)

- Carousel generate (1.4), publish, auth
- Public nginx `/api`
- Scheduler / Phase 2 bulk polish
- HTML scrape; authenticated Spotmu export

## Scripts touched

- `apps/server/app/ingest/` (`spotmu.py`, `upsert.py`, `spotmu_interest.py`)
- `apps/server/app/api/v1/ingest.py`, `clusters.py`, `schemas.py`, `router.py`
- `apps/server/app/settings.py`, `requirements.txt`, `pyproject.toml`, `.env.example`
- `apps/server/tests/test_spotmu_client.py`, `test_spotmu_upsert.py`,
  `test_cluster_links.py`, route/schema/settings/persist tests
- `tools/smoke_1_3_ingest.sh`
- `apps/server/README.md`, root `README.md`
- `docs/reports/task_1_3_ingest_spike.md`, this file
- `docs/prompts/product.md`, task sheet (later replaced by `docs/planning/phase_map.md`), `docs/ops/deploy.md`

## Next

- Badger: `pip install -r requirements.txt`, restart `twerva-api`, keep
  nginx `/health` only. Optional loopback
  `tools/smoke_1_3_ingest.sh`.
- **1.4** carousel generate from an ingested `source_item`.
