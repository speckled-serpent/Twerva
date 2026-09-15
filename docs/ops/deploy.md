# Production deploy and rollback (`twerva-server`)

Audience: **Badger** (Twerva Server Manager).

This runbook is the in-repo copy of the Server Manager handoff for
production `twerva-server`. It is **on-box procedure only**. Do not
invent AWS console steps, security-group edits, or credentials. Do not
paste secret file contents into git or chat.

Until a secret-free helper lands under `tools/`, deploy is manual.

## Host and access

| Fact | Value |
|---|---|
| Instance name | EC2 `twerva-server` |
| Elastic IP | `3.19.233.237` |
| Public URL | `https://twerva.com` |
| SSH | `ubuntu@3.19.233.237` |
| SSH key (Mu’s archlinux) | `~/.ssh/twerva-key.pem` |
| OS user | `ubuntu` (admin / sudo) |

There is **no** separate monitor account yet. Use `ubuntu`.

```bash
ssh -i ~/.ssh/twerva-key.pem ubuntu@3.19.233.237
```

## On-box layout

`/opt/twerva/server` is **not** a git checkout today. Sync a tree from
git `main` (rsync or tar). Preserve the on-box `.venv`.

| Path | Role |
|---|---|
| `/opt/twerva/server` | App tree (`apps/server` contents). Preserve `.venv`. |
| systemd `twerva-api` | uvicorn `app.main:application` on `127.0.0.1:8000` |
| optional `EnvironmentFile` | `/opt/twerva/database_url.env` |
| nginx + Let’s Encrypt | TLS for `twerva.com`; **public** `location = /health` only → uvicorn |
| `/opt/twerva/docker-compose.postgres.yml` | Docker Postgres 16 |
| `/opt/twerva/postgres/` | Postgres data directory |
| `/opt/twerva/artifacts` | Local carousel PNG store (1.4). `ARTIFACT_STORAGE_DIR`. Not public. |
| Postgres bind | `127.0.0.1:5432` only (not public) |

## Public surface (`/health` only)

**Standing decision (Mu accepted Sparky’s recommendation):** nginx’s
public surface on `https://twerva.com` is **`/health` only**.

Live nginx already proxies `location = /health` to uvicorn on
`127.0.0.1:8000`. Do **not** add public `location` blocks for `/api/`,
`/docs`, or other uvicorn paths until the API has auth — or Mu
explicitly revisits.

`/api/v1` currently has **no auth** and includes POSTs. Treat it as
private: on-box loopback, or an SSH tunnel. Same for FastAPI `/docs`.

| URL | Who can reach it |
|---|---|
| `https://twerva.com/health` | Public. nginx exact `/health` → uvicorn |
| `http://127.0.0.1:8000/health` | On-box (same process Badger monitors) |
| `http://127.0.0.1:8000/api/v1/...` | Private. Loopback or SSH tunnel |
| `http://127.0.0.1:8000/docs` | Private. FastAPI Swagger; not public |
| `https://twerva.com/api/...` | Must stay **unreachable** via nginx |
| `https://twerva.com/docs` | Must stay **unreachable** via nginx |

Off-box API access is a tunnel to loopback, not a new nginx location:

```bash
ssh -i ~/.ssh/twerva-key.pem -L 8000:127.0.0.1:8000 ubuntu@3.19.233.237
```

Then `http://127.0.0.1:8000/api/v1/...` and `/docs` on your machine.
Do not paste production payloads or env files into chat.

## Secrets (paths only)

Mode **600**. **Never** commit, print, or paste these files.

| Path | Role |
|---|---|
| `/opt/twerva/database_url.env` | `DATABASE_URL` for the API and Alembic |
| `/opt/twerva/postgres.env` | Docker Postgres credentials |

### Phase 1.3 env vars (Spotmu ingest)

`SPOTMU_API_BASE_URL` is **optional** and **not a secret**. Default is
`https://spotmu.com` (locked in
[`docs/reports/task_1_3_ingest_spike.md`](../reports/task_1_3_ingest_spike.md)).
The API process uses it to GET public JSON
`/api/v1/interests/slug/{slug}` and `/sitemap.xml`. Production can rely
on the default. To set it explicitly, add a line to an existing mode-600
env file systemd already loads, or a second `EnvironmentFile=` — do not
invent a new nginx location.

**Do not** add public nginx `/api/` (or `/docs`) for ingest. `/api/v1`
stays loopback / SSH tunnel. `GET /health` is still the only public
path. No new Alembic revision in 1.3 (`12bk_domain_schema` remains
head). After sync, `pip install -r requirements.txt` so **httpx** lands
in `.venv`, then restart `twerva-api`.

