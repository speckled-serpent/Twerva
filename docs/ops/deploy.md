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
| nginx + Let’s Encrypt | TLS for `twerva.com`; `location = /health` proxies to uvicorn |
| `/opt/twerva/docker-compose.postgres.yml` | Docker Postgres 16 |
| `/opt/twerva/postgres/` | Postgres data directory |
| Postgres bind | `127.0.0.1:5432` only (not public) |

## Secrets (paths only)

Mode **600**. **Never** commit, print, or paste these files.

| Path | Role |
|---|---|
| `/opt/twerva/database_url.env` | `DATABASE_URL` for the API and Alembic |
| `/opt/twerva/postgres.env` | Docker Postgres credentials |

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
| Disk | box has free space (data volume under `/opt/twerva/postgres/` grows) |
| TLS | Let’s Encrypt cert for `twerva.com`; **alert if expiry is under 14 days** |

nginx `location = /health` must keep proxying to uvicorn. A public
`https://twerva.com/health` failure with a passing loopback curl points
at nginx/TLS, not the app.

Database connectivity (not `/health`): `alembic current` after sourcing
`/opt/twerva/database_url.env`, as in
[`apps/server/README.md`](../../apps/server/README.md).

## Landmines

Ask **Mu** before any of:

- AWS spend
- Security-group changes that can lock us out of SSH
- Destroying EBS volumes, the Postgres data dir, or the Twerva EIP

Never:

- Touch Spotmu’s EIP **`3.146.63.53`**
- Put secrets in git or chat (`database_url.env`, `postgres.env`,
  `DATABASE_URL` values, key material)
- Bind Postgres on a public interface
- Overwrite `/opt/twerva/server/.venv` as part of a routine sync
- Treat `/health` as proof the schema or `DATABASE_URL` is good

Deferred (do not provision in this runbook): RDS, S3, Secrets Manager /
SSM. Same Spotmu AWS account is fine; this file does not describe
console setup.

## Related notes

Do not copy large report text here. Use these for schema and local-dev
detail:

- [`apps/server/README.md`](../../apps/server/README.md) — local run,
  `DATABASE_URL`, Alembic smoke (`1.2a-v`)
- [`docs/reports/task_1_2_report.md`](../reports/task_1_2_report.md) —
  revision `12bk_domain_schema`, apply commands, live apply status
- [`docs/reports/task_1_2a_report.md`](../reports/task_1_2a_report.md) —
  DB plumbing (settings, engine, empty Alembic chain at 1.2a)
- [`docs/planning/task_sheet.md`](../planning/task_sheet.md) — §1.1 host
  facts; parking lot for S3 and Secrets Manager
