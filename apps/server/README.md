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
```

`.env` is gitignored. Do not commit credentials.

### Production (`twerva-server`)

On-box file: `/opt/twerva/database_url.env` (mode 600). It provides
`DATABASE_URL` for Docker Postgres bound to `127.0.0.1:5432`. Load it into
the process environment (systemd `EnvironmentFile=` or `source` in a shell).
The app does not open that file itself.

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
Interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
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

`GET /health` must keep working if the unit is ever started without
`DATABASE_URL` (health-only). Production must keep the env file so
`/api/v1` mounts in the same process Badger monitors.