### Phase 1.4 env vars (carousel generate)

`ARTIFACT_STORAGE_DIR` is **optional** and **not a secret**. Default is
`/opt/twerva/artifacts`. Before first generate:

```bash
sudo mkdir -p /opt/twerva/artifacts
sudo chown ubuntu:ubuntu /opt/twerva/artifacts
```

Match ownership to whichever user runs `twerva-api` if that is not
`ubuntu`. Disk will grow: each generate keeps a new Artifact row **and**
a new PNG folder (history on purpose). Watch free space next to the
Postgres data volume.

**Do not** add public nginx `/api/` (or `/docs`, or `/artifacts`).
`/api/v1` stays loopback / SSH tunnel. `GET /health` is still the only
public path. No new Alembic revision in 1.4 (`12bk_domain_schema`
remains head). After sync, `pip install -r requirements.txt` so
**Pillow** lands in `.venv`, then restart `twerva-api`.

### Phase 1.5 (approval & schedule)

No new host deps, env vars, or Alembic revision. Sync the app tree and
`sudo systemctl restart twerva-api`. Optional loopback smoke:
`tools/smoke_1_5_approve_schedule.sh` (seed/generate; no Spotmu, no
real publish). Still no public nginx `/api/`.

### Phase 1.6 (publish adapter)

No new host deps or Alembic revision. Default `PUBLISH_ADAPTER=mock`
(CI-safe, no vendor keys). Optional `AYRSHARE_API_KEY` is unused until
live HTTP is wired — do **not** switch the adapter to `ayrshare` on the
box yet. Sync the app tree and `sudo systemctl restart twerva-api`.
Optional loopback smoke: `tools/smoke_1_6_publish.sh` (seed/generate/
approve/schedule/mock publish; no Spotmu, no vendor signup). Still no
public nginx `/api/`.

The app does not open `database_url.env` itself. systemd may load it as
`EnvironmentFile=`, or a shell must `source` it before Alembic. Local
override and URL rewrite rules: [`apps/server/README.md`](../../apps/server/README.md).

RDS, S3, and Secrets Manager / SSM are **deferred**. Phase 1 secrets
stay on this box.

## Deploy (until scripts exist)

Record the git revision you are shipping (usually `origin/main`) so
rollback has a target.

### 1. Sync the app tree

From a clone at the intended revision, copy `apps/server` into
`/opt/twerva/server`. Preserve `.venv`. Do not overwrite the on-box env
files under `/opt/twerva/*.env`.

Illustrative rsync (not an official script; exclude the virtualenv):

```bash
rsync -a --delete \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  --exclude '.env' \
  apps/server/ ubuntu@3.19.233.237:/opt/twerva/server/
```

Equivalent: tar the same tree, extract on the box, keep `.venv`.

### 2. Virtualenv and dependencies

On the box:

```bash
cd /opt/twerva/server
source .venv/bin/activate
pip install -r requirements.txt
```

Recreate `.venv` only when the Python version or dependency set has
changed. After recreate, `pip install -r requirements.txt` again.
**1.3 adds `httpx`** — a routine `pip install -r requirements.txt` is
enough; no venv recreate required.
**1.4 adds `pillow`** — same: routine `pip install -r requirements.txt`,
then restart. Also `mkdir -p /opt/twerva/artifacts` (writable by the
API user). Do not recreate the venv just for Pillow.

### 3. Migrate (when revisions exist)

Load the on-box URL, then upgrade from the app tree so `alembic.ini` and
`app.settings` resolve.

```bash
set -a && source /opt/twerva/database_url.env && set +a
cd /opt/twerva/server && alembic upgrade head
```

Head after tasks **1.2b–k**: revision **`12bk_domain_schema`**.

Confirm before and after:

```bash
alembic heads
alembic current
```

Expected after a clean apply: `12bk_domain_schema (head)`.

Live apply of this revision may still be pending — see
[`docs/reports/task_1_2_report.md`](../reports/task_1_2_report.md)
(1.2k-iii). Do not skip `alembic current` after upgrade.

Local Alembic (your own `DATABASE_URL`, not production secrets):
[`apps/server/README.md`](../../apps/server/README.md).

### 4. Restart the API

```bash
sudo systemctl restart twerva-api
```

### 5. Verify

```bash
curl -sf http://127.0.0.1:8000/health
curl -sf https://twerva.com/health
```

