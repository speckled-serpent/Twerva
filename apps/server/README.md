# Twerva server

FastAPI process for the Twerva API. `GET /health` is a liveness check and does
**not** open a database connection (it does not import models or `app.db` at
module load). Domain tables land in Alembic revision `12bk_domain_schema`
(task 1.2b–k). Ops operator table `ops_users` is revision
`ops_users_web_auth`; `role` (`admin` / `reader`) is
`ops_users_role_rbac`. Persist-proof HTTP lives under `/api/v1` (task 1.2l) and is
mounted when `DATABASE_URL` can be resolved. All `/api/v1` routes except
`/api/v1/auth/login` / `/logout` / `/me` require a signed session cookie.
Readers are GET-only (plus self `change-password` and `logout`).

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
Current head: **`artifact_template_id`** (parent `ops_users_role_rbac`).

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
After `alembic upgrade head` it should report `ops_users_role_rbac (head)`.

Local equivalent (your own `DATABASE_URL`):

```bash
export DATABASE_URL=postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva
alembic upgrade head
alembic current
```

## Ops auth

Operator accounts live in `ops_users` (not social `accounts`). Sessions
are a **signed httpOnly cookie** (`itsdangerous` + `SESSION_SECRET`);
there is no `ops_sessions` table. Cookie flags: `HttpOnly`,
`SameSite=Lax`, `Secure` from `SESSION_COOKIE_SECURE` (true in
production HTTPS).

```bash
# required outside tests when DATABASE_URL is set
export SESSION_SECRET=...          # openssl rand -hex 32
export SESSION_COOKIE_SECURE=false # local HTTP only
export OPS_ADMIN_USERNAME=admin
export OPS_ADMIN_PASSWORD=...      # bootstrap only; never commit
alembic upgrade head
python -m app.auth.bootstrap       # no-op if any ops_users row exists
```

Public routes: `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`,
`GET /api/v1/auth/me`. Everything else under `/api/v1` is 401 without a
valid cookie. `GET /health` stays public and import-light.

Roles: bootstrap env seeds the **first empty-DB admin** only (`role=admin`).
Password rotation is `POST /api/v1/auth/change-password` (self) or the
Account page — not a second bootstrap. Admins `GET`/`POST /api/v1/auth/users`
to provision operators (`admin` or `reader`). Readers may GET domain
routes and change their own password; other writes are 403.

```bash
curl -sS -c /tmp/twerva-ops.jar -b /tmp/twerva-ops.jar \
  -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"..."}'
curl -sS -b /tmp/twerva-ops.jar http://127.0.0.1:8000/api/v1/auth/me
curl -sS -b /tmp/twerva-ops.jar http://127.0.0.1:8000/api/v1/brands
```

## HTTP API (`/api/v1`)

Cookie auth (see above). `POST` + `GET` list + `GET` by id for Brand, SourceItem, Cluster,
Account, Artifact (includes `status`), and PostJob (includes `status`).
`POST /api/v1/generate/carousel` renders a draft Artifact from a
SourceItem. Review-queue approve/reject/PATCH and `POST /api/v1/schedule`
are Phase 1.5. `POST /api/v1/publish/run/{post_job_id}` mock-publishes a
scheduled job (Phase 1.6; default `PUBLISH_ADAPTER=mock`). Measure &
steer (Phase 1.7): `POST /api/v1/post-jobs/{id}/metrics`, cluster
median summary, steer, agent-summary. Interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
when the process has a database URL. Thin ops UI: [`apps/ops/README.md`](../ops/README.md)
(Vite proxy `/api` → this process). Agent hooks (draft / human gate /
propose steer): [`docs/agents/README.md`](../../docs/agents/README.md).

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
Restricted Spotmu templates (`GET /api/v1/generate/templates`):
`spotmu_paper_v1` (default, current look) and `spotmu_bold_v1`.
Sync generate (no Celery). Each generate or regenerate inserts a **new**
`draft` Artifact (history kept). Authenticated
`GET /api/v1/artifacts/{id}/slides/{index}/image` streams the PNG
(readers may GET; no public unauthenticated access).
`GET /health` still starts without `DATABASE_URL`.

### CLI

From this directory, after `alembic upgrade head` and with
`DATABASE_URL` set. Uses a SourceItem already in Postgres (seed or
ingest) — does not call Spotmu:

```bash
python -m app.generate.carousel_cli <source_item_id>
python -m app.generate.carousel_cli <source_item_id> --cluster-id <cluster-id>
python -m app.generate.carousel_cli <source_item_id> --template-id spotmu_bold_v1
# optional local store override:
python -m app.generate.carousel_cli <source_item_id> --storage-dir ./data/artifacts
```

### HTTP (loopback / SSH tunnel — not public nginx)

