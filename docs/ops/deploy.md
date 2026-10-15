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
| systemd `twerva-api` | uvicorn `app.main:application` on `127.0.0.1:8000` (loopback only) |
| optional `EnvironmentFile` | `/opt/twerva/database_url.env` (add ops auth vars here, or a second file) |
| optional ops auth env | `/opt/twerva/ops_auth.env` (mode 600) if secrets are split from the DB URL |
| nginx + Let’s Encrypt | TLS for `twerva.com`; static ops at `/`; proxy `/api/` and `/health` |
| `/var/www/twerva-ops` | Production `apps/ops` `dist/` (replaces the old stub page) |
| `/opt/twerva/docker-compose.postgres.yml` | Docker Postgres 16 |
| `/opt/twerva/postgres/` | Postgres data directory |
| `/opt/twerva/artifacts` | Local carousel PNG store (1.4). `ARTIFACT_STORAGE_DIR`. Not public. |
| Postgres bind | `127.0.0.1:5432` only (not public) |

## Public surface (ops console + authenticated `/api`)

`https://twerva.com` is the **ops console**. nginx serves the Vite
`dist/` at `/` and proxies `/api/` plus `/health` to uvicorn on
loopback. **Do not** bind uvicorn on a public interface. **Do not**
proxy FastAPI `/docs` (or `/redoc`, `/openapi.json`).

`/api/v1` (except `/api/v1/auth/login`, `/logout`, `/me`) requires a
signed httpOnly session cookie. Unauthenticated `/api/v1` calls return
**401**. Signed-in **readers** may `GET` `/api/v1` (except user-admin
routes) and may `POST /auth/change-password` / `/logout`; other writes
are **403**. **Admins** keep full access, including user create. `GET
/health` stays public and does not open Postgres.

| URL | Who can reach it |
|---|---|
| `https://twerva.com/` | Public HTML/JS for the ops console. Login required to use `/api`. |
| `https://twerva.com/health` | Public. nginx `/health` → uvicorn |
| `https://twerva.com/api/v1/auth/*` | Public login / logout / me (me is 401 without a cookie) |
| `https://twerva.com/api/v1/...` | Cookie session required (401 otherwise) |
| `http://127.0.0.1:8000/...` | On-box only. nginx is the only public front door |
| `https://twerva.com/docs` | Must stay **unreachable** via nginx |

Same-origin cookies on `twerva.com` are enough (no CORS required in
production). Local Vite still proxies `/api` and `/health` to
`127.0.0.1:8000`.

Off-box Swagger remains a tunnel to loopback:

```bash
ssh -i ~/.ssh/twerva-key.pem -L 8000:127.0.0.1:8000 ubuntu@3.19.233.237
```

Then `http://127.0.0.1:8000/docs` on your machine. Do not paste
production payloads or env files into chat.

## Secrets (paths only)

Mode **600**. **Never** commit, print, or paste these files.

| Path | Role |
|---|---|
| `/opt/twerva/database_url.env` | `DATABASE_URL` for the API and Alembic. May also hold ops auth vars if systemd only loads this file. |
| `/opt/twerva/ops_auth.env` | Optional split file: `OPS_ADMIN_USERNAME`, `OPS_ADMIN_PASSWORD`, `SESSION_SECRET`, `SESSION_COOKIE_SECURE=true`. Mode 600. Add `EnvironmentFile=` on `twerva-api` if used. |
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

Ingest still talks to public Spotmu. After this auth slice, nginx **does**
proxy `/api/` (cookie required). Do **not** proxy `/docs`. After sync,
`pip install -r requirements.txt` so **httpx** (and later **bcrypt** /
**itsdangerous**) land in `.venv`, then restart `twerva-api`.

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

Album image intake uses the same directory. The API creates
`albums/<source_id>/<unit_id>/` on upload. No new env var and no
migration for images. The service user must be able to create
directories and files inside `/opt/twerva/artifacts`. URL import needs
outbound http(s), which Spotmu ingest already uses. Do not publish
this directory.

Resource files use the same directory at `resources/<source_id>/body.md`
or `body.txt`. That needs the Alembic revision `sources_resource_files`
(`alembic upgrade head` from `apps/server`). No new env var. The same
user must be able to create `resources/` inside the artifact directory.
`python-multipart` is already required for uploads. Restart
`twerva-api` after the migration.

