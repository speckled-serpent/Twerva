# Twerva server

FastAPI process for the Twerva API. `GET /health` is a liveness check and does
**not** open a database connection (it does not import models or `app.db` at
module load). Domain tables land in Alembic revision `12bk_domain_schema`
(task 1.2b–k). Persist-proof HTTP lives under `/api/v1` (task 1.2l) and is
mounted when `DATABASE_URL` can be resolved.

Requires **Python 3.11+**.

## Run locally

From this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:application --reload --host 127.0.0.1 --port 8000
```

Alternatively, install from `pyproject.toml` with `pip install -e .` instead of `pip install -r requirements.txt`.

Check the process:

```bash
curl http://127.0.0.1:8000/health
```

Expected JSON:

```json
{"status":"ok"}
```

Interactive docs (FastAPI default): [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

`GET /health` works without `DATABASE_URL`. Settings, `app.db`, Alembic, seed,
and `/api/v1` require the URL below. Without a URL the process still starts
and serves health only (1.2a / 1.2l-iv).

## Database URL

The process reads `DATABASE_URL` from the environment (or a local `.env` in
this directory). Bare `postgresql://` / `postgres://` URLs are rewritten to
the psycopg3 dialect `postgresql+psycopg://`.

Outside tests, a missing or blank `DATABASE_URL` raises at settings load
(`MissingDatabaseUrlError`). Tests may set `TWERVA_ENV=test` or
`TWERVA_TESTING=1` to use a placeholder URL.

### Local override

```bash
cp .env.example .env
# edit .env, or export instead:
export DATABASE_URL=postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva
export ARTIFACT_STORAGE_DIR=./data/artifacts
```

`.env` is gitignored. Do not commit credentials.

### Production (`twerva-server`)

On-box file: `/opt/twerva/database_url.env` (mode 600). It provides
`DATABASE_URL` for Docker Postgres bound to `127.0.0.1:5432`. Load it into
the process environment (systemd `EnvironmentFile=` or `source` in a shell).
The app does not open that file itself.

Production deploy, migrate, verify, and rollback (Badger):
[`docs/ops/deploy.md`](../../docs/ops/deploy.md).

## Artifact storage (1.4)

Carousel PNGs live on the **local filesystem**. There is no S3 in this
slice. Settings key: `ARTIFACT_STORAGE_DIR`.

| Environment | Path |
|---|---|
| Production (`twerva-server`) | `/opt/twerva/artifacts` (process default) |
| Local | `./data/artifacts` (relative to this directory; set in `.env.example`) |

The write helper stores `{artifact_id}/{slide_index}_{role}.png` and puts
that relative path on each `slides[].asset_ref`. Create the directory
before generate if the process user cannot mkdir the default.

Template: [`docs/planning/carousel_template_v1.md`](../../docs/planning/carousel_template_v1.md).

## Alembic

Run from this directory so `alembic.ini` and `app.settings` resolve.
Current head: **`12bk_domain_schema`** (Phase 1.2c–1.2j tables + enums).

```bash
export DATABASE_URL=postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva
alembic heads
alembic upgrade head
alembic current
```

`alembic upgrade head` is clean on an empty Postgres database. Production
apply on `twerva-server` uses the on-box env file (below). See
`docs/reports/task_1_2_report.md` for the 1.2k-iii note.

### Smoke (`1.2a-v`) — connect with the on-box env file

SSH to `twerva-server` is optional if you already have a shell there. From
`apps/server` on that box:

```bash
set -a
source /opt/twerva/database_url.env
set +a
alembic current
```

`alembic current` opens Postgres on `127.0.0.1:5432` using `DATABASE_URL`.
After `alembic upgrade head` it should report `12bk_domain_schema (head)`.

Local equivalent (your own `DATABASE_URL`):

```bash
export DATABASE_URL=postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva
alembic upgrade head
alembic current
```

## HTTP API (`/api/v1`)

No auth. `POST` + `GET` list + `GET` by id for Brand, SourceItem, Cluster,
Account, Artifact (includes `status`), and PostJob (includes `status`).
`POST /api/v1/generate/carousel` renders a draft Artifact from a
SourceItem. Interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
when the process has a database URL.

### Seed (1.2m)

Idempotent Spotmu brand (`slug=spotmu`, `name=Spotmu`) plus one **fake**
example SourceItem (`external_key=example`, canonical URL
`https://spotmu.com/interest/example`). Not real ingest.

From this directory, after `alembic upgrade head`:

```bash
export DATABASE_URL=postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva
python -m app.seed
```

Re-running converges on the same slug / `external_key` rows.

## Spotmu ingest (1.3)

Locked path (spike): public JSON + sitemap. Config:

