# Twerva — local startup (Phase 1)

How to poke the Phase 1 loop. Production ops is `https://twerva.com`
(login required). Local work is still Vite + optional SSH tunnel.

For the overnight close-out packet, see [`docs/reports/phase_1_exit_report.md`](reports/phase_1_exit_report.md). Deploy the public console + auth on the box: [`docs/ops/deploy.md`](ops/deploy.md).

---

## What runs where

| Piece | Where | Notes |
|---|---|---|
| Public site | `https://twerva.com` | Ops console at `/`. nginx proxies `/api/` and `/health`. Login required for `/api/v1` (except `/auth/login` / `/logout` / `/me`). Readers are GET-only. |
| API | EC2 `twerva-server` | Code at `/opt/twerva/server` (synced `apps/server` tree, **not** a full git clone). Uvicorn on **`127.0.0.1:8000`** (not public). |
| Postgres | Same EC2 (Docker) | Bound to `127.0.0.1:5432`. Creds in `/opt/twerva/database_url.env` (mode 600 — don’t paste into chat). |
| Artifacts (carousel PNGs) | `/opt/twerva/artifacts` | Local disk; S3 still deferred. |
| Ops console (prod) | `/var/www/twerva-ops` | Vite `dist/` behind nginx. Same-origin `/api`. |
| Ops console (local) | Your machine | `~/projects/twerva/apps/ops` — Vite React. Talks to the API via Vite proxy (and optional SSH tunnel). |

Human gate: agents/scripts may **generate** drafts; **approve / schedule / publish / steer** are for you (or intentional API calls). Publish is still the **mock** adapter unless you change `PUBLISH_ADAPTER`.

---

## One-time checks

- Repo on your Arch box: `~/projects/twerva` on `main` (`git pull`).
- SSH key: `~/.ssh/twerva-key.pem` (mode `400`).
- Host: `ubuntu@3.19.233.237` (EIP for `twerva.com`).
- Node 20+ for ops (`node -v`).

Optional health from anywhere:

```bash
curl -s https://twerva.com/health
# → {"status":"ok"}
```

Open **https://twerva.com** and sign in with the bootstrap admin (set on
the box; never committed). Unauthenticated `GET /api/v1/brands` is 401.
Rotate that bootstrap password under **Account → Change password** (env
does not overwrite an existing admin). Admins create more operators
under **Users** (`admin` full, `reader` GET-only). The header shows the
current role.

---

## Start the loop (two terminals)

### Terminal 1 — tunnel the API to localhost (optional)

Needed only for local Vite against the **box** API, or for `/docs`:

```bash
ssh -i ~/.ssh/twerva-key.pem -L 8000:127.0.0.1:8000 ubuntu@3.19.233.237
```

Leave this open. Your laptop’s `http://127.0.0.1:8000` is now the box API.

Quick check (new local terminal is fine). Health is public; `/api/v1`
needs a session cookie after login:

```bash
curl -s http://127.0.0.1:8000/health
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/v1/brands
# → 401 without a cookie
```

Interactive API docs (while tunneled): http://127.0.0.1:8000/docs

Or run the API locally (`apps/server` + Postgres + `SESSION_SECRET` +
`python -m app.auth.bootstrap`) and skip the tunnel.

### Terminal 2 — ops console (local Vite)

```bash
cd ~/projects/twerva/apps/ops
npm install          # first time / after lockfile changes
npm run dev
```

Open **http://127.0.0.1:5173**

Vite proxies `/api` and `/health` to `http://127.0.0.1:8000` (local
uvicorn or the tunnel). Fetches send `credentials: "include"` so the
session cookie is stored for `:5173`. Header should show API healthy
when the tunnel + `twerva-api` are up. Sign in before Sources loads.

Local API `.env` should set `SESSION_COOKIE_SECURE=false` (HTTP) and
`OPS_ADMIN_USERNAME` / `OPS_ADMIN_PASSWORD` for the first bootstrap.

---

## Walk the Phase 1 path in ops

Nav: **Sources · Queue · Schedule · Accounts · Results · Account** (+ **Users** for admins)

1. **Sign in** — bootstrap admin (or any `ops_users` row). Role is in the header.
2. **Sources** — list Spotmu-shaped source items; generate a carousel (creates a **draft** artifact; PNGs land under `/opt/twerva/artifacts` on the server).
3. **Queue** — approve / reject / edit caption (human gate).
4. **Accounts** — clusters/accounts, cadence caps, steer (pause/kill/resume).
5. **Schedule** — attach an **approved** artifact to an account + time → `post_job`; then **mock publish**.
6. **Results** — stub/manual metrics, cluster median views, agent-summary.

Seeded Brand `spotmu` and example source may already exist; live Spotmu ingest (`ai-agents`, etc.) may also be on the box from smokes.

---

## Optional CLI smokes (on the server)

With the tunnel up you can hit the API from your laptop; scripts that need DB files/artifacts usually run **on the box**. Smokes now `POST /api/v1/auth/login` first — export the same bootstrap credentials (do not paste them into chat):

```bash
ssh -i ~/.ssh/twerva-key.pem ubuntu@3.19.233.237
set -a && source /opt/twerva/database_url.env && set +a
# if split: set -a && source /opt/twerva/ops_auth.env && set +a
cd /opt/twerva/server
# examples (see tools/ in the git repo on your machine — copy or run from a checkout):
# python -m app.ingest.spotmu_interest ai-agents
# python -m app.generate.carousel_cli <source_item_id>
```

Repo scripts live under `tools/` in git (`smoke_1_*.sh`, `agent_batch_generate.sh`). They source `tools/lib/ops_session.sh` and need `OPS_ADMIN_USERNAME` / `OPS_ADMIN_PASSWORD`. The server tree may not include `tools/`; prefer running those from your laptop against the tunneled API when the script is HTTP-only, or copy them up when needed.

---

## What’s intentionally not here yet

- OAuth / SSO (operator table + session cookie only).
- Multi-tenant product accounts (`ops_users` ≠ social `accounts`).
- Real Instagram/TikTok publish (mock only).
- Full monorepo git checkout on EC2.
- Phase 2 work — parked until after manual tweak/iterate.

When something feels wrong while you play, note it; we’ll turn those into task-sheet tweaks before Phase 2.