Theme picture and image pickers read albums that are already in the
database. No new Alembic revision and no new env var. `theme-defaults/`
still comes from the package. An uploaded album file is read from
`ARTIFACT_STORAGE_DIR` by theme preview and theme samples. Restart
`twerva-api` and the ops console after sync. `POST /api/v1/generate/carousel`
stays on the text template.

### Theme-bound sources (model change)

From `apps/server`, run `alembic upgrade head`. The new revision is
`sources_theme_bound`. No new env var. Restart `twerva-api` and replace
the ops `dist/` after sync.

The upgrade deletes resource sources and their `resource_files` rows.
It deletes every other source except the Default album when none of
that source's image paths are stored on a theme background, a theme
image element, or an artifact slide. It also drops extra images on a
unit down to one, keeping a stored path when only one of them is
stored. If deleting a row would remove a path a theme or artifact
still stores, the upgrade stops and changes nothing. Clear that path
in the theme or artifact, then run the upgrade again.

The Default album (slug `default`) is kept. It is bound to Spotmu
Paper v1 when that seeded theme is still in the database, and
otherwise to the oldest theme. Its six units keep their ids and gain
names from the photo filenames. Theme pickers still list sources and
still store one concrete image path. `theme-defaults/` bytes stay in
the package.

Rows that the upgrade deletes do not delete bytes under
`ARTIFACT_STORAGE_DIR`. After a successful upgrade, leftover
`resources/` files and `albums/` files for deleted sources can be
removed by hand. Do not delete `theme-defaults/` in the package.

Downgrade to `sources_resource_files` restores `kind` and an empty
`resource_files` table. It does not restore rows the upgrade deleted.

### Unit text per theme element

From `apps/server`, run `alembic upgrade head`. The new revision is
`unit_element_texts`. No new env var. Restart `twerva-api` and replace
the ops `dist/` after sync.

The upgrade adds `unit_element_texts` and copies each unit's free text,
then its labeled field values, onto that source theme's text elements
in frame order (top, then middle, then bottom, then sort order). A
blank free text is skipped. Extra pieces have no element to land on
and are dropped. Tags are dropped. It then removes `units.free_text`,
`units.tags`, and `unit_fields`.

Downgrade to `sources_theme_bound` restores `free_text`, an empty tags
array, and an empty `unit_fields` table. The first stored value, in
that same frame order, is written back to `free_text`. Later values
are not restored.

### Unit exclusion pairs

From `apps/server`, run `alembic upgrade head`. The new revision is
`unit_exclusions`. No new env var. Restart `twerva-api` and replace
the ops `dist/` after sync.

The upgrade adds `unit_exclusions`. Each saved pair is stored in both
directions, so the unit editor on either unit lists the other by name.
Deleting a unit removes both directions. A unit cannot exclude itself,
and the other id has to be a unit in the same source.

Downgrade to `unit_element_texts` drops `unit_exclusions`. It does not
restore the pairs.

**Do not** add a public artifacts location. After sync,
`pip install -r requirements.txt` so **Pillow** lands in `.venv`, then
restart `twerva-api`.

### Phase 1.5 (approval & schedule)

No new host deps, env vars, or Alembic revision. Sync the app tree and
`sudo systemctl restart twerva-api`. Optional loopback smoke:
`tools/smoke_1_5_approve_schedule.sh` (seed/generate; no Spotmu, no
real publish). Smokes need `OPS_ADMIN_USERNAME` / `OPS_ADMIN_PASSWORD`
so they can `POST /api/v1/auth/login`.

### Phase 1.6 (publish adapter)

No new host deps or Alembic revision. Default `PUBLISH_ADAPTER=mock`
(CI-safe, no vendor keys). Optional `AYRSHARE_API_KEY` is unused until
live HTTP is wired — do **not** switch the adapter to `ayrshare` on the
box yet. Sync the app tree and `sudo systemctl restart twerva-api`.
Optional loopback smoke: `tools/smoke_1_6_publish.sh` (seed/generate/
approve/schedule/mock publish; no Spotmu, no vendor signup). Smokes need
ops login env as above.

