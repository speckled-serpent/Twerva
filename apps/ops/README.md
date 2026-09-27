# Twerva ops

Vite + React + TypeScript ops console for the Phase 1 loop:

```
source → generate carousel → approve → schedule → mock publish → measure / steer
```

Ugly-but-usable. Operator login against `/api/v1/auth` (session cookie).
Roles: **admin** (full) and **reader** (GET-only; Account password change
still allowed). Requires **Node.js 20+** (22 is fine).

## Run locally (API + ops)

The console talks to the FastAPI process on `127.0.0.1:8000`. Start **both**.

### 1. API

From the repo, with Postgres and `DATABASE_URL` as in
[`apps/server/README.md`](../server/README.md):

```bash
cd apps/server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set DATABASE_URL; ARTIFACT_STORAGE_DIR=./data/artifacts
alembic upgrade head
python -m app.seed
uvicorn app.main:application --reload --host 127.0.0.1 --port 8000
```

`GET http://127.0.0.1:8000/health` → `{"status":"ok"}`. Interactive API docs:
[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Seed loads Brand
`spotmu` plus one example SourceItem. Create a cluster + account on the
**Accounts** page before schedule (seed does not create those).

### 2. Ops console

In a second terminal:

```bash
cd apps/ops
npm install
npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). Sign in (bootstrap
admin from `OPS_ADMIN_USERNAME` / `OPS_ADMIN_PASSWORD` after
`python -m app.auth.bootstrap`). Rotate the bootstrap password on
**Account**. Admins create more operators on **Users**. Unauthenticated
`/api/v1` is 401; `GET /auth/me` 401 sends you back to the login page.

### Walk the loop in the browser

1. **New Campaign** — Spotmu + carousel + platforms + accounts + live
   Spotmu interest search. Saves `ready` only — no generate on this page.
   Success opens the new campaign on **Campaigns**.
2. **Campaigns** — list all campaigns; open a row for details and
   Start / Pause / Resume / Finish (admin). Readers see data only.
3. **Create Theme** / **Themes** — save a carousel theme (name required,
   advertisement type locked to Carousel) and list it. Seeded Spotmu
   Paper v1 and Bold v1 appear after `alembic upgrade head`. Readers
   can list; only admins can create.
4. **Queue** — edit caption if needed → **Approve** (or Reject).
5. **Accounts** — create a cluster + account if none exist (set
   `cadence_cap_per_day` if you want the cap enforced).
6. **Schedule** — pick the approved artifact + account + time → **Schedule**
   → **Mock publish** on the new post job.
7. **Results** — pick the cluster → median summary + agent-summary pane.
   **POST stub metrics** on a mock-published job (`platform_post_id` starts
   with `mock-`) so `median_views` is no longer null. Steer buttons live on
   **Accounts**.

API errors render as plain text under the page heading (403 writes say
the role is read-only). **Log out** and the current **role** are in the
header. All fetches use `credentials: "include"`.

Agent dry-run (generate drafts, **stop before approve**):
[`docs/agents/playbook_batch_generate_spotmu_cluster.md`](../../docs/agents/playbook_batch_generate_spotmu_cluster.md)
and `tools/agent_batch_generate.sh`.

## How the console reaches the API

Two options. **Prefer the Vite proxy for local `npm run dev`.**

| Mode | When | What happens |
|---|---|---|
| Vite proxy (default) | `VITE_API_BASE_URL` unset | Browser calls `/api/...` and `/health` on `:5173`. Vite forwards to `http://127.0.0.1:8000`. |
| Explicit origin | `VITE_API_BASE_URL` set | Browser calls that origin directly (`http://127.0.0.1:8000` locally, or an SSH tunnel). |

Copy [`.env.example`](.env.example) to `.env` only if you need the explicit
origin (Vite preview against a remote API, etc.). Trailing slashes are
stripped. CORS is not required when using the proxy. If you skip the
proxy and call another origin, the API must list that origin in
`OPS_CORS_ORIGINS` and allow credentials.

```bash
# optional — skip unless you are not using the proxy
cp .env.example .env
# VITE_API_BASE_URL=http://127.0.0.1:8000
```

Production on `https://twerva.com` is same-origin `/api` (no Vite
proxy). Leave `VITE_API_BASE_URL` unset when running `npm run build`.

## Production build (static `dist/`)

```bash
npm run build
npm run preview
```

`npm run build` type-checks with `tsc -b`, then writes static files to
`dist/`. **Production:** copy `dist/` to `/var/www/twerva-ops` and let
nginx serve `/` plus proxy `/api/` (see
[`docs/ops/deploy.md`](../../docs/ops/deploy.md)). Do **not** set
`VITE_API_BASE_URL` for that build.

`vite preview` does **not** include the dev proxy. For a local preview
against uvicorn, either put a proxy in front or set
`VITE_API_BASE_URL` at **build** time (that baked origin is **not**
what we deploy to `twerva.com`).