```bash
# optional; default is the locked public origin
export SPOTMU_API_BASE_URL=https://spotmu.com
```

The client calls:

- `{SPOTMU_API_BASE_URL}/api/v1/interests/slug/{slug}`
- `{SPOTMU_API_BASE_URL}/sitemap.xml`

`GET /interests/slug/{slug}` without `/api/v1` is the Spotmu SPA shell,
not JSON. Live curls and field mapping:
[`docs/reports/task_1_3_ingest_spike.md`](../../docs/reports/task_1_3_ingest_spike.md).

### Fetch + upsert one slug (CLI)

From this directory, after `alembic upgrade head` and with
`DATABASE_URL` set. Talks to production Spotmu:

```bash
python -m app.ingest.spotmu_interest ai-agents
# optional origin override:
python -m app.ingest.spotmu_interest ai-agents --base-url https://spotmu.com
```

Idempotent: Brand `slug=spotmu` is created if missing;
`source_type=spotmu_interest` / `external_key=<slug>` updates in place
(same id). `overview_bullets` on the wire is a newline string; we store
`list[str]`. Brand-kit refs are `null` (not on the public payload).

### HTTP (loopback / SSH tunnel — not public nginx)

```bash
# one real production slug
curl -sS -X POST http://127.0.0.1:8000/api/v1/ingest/spotmu/interests/ai-agents

# sitemap window (default limit 20) or an explicit list
curl -sS -X POST http://127.0.0.1:8000/api/v1/ingest/spotmu/sync \
  -H 'Content-Type: application/json' \
  -d '{"limit": 5}'
curl -sS -X POST http://127.0.0.1:8000/api/v1/ingest/spotmu/sync \
  -H 'Content-Type: application/json' \
  -d '{"slugs":["ai-agents","amazon"]}'
```

No scheduler. On-demand only.

### Cluster `spotmu-general` recipe (1.3e)

After ingest, assign the interest to a lane under Brand spotmu:

```bash
# BRAND_ID from GET /api/v1/brands (slug=spotmu)
# SOURCE_ITEM_ID from the ingest POST (or GET /api/v1/source-items)
curl -sS -X POST http://127.0.0.1:8000/api/v1/clusters \
  -H 'Content-Type: application/json' \
  -d '{"brand_id":"<brand-id>","slug":"spotmu-general","name":"Spotmu general"}'
curl -sS -X POST \
  http://127.0.0.1:8000/api/v1/clusters/<cluster-id>/source-items/<source-item-id>
curl -sS http://127.0.0.1:8000/api/v1/clusters/<cluster-id>
# -> source_item_ids includes the ingested id
curl -sS -X DELETE \
  http://127.0.0.1:8000/api/v1/clusters/<cluster-id>/source-items/<source-item-id>
```

### Ingest smoke (1.3f-i)

With uvicorn running **and** `DATABASE_URL` set (so `/api/v1` is mounted).
Hits **production** Spotmu for slug `ai-agents` (override with
`SPOTMU_SMOKE_SLUG`):

```bash
# from the repo root
tools/smoke_1_3_ingest.sh
# or
TWERVA_API_BASE_URL=http://127.0.0.1:8000 tools/smoke_1_3_ingest.sh
```

Ingests `ai-agents`, GETs the SourceItem, creates/reuses cluster
`spotmu-general`, attaches the pair. Same public-surface rule as 1.2:
`https://twerva.com/api/...` stays unreachable; use loopback or a tunnel.

## Carousel generate (1.4)

Template lock: [`docs/planning/carousel_template_v1.md`](../../docs/planning/carousel_template_v1.md).
Sync generate (no Celery). Each call inserts a **new** `draft` Artifact
(history kept). `GET /health` still starts without `DATABASE_URL`.

### CLI

From this directory, after `alembic upgrade head` and with
`DATABASE_URL` set. Uses a SourceItem already in Postgres (seed or
ingest) — does not call Spotmu:

```bash
python -m app.generate.carousel_cli <source_item_id>
python -m app.generate.carousel_cli <source_item_id> --cluster-id <cluster-id>
# optional local store override:
python -m app.generate.carousel_cli <source_item_id> --storage-dir ./data/artifacts
```

### HTTP (loopback / SSH tunnel — not public nginx)

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/generate/carousel \
  -H 'Content-Type: application/json' \
  -d '{"source_item_id":"<source-item-id>"}'
