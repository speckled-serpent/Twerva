# Task 1.4 — Carousel generate

*2026-09-15*

Phase 1.4 leaves **1.4a–1.4f** (serial). No approval UI, publish,
Celery, video, or S3. `GET /health` still starts without
`DATABASE_URL`. Sync generate only.

## Done

- **1.4a** Template lock: [`carousel_template_v1.md`](../planning/carousel_template_v1.md).
  1080×1080 PNG; roles `cover` / `heading` / `bullet` / `cta`; warm
  paper + muted teal; CTA = `canonical_url` or
  `https://spotmu.com/interest/{slug}`; caption + seven safe hashtags;
  one bullet per slide, 160-char overflow, empty skipped.
- **1.4b** `ARTIFACT_STORAGE_DIR` (default `/opt/twerva/artifacts`;
  local `./data/artifacts`). Write helper
  `{artifact_id}/{slide_index}_{role}.png` → relative `asset_ref`.
  README + Badger notes. **No S3.**
- **1.4c** `pillow>=10.4.0,<12.0.0`. `app/generate/carousel.py` plans
  and renders. Unit test: fake source → ≥3 PNGs + caption (tmp dir).
  Empty bullets still emit cover / heading / CTA.
- **1.4d** `generate_carousel_artifact_draft` inserts a new
  `Artifact` (`format=carousel`, `status=draft`) each run. Wires
  `brand_id` / `source_item_id` / optional `cluster_id`. Persist test
  reads via existing `GET` schema (skips if Postgres is down).
- **1.4e** `POST /api/v1/generate/carousel`
  `{source_item_id, cluster_id?}`. CLI
  `python -m app.generate.carousel_cli <source_item_id>`.
  `tools/smoke_1_4_carousel.sh` uses a DB source (seed-shaped example);
  no Spotmu HTTP.
- **1.4f** This report. Leaves ticked. Badger: mkdir artifacts dir,
  pip (Pillow), restart; disk growth; still no public `/api` nginx.

## Locked choices

| Topic | Choice |
|---|---|
| Canvas | 1080×1080 PNG |
| Storage | Local `ARTIFACT_STORAGE_DIR` (not S3) |
| `asset_ref` | `{artifact_id}/{slide_index}_{role}.png` |
| Re-generate | New draft row (keep history) |
| Jobs | Sync in the API process (no Celery) |
| Public nginx | `/health` only |

## Trade-offs

- System fonts (DejaVu / Liberation) when present; Pillow default
  otherwise. No vendored webfont, no brand-kit image.
- Orphan PNGs if DB commit fails after write (MVP).
- Disk grows with history; operators watch `/opt/twerva/artifacts`.
- Cluster brand mismatch is HTTP 400; missing source/cluster is 404.
- Live SSH deploy / smoke on `twerva-server` is documented, not run
  here (same stance as 1.2l-iv / 1.3).

## Verified

- `python -m unittest discover -s tests` from `apps/server`: **64 tests OK**
  (render, storage helper, settings, route surface, health without
  `DATABASE_URL`, persist generate+GET against local Postgres 16).
- Smoke: `tools/smoke_1_4_carousel.sh` against loopback uvicorn — seed
  SourceItem `example` → 6-slide draft, GET matches, second generate
  keeps a new Artifact id. PNGs are 1080×1080.
- CLI: `python -m app.generate.carousel_cli <source_item_id>` prints a
  new draft id.
- `GET /health` via TestClient **without** `DATABASE_URL` →
  `200 {"status":"ok"}`; `/api/v1` not attached in that process.
- Live SSH deploy on `twerva-server` is documented, not run here.

## Out of scope (as specified)

- Approval UI (1.5), publish (1.6), Celery/Redis
- Short video
- S3 / public artifact URLs
- Public nginx `/api`

## Scripts touched

- `docs/planning/carousel_template_v1.md`
- `apps/server/app/generate/` (`carousel.py`, `service.py`,
  `carousel_cli.py`, `errors.py`)
- `apps/server/app/storage/artifacts.py`
- `apps/server/app/api/v1/generate.py`, `router.py`, `schemas.py`
- `apps/server/app/settings.py`, `requirements.txt`, `pyproject.toml`,
  `.env.example`
- `apps/server/tests/test_carousel_render.py`,
  `test_carousel_persist.py`, `test_artifact_storage.py`, plus route /
  schema / settings tests
- `tools/smoke_1_4_carousel.sh`
- `apps/server/README.md`, root `README.md`
- `docs/ops/deploy.md`, `docs/ops/README.md`
- `docs/planning/task_sheet.md`, this file

## Next

- Badger: `mkdir -p /opt/twerva/artifacts`,
  `pip install -r requirements.txt`, restart `twerva-api`, keep nginx
  `/health` only. Optional loopback `tools/smoke_1_4_carousel.sh`.
- **1.5** approval & schedule.