```bash
curl -sS -b /tmp/twerva-ops.jar http://127.0.0.1:8000/api/v1/generate/templates
curl -sS -b /tmp/twerva-ops.jar -X POST http://127.0.0.1:8000/api/v1/generate/carousel \
  -H 'Content-Type: application/json' \
  -d '{"source_item_id":"<source-item-id>","template_id":"spotmu_bold_v1"}'
curl -sS -b /tmp/twerva-ops.jar http://127.0.0.1:8000/api/v1/artifacts/<artifact-id>
curl -sS -b /tmp/twerva-ops.jar \
  http://127.0.0.1:8000/api/v1/artifacts/<artifact-id>/slides/0/image -o /tmp/slide.png
curl -sS -b /tmp/twerva-ops.jar -X POST \
  http://127.0.0.1:8000/api/v1/artifacts/<artifact-id>/regenerate \
  -H 'Content-Type: application/json' \
  -d '{"template_id":"spotmu_paper_v1"}'
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

## Approval & schedule (1.5)

Thin API plus ops console (`apps/ops`, 1.8). No real publish (1.6). Sync schedule create
(no Celery). Cadence day is **UTC**. `GET /health` still starts without
`DATABASE_URL`.

### Review queue

```bash
# drafts
curl -sS 'http://127.0.0.1:8000/api/v1/artifacts?status=draft'
# edit caption / cta_url while draft or approved
curl -sS -X PATCH http://127.0.0.1:8000/api/v1/artifacts/<artifact-id> \
  -H 'Content-Type: application/json' \
  -d '{"caption":"edited caption"}'
# approve (optional caption at approve)
curl -sS -X POST http://127.0.0.1:8000/api/v1/artifacts/<artifact-id>/approve \
  -H 'Content-Type: application/json' \
  -d '{"caption":"approved caption"}'
# reject (terminal; optional reason is accepted and ignored — no column)
curl -sS -X POST http://127.0.0.1:8000/api/v1/artifacts/<artifact-id>/reject \
  -H 'Content-Type: application/json' \
  -d '{"reason":"off-brand"}'
```

Rejected cannot be re-approved; generate a new Artifact.

### Schedule

Artifact must be `approved`. Account cluster brand must match the
Artifact brand. When the Artifact has `cluster_id`, the Account must
belong to that cluster. `accounts.cadence_cap_per_day` null = no cap;
otherwise non-failed `post_jobs` on that UTC day must stay under the cap
(HTTP **409** when at/over).

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/schedule \
  -H 'Content-Type: application/json' \
  -d '{"artifact_id":"<artifact-id>","account_id":"<account-id>","scheduled_for":"2026-09-16T15:00:00Z"}'
```

### Approve + schedule smoke (1.5c-iii)

With uvicorn running **and** `DATABASE_URL` set (so `/api/v1` is mounted).
Uses the seeded/example SourceItem + generate (no Spotmu HTTP):

```bash
# from the repo root
tools/smoke_1_5_approve_schedule.sh
# or
TWERVA_API_BASE_URL=http://127.0.0.1:8000 tools/smoke_1_5_approve_schedule.sh
```

## Publish (1.6)

Thin API plus ops console (`apps/ops`, 1.8). No live vendor HTTP. Default adapter is
**mock** (`PUBLISH_ADAPTER=mock`). Sync publish (no Celery).
`GET /health` still starts without `DATABASE_URL`. Spike lock:
[`docs/reports/task_1_6_publish_spike.md`](../../docs/reports/task_1_6_publish_spike.md).

```bash
# optional; default is mock (CI-safe)
export PUBLISH_ADAPTER=mock
# live vendor later only:
# export PUBLISH_ADAPTER=ayrshare
# export AYRSHARE_API_KEY=...
```

### Run one scheduled job

Artifact should already be approved and scheduled (1.5). The endpoint
also accepts `failed` jobs (manual retry). Already `published` is HTTP
**409**.

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/publish/run/<post-job-id>
```

Mock success: `status=published`, `platform_post_id` like
`mock-instagram-<uuid>`, `platform_post_url` on `example.invalid`,
`published_at` set. Slide PNGs are resolved from `ARTIFACT_STORAGE_DIR`
via `slides[].asset_ref`. Adapter/media errors record `failed` +
`last_error` on the same row (HTTP 200).

Retry: POST the same URL again on a `failed` job. No Redis and no
backoff sleep — the operator (or a later worker) decides when to retry.

### Publish smoke (1.6c-iv)

With uvicorn running **and** `DATABASE_URL` set (so `/api/v1` is mounted).
Uses the seeded/example SourceItem + generate + approve + schedule
(**no** Spotmu HTTP, **no** vendor signup):

```bash
# from the repo root
tools/smoke_1_6_publish.sh
# or
TWERVA_API_BASE_URL=http://127.0.0.1:8000 tools/smoke_1_6_publish.sh
```

## Measure & steer (1.7)

Thin API plus ops console (`apps/ops`, 1.8). No Celery, **no** real analytics vendor.
`GET /health` still starts without `DATABASE_URL`. Reuses
`metric_snapshots` + `steer_actions` (no new Alembic revision).

After mock publish, POST metrics by hand (or use the stub below):

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/post-jobs/<post-job-id>/metrics \
  -H 'Content-Type: application/json' \
  -d '{"views":20,"likes":2,"comments":0,"shares":0}'
```