# optional:
# -d '{"source_item_id":"<source-item-id>","cluster_id":"<cluster-id>"}'
curl -sS http://127.0.0.1:8000/api/v1/artifacts/<artifact-id>
```

Returns the existing Artifact read schema (`status=draft`,
`format=carousel`, `caption`, `cta_url`, `slides` with `asset_ref`).

### Carousel smoke (1.4e-iii)

With uvicorn running **and** `DATABASE_URL` set (so `/api/v1` is mounted).
Uses the seeded/example SourceItem in the DB (creates the seed-shaped
row via API if missing). **Does not** call Spotmu:

```bash
# from the repo root
tools/smoke_1_4_carousel.sh
# or
TWERVA_API_BASE_URL=http://127.0.0.1:8000 tools/smoke_1_4_carousel.sh
```

### Persist-proof smoke (1.2l-v)

With uvicorn running **and** `DATABASE_URL` set (so `/api/v1` is mounted):

```bash
# from the repo root
tools/smoke_1_2l_api.sh
# or
TWERVA_API_BASE_URL=http://127.0.0.1:8000 tools/smoke_1_2l_api.sh
```

The script POSTs Brand `spotmu` (reuses the row if the slug exists) →
SourceItem → Cluster → Account → Artifact `draft` → PostJob `scheduled`,
then GETs each id. Cluster/account/source keys use a timestamp suffix so
re-runs do not collide.

Equivalent curl sketch (replace UUIDs from each response):

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS -X POST http://127.0.0.1:8000/api/v1/brands \
  -H 'Content-Type: application/json' \
  -d '{"slug":"spotmu","name":"Spotmu"}'
curl -sS -X POST http://127.0.0.1:8000/api/v1/source-items \
  -H 'Content-Type: application/json' \
  -d '{"brand_id":"<brand-id>","title":"Example Spotmu interest","interest_heading":"What this example lane is about","overview_bullets":["one","two","three"],"canonical_url":"https://spotmu.com/interest/example"}'
curl -sS -X POST http://127.0.0.1:8000/api/v1/clusters \
  -H 'Content-Type: application/json' \
  -d '{"brand_id":"<brand-id>","slug":"example-lane","name":"Example lane"}'
curl -sS -X POST http://127.0.0.1:8000/api/v1/accounts \
  -H 'Content-Type: application/json' \
  -d '{"cluster_id":"<cluster-id>","platform":"instagram","handle":"spotmu_example"}'
curl -sS -X POST http://127.0.0.1:8000/api/v1/artifacts \
  -H 'Content-Type: application/json' \
  -d '{"brand_id":"<brand-id>","source_item_id":"<source-item-id>","cluster_id":"<cluster-id>","status":"draft"}'
curl -sS -X POST http://127.0.0.1:8000/api/v1/post-jobs \
  -H 'Content-Type: application/json' \
  -d '{"artifact_id":"<artifact-id>","account_id":"<account-id>","status":"scheduled"}'
```

### Deploy `twerva-api` on EC2 (1.2l-iv)

Live SSH to `twerva-server` is **not** required for this slice (same
deferral as 1.2a-v / 1.2k-iii). When applying this revision on the box:

1. Update the Twerva checkout used by systemd `twerva-api`.
2. In `apps/server`, refresh the venv: `pip install -r requirements.txt`.
3. Load `/opt/twerva/database_url.env` into the environment (`set -a; source ...; set +a` or systemd `EnvironmentFile=`).
4. `alembic upgrade head` — still revision `12bk_domain_schema` (no new migration).
5. `python -m app.seed` (idempotent Spotmu brand + example SourceItem).
6. `sudo systemctl restart twerva-api` (uvicorn `app.main:application` on `127.0.0.1:8000`).
7. Confirm `curl -sS http://127.0.0.1:8000/health` and `https://twerva.com/health` return `{"status":"ok"}`.
8. Optional: `tools/smoke_1_2l_api.sh` with `TWERVA_API_BASE_URL=http://127.0.0.1:8000`.
9. **1.3:** `pip install -r requirements.txt` picks up `httpx`. No new
   Alembic revision. `SPOTMU_API_BASE_URL` is optional (default
   `https://spotmu.com`). Do **not** add nginx `/api`. Optional:
   `tools/smoke_1_3_ingest.sh` on loopback (talks to production Spotmu).
10. **1.4:** `mkdir -p /opt/twerva/artifacts` (writable by the
    `twerva-api` user). `pip install -r requirements.txt` picks up
    **Pillow**. Optional `ARTIFACT_STORAGE_DIR` (default
    `/opt/twerva/artifacts`). Restart `twerva-api`. Do **not** add
    nginx `/api` or a public artifacts location. Optional loopback:
    `tools/smoke_1_4_carousel.sh` (DB source only; no Spotmu).

`GET /health` must keep working if the unit is ever started without
`DATABASE_URL` (health-only). Production must keep the env file so
`/api/v1` mounts in the same process Badger monitors.