### Phase 1.7 (measure & steer)

No new host deps, env vars, or Alembic revision. Sync the app tree and
`sudo systemctl restart twerva-api`. Optional loopback smoke:
`tools/smoke_1_7_measure_steer.sh` (metrics → median → steer →
agent-summary; no analytics vendor). Smokes need ops login env as above.

The app does not open `database_url.env` itself. systemd may load it as
`EnvironmentFile=`, or a shell must `source` it before Alembic. Local
override and URL rewrite rules: [`apps/server/README.md`](../../apps/server/README.md).

RDS, S3, and Secrets Manager / SSM are **deferred**. Phase 1 secrets
stay on this box.

### Ops auth env (public console)

Add these to the env file **systemd already loads**
(`/opt/twerva/database_url.env`) **or** a second mode-600 file
`/opt/twerva/ops_auth.env` listed as another `EnvironmentFile=` on
`twerva-api`. Do **not** commit or paste the values.

```bash
# generate on the box; do not put the result in git
openssl rand -hex 32
```

| Variable | Role |
|---|---|
| `SESSION_SECRET` | HMAC secret for the signed session cookie. Required. Rotate invalidates every session. |
| `OPS_ADMIN_USERNAME` | Bootstrap only — first `ops_users` row when the table is empty |
| `OPS_ADMIN_PASSWORD` | Bootstrap only. Never logged. Not a standing override after the first user exists |
| `SESSION_COOKIE_SECURE` | `true` on `https://twerva.com` |
| `SESSION_COOKIE_NAME` | Optional. Default `twerva_ops_session` |
| `SESSION_COOKIE_SAMESITE` | Optional. Default `lax` |
| `OPS_CORS_ORIGINS` | Optional. Local Vite origins; production same-origin does not need CORS |

After writing the file:

```bash
sudo chmod 600 /opt/twerva/database_url.env
# if split:
# sudo chmod 600 /opt/twerva/ops_auth.env
```

If you add `/opt/twerva/ops_auth.env`, edit the systemd unit so it
loads both files, then `sudo systemctl daemon-reload`.

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
**Ops web auth adds `bcrypt` and `itsdangerous`** — same: routine
`pip install -r requirements.txt`. No venv recreate.

### 3. Build and publish the ops console

From a clone at the intended revision (Node 20+). Production must use
**relative `/api`** — do **not** set `VITE_API_BASE_URL` at build time
(empty base = same-origin `/api` behind nginx; Vite proxy is local-only).

```bash
cd apps/ops
npm ci
npm run build
```

Copy `apps/ops/dist/` onto the box, replacing the stub page:

```bash
sudo mkdir -p /var/www/twerva-ops
sudo rsync -a --delete apps/ops/dist/ /var/www/twerva-ops/
```

Or rsync from your laptop to `ubuntu@3.19.233.237:/tmp/twerva-ops-dist/`
then `sudo rsync -a --delete /tmp/twerva-ops-dist/ /var/www/twerva-ops/`.

### 4. nginx (replace the stub with the console)

Keep uvicorn on `127.0.0.1:8000`. Certbot-compatible skeleton (HTTP
first; `certbot --nginx` adds `listen 443 ssl` and the HTTP→HTTPS
redirect). **Do not** add `location /docs`.