`published` / `failed` jobs become `measured`. Multiple snapshots per
job are allowed; queries take **latest `captured_at`**.

### Stub puller (1.7a-ii)

There is no vendor insights pull. For jobs whose `platform_post_id`
starts with `mock-` (the 1.6 mock adapter):

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/post-jobs/<post-job-id>/metrics/stub
```

Writes `views=100`, `likes=10`, `comments=2`, `shares=1`. Any other
platform id is HTTP **409**.

### Cluster median (1.7b)

```bash
curl -sS http://127.0.0.1:8000/api/v1/clusters/<cluster-id>/metrics/summary
```

Median of latest-wins **views** across post jobs on that cluster's
accounts. Jobs without a snapshot, or with `views` null on the latest
row, are omitted from the median. Empty → `"median_views": null`
(not zero). Even-length lists average the two central values.

### Steer (1.7c)

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/clusters/<cluster-id>/steer \
  -H 'Content-Type: application/json' \
  -d '{"action":"pause","reason":"median below floor"}'
```

`action` is `kill` | `pause` | `double_down` | `resume`. Optional
`reason`, optional `created_by` (default `human`). Pause/kill set
`clusters.is_active=false`; resume sets true. **double_down is
log-only** (row written, flag unchanged; no cadence bump in MVP).
Account `status` rows are not flipped.

### Agent summary (1.7d)

```bash
curl -sS "http://127.0.0.1:8000/api/v1/clusters/<cluster-id>/agent-summary"
curl -sS "http://127.0.0.1:8000/api/v1/clusters/<cluster-id>/agent-summary?format=markdown"
```

JSON (default) or markdown: cluster flag, median block, recent
artifacts / post jobs / steer actions.

## Agent hooks (1.9)

Docs only (plus a thin localhost script). No new routes.

- Operator/agent: [`docs/agents/README.md`](../../docs/agents/README.md)
- Dry-run playbook: [`docs/agents/playbook_batch_generate_spotmu_cluster.md`](../../docs/agents/playbook_batch_generate_spotmu_cluster.md)
- Script: `tools/agent_batch_generate.sh` (generate drafts, **stop
  before approve**)
- Phase 1 close: [`docs/reports/phase_1_exit_report.md`](../../docs/reports/phase_1_exit_report.md)

```bash
# from the repo root; API already running with DATABASE_URL
tools/agent_batch_generate.sh
```

### Measure & steer smoke (1.7d-ii)

With uvicorn running **and** `DATABASE_URL` set (so `/api/v1` is mounted).
Uses the seeded/example SourceItem + generate + approve + schedule +
mock publish (**no** Spotmu HTTP, **no** vendor):

```bash
# from the repo root
tools/smoke_1_7_measure_steer.sh
# or
TWERVA_API_BASE_URL=http://127.0.0.1:8000 tools/smoke_1_7_measure_steer.sh
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
4. `alembic upgrade head` — head is `ops_users_role_rbac`. Then
   `python -m app.auth.bootstrap`.
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
11. **1.5:** no new host deps, no Alembic revision, no nginx `/api`.
    Restart `twerva-api` after sync. Optional loopback:
    `tools/smoke_1_5_approve_schedule.sh` (seed/generate path; no Spotmu,
    no real publish).
12. **1.6:** no new host deps, no Alembic revision, no nginx `/api`.
    Optional `PUBLISH_ADAPTER` (default `mock`). Do **not** set
    `ayrshare` until Mu adds `AYRSHARE_API_KEY` (live HTTP is not wired
    yet). Restart `twerva-api` after sync. Optional loopback:
    `tools/smoke_1_6_publish.sh` (approve/schedule/mock publish; no
    Spotmu, no vendor signup).
13. **1.7:** no new host deps, no Alembic revision, no nginx `/api`.
    Restart `twerva-api` after sync. Optional loopback:
    `tools/smoke_1_7_measure_steer.sh` (metrics → median → steer →
    agent-summary; no analytics vendor).
14. **1.8:** ops console is local Vite (`apps/ops`). Do **not** add
    nginx for `dist/` or `/api` tonight. See `apps/ops/README.md`.
15. **1.9:** docs + `tools/agent_batch_generate.sh` only. No new host
    deps, no Alembic, no nginx `/api`. Optional loopback dry-run after
    generate storage is writable.

`GET /health` must keep working if the unit is ever started without
`DATABASE_URL` (health-only). Production must keep the env file so
`/api/v1` mounts in the same process Badger monitors.