Both must print:

```json
{"status":"ok"}
```

Those are the **only** public verify curls. Do not expect
`https://twerva.com/api/...` or `https://twerva.com/docs` to hit
uvicorn — see [Public surface](#public-surface-health-only). On-box
`/api/v1` and `/docs` stay on `http://127.0.0.1:8000`.

Then check the rest of [Health](#health-expectations).

## Rollback

1. Redeploy the **previous** app tree / git commit into
   `/opt/twerva/server` (same sync rules: preserve `.venv`).
2. `sudo systemctl restart twerva-api`.
3. Re-run the [verify](#5-verify) curls.

**Database:** downgrade only if the target revision is known safe.
Prefer a **forward** migration or a forward code fix.

`12bk_domain_schema` is the first revision (`down_revision` is empty).
`alembic downgrade base` drops the whole 1.2 domain schema. Do not do
that on production unless Mu has explicitly approved destroying those
tables.

## Health expectations

`GET /health` is **liveness only**. It does not open Postgres and does
not import models or `app.db`. A `{"status":"ok"}` body means uvicorn is
up, not that the database is reachable.

Also watch:

| Check | Expectation |
|---|---|
| systemd `twerva-api` | active after restart; review `journalctl -u twerva-api` on failure |
| Postgres 16 container | healthy; compose file `/opt/twerva/docker-compose.postgres.yml`; data in `/opt/twerva/postgres/`; listen `127.0.0.1:5432` only |
| Disk | box has free space (data volume under `/opt/twerva/postgres/` grows; carousel PNGs under `/opt/twerva/artifacts` grow on each generate) |
| TLS | Let’s Encrypt cert for `twerva.com`; **alert if expiry is under 14 days** |

nginx `location = /health` must keep proxying to uvicorn. A public
`https://twerva.com/health` failure with a passing loopback curl points
at nginx/TLS, not the app. Do not “fix” that by widening nginx to
`/api/` or `/docs`.

Database connectivity (not `/health`): `alembic current` after sourcing
`/opt/twerva/database_url.env`, as in
[`apps/server/README.md`](../../apps/server/README.md).

## Landmines

Ask **Mu** before any of:

- AWS spend
- Security-group changes that can lock us out of SSH
- Destroying EBS volumes, the Postgres data dir, or the Twerva EIP
- Exposing `/api/` or `/docs` (or any other uvicorn path) on public
  nginx — even a “temporary” location

Never:

- Touch Spotmu’s EIP **`3.146.63.53`**
- Put secrets in git or chat (`database_url.env`, `postgres.env`,
  `DATABASE_URL` values, key material)
- Bind Postgres on a public interface
- Overwrite `/opt/twerva/server/.venv` as part of a routine sync
- Treat `/health` as proof the schema or `DATABASE_URL` is good
- Add public nginx `/api/` or `/docs` while `/api/v1` has no auth
  (POSTs included)

Deferred (do not provision in this runbook): RDS, S3, Secrets Manager /
SSM. Same Spotmu AWS account is fine; this file does not describe
console setup. **1.4 uses local disk**, not S3.

## Related notes

Do not copy large report text here. Use these for schema and local-dev
detail:

- [`apps/server/README.md`](../../apps/server/README.md) — local run,
  `DATABASE_URL`, Alembic smoke (`1.2a-v`)
- [`docs/reports/task_1_2_report.md`](../reports/task_1_2_report.md) —
  revision `12bk_domain_schema`, apply commands, live apply status
- [`docs/reports/task_1_2a_report.md`](../reports/task_1_2a_report.md) —
  DB plumbing (settings, engine, empty Alembic chain at 1.2a)
- [`docs/reports/task_1_3_report.md`](../reports/task_1_3_report.md) —
  Spotmu ingest, `httpx`, `/health`-only reminder
- [`docs/reports/task_1_4_report.md`](../reports/task_1_4_report.md) —
  carousel generate, local `ARTIFACT_STORAGE_DIR`, Pillow
- [`docs/reports/task_1_5_report.md`](../reports/task_1_5_report.md) —
  approval, UTC cadence caps, `POST /api/v1/schedule`
- [`docs/reports/task_1_6_report.md`](../reports/task_1_6_report.md) —
  mock PublishAdapter, `POST /api/v1/publish/run/{post_job_id}`
- [`docs/planning/task_sheet.md`](../planning/task_sheet.md) — §1.1 host
  facts; parking lot for S3 and Secrets Manager
