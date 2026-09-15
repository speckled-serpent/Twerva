# Twerva ops

Vite + React + TypeScript ops console for the Phase 1 loop:

```
source → generate carousel → approve → schedule → mock publish → measure / steer
```

Ugly-but-usable. No auth. Requires **Node.js 20+** (22 is fine).

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

Open [http://127.0.0.1:5173](http://127.0.0.1:5173).

### Walk the loop in the browser

1. **Sources** — list (or create) a source item → **Generate carousel**
   (optional cluster so schedule can match the account’s cluster).
2. **Queue** — edit caption if needed → **Approve** (or Reject).
3. **Accounts** — create a cluster + account if none exist (set
   `cadence_cap_per_day` if you want the cap enforced).
4. **Schedule** — pick the approved artifact + account + time → **Schedule**
   → **Mock publish** on the new post job.
5. **Results** — pick the cluster → median summary + agent-summary pane.
   **POST stub metrics** on a mock-published job (`platform_post_id` starts
   with `mock-`) so `median_views` is no longer null. Steer buttons live on
   **Accounts**.

API errors render as plain text under the page heading.

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
stripped. CORS is not required when using the proxy.

```bash
# optional — skip unless you are not using the proxy
cp .env.example .env
# VITE_API_BASE_URL=http://127.0.0.1:8000
```

There is **no auth**. Do not point this console at a public API.

## Production build (static `dist/`)

```bash
npm run build
npm run preview
```

`npm run build` type-checks with `tsc -b`, then writes static files to
`dist/`. `vite preview` serves that folder; it does **not** include the
dev proxy, so set `VITE_API_BASE_URL` at **build** time if preview needs
the API (or put nginx in front later).

Later nginx can serve `dist/` as a private ops host. That is **not**
required tonight. Do **not** expose the ops console (or `/api`) on
`https://twerva.com` — public nginx stays `/health` only (see
[`docs/ops/deploy.md`](../../docs/ops/deploy.md)).