```nginx
server {
    listen 80;
    server_name twerva.com;

    root /var/www/twerva-ops;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

Reload after editing: `sudo nginx -t && sudo systemctl reload nginx`.
If certbot already manages `twerva.com`, merge the `root` / `location`
blocks into the existing 443 server and keep its `ssl_certificate`
lines.

### 5. Migrate and bootstrap the first admin

Load the on-box URL **and** ops auth vars, then upgrade from the app
tree so `alembic.ini` and `app.settings` resolve.

```bash
set -a && source /opt/twerva/database_url.env && set +a
# if split:
# set -a && source /opt/twerva/ops_auth.env && set +a
cd /opt/twerva/server && alembic upgrade head
python -m app.auth.bootstrap
```

Head after carousel preview: revision **`artifact_template_id`** (parent
`ops_users_role_rbac`). Adds nullable `artifacts.template_id`. Existing
`ops_users` rows stay as previously backfilled (`admin`). New creates
default to `reader` unless an admin sets otherwise.

Confirm before and after:

```bash
alembic heads
alembic current
```

Expected after a clean apply: `artifact_template_id (head)`.

`python -m app.auth.bootstrap` creates the first `ops_users` row when
the table is empty and `OPS_ADMIN_USERNAME` / `OPS_ADMIN_PASSWORD` are
set. The seeded row is **`admin`**. It prints the username only — never
the password. Re-running is a no-op once any operator exists (env is
**not** a password reset). Rotate the bootstrap password in the ops
**Account** page (`POST /api/v1/auth/change-password`). Create more
operators on the admin **Users** page (`POST /api/v1/auth/users`).

Startup also attempts bootstrap when `/api/v1` mounts (non-test). The
CLI is the reliable first-apply path.

Local Alembic (your own `DATABASE_URL`, not production secrets):
[`apps/server/README.md`](../../apps/server/README.md).

### 6. Restart the API

```bash
sudo systemctl restart twerva-api
```

### 7. Verify

```bash
curl -sf http://127.0.0.1:8000/health
curl -sf https://twerva.com/health
curl -sS -o /dev/null -w "%{http_code}\n" https://twerva.com/api/v1/brands
curl -sS -o /dev/null -w "%{http_code}\n" https://twerva.com/
```

Health curls must print:

```json
{"status":"ok"}
```

`/api/v1/brands` without a cookie must be **401**. `/` must be **200**
(the ops `index.html`). `/docs` must **not** be a public FastAPI page.

Then check the rest of [Health](#health-expectations). Open
`https://twerva.com`, sign in with the bootstrap admin, and confirm
Sources loads.

## Rollback

1. Redeploy the **previous** app tree / git commit into
   `/opt/twerva/server` (same sync rules: preserve `.venv`).
2. `sudo systemctl restart twerva-api`.
3. Re-run the [verify](#7-verify) curls.

**Database:** downgrade only if the target revision is known safe.
Prefer a **forward** migration or a forward code fix.

`12bk_domain_schema` is the first revision (`down_revision` is empty).
`artifact_template_id` drops only `artifacts.template_id`.
`ops_users_role_rbac` drops only the `role` column (and `ops_user_role`
enum). `ops_users_web_auth` drops `ops_users` on downgrade. `alembic
downgrade base` drops the whole 1.2 domain schema. Do not do that on
production unless Mu has explicitly approved destroying those tables.

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

nginx must keep proxying `/health` and `/api/` to uvicorn, and serving
`/var/www/twerva-ops` at `/`. A public `https://twerva.com/health`
failure with a passing loopback curl points at nginx/TLS, not the app.
Do not “fix” that by binding uvicorn on `0.0.0.0` or exposing `/docs`.

Database connectivity (not `/health`): `alembic current` after sourcing
`/opt/twerva/database_url.env`, as in
[`apps/server/README.md`](../../apps/server/README.md).

## Landmines

Ask **Mu** before any of:

- AWS spend
- Security-group changes that can lock us out of SSH
- Destroying EBS volumes, the Postgres data dir, or the Twerva EIP
- Binding uvicorn on a public interface
- Exposing FastAPI `/docs` / `/redoc` / `/openapi.json` on public nginx

Never:

- Touch Spotmu’s EIP **`3.146.63.53`**
- Put secrets in git or chat (`database_url.env`, `ops_auth.env`,
  `postgres.env`, `DATABASE_URL` values, `SESSION_SECRET`,
  `OPS_ADMIN_PASSWORD`, key material)
- Bind Postgres on a public interface
- Overwrite `/opt/twerva/server/.venv` as part of a routine sync
- Treat `/health` as proof the schema or `DATABASE_URL` is good
- Leave `/api/v1` reachable without the session cookie (auth regression)
- Set `VITE_API_BASE_URL` when building production ops (breaks
  same-origin `/api`)

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
- [`docs/reports/task_ops_web_auth_report.md`](../reports/task_ops_web_auth_report.md)
  — `ops_users`, signed session cookie, public console nginx
- [`docs/planning/phase_map.md`](../planning/phase_map.md) — what's left.
  S3 image storage is under Housekeeping. Host facts for this box stay
  in this file.
