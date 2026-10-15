# Phase 1 exit report (Mu review)

*2026-09-15*

Overnight mandate was **1.5 → 1.9**, then **stop**. This is the
morning packet. **Phase 2 is not started — awaiting Mu review.**

Task grain at the time was the task sheet, since replaced by
`docs/planning/phase_map.md`. Agent hooks: `docs/agents/README.md`.

---

## What works end-to-end (1.1–1.8)

The Phase 1 loop is implemented and smoke-tested against **local
loopback** `/api/v1` (Postgres + uvicorn). Public `twerva.com` still
exposes **`/health` only**.

```
source → generate carousel → approve → schedule → mock publish → metrics → steer
```

| Slice | What landed | How it was proven |
|---|---|---|
| **1.1** | Repo, FastAPI + Vite shells, EC2 `twerva-server`, `https://twerva.com` TLS, Docker Postgres on-box, systemd `twerva-api` | Live `GET https://twerva.com/health` → `{"status":"ok"}` (re-checked this report) |
| **1.2** | Domain schema Alembic `12bk_domain_schema`; `/api/v1` CRUD; seed Brand `spotmu` + fake SourceItem `example` | Persist-proof `tools/smoke_1_2l_api.sh`; `python -m app.seed` |
| **1.3** | Spotmu public JSON ingest + sitemap sync; `cluster_source_items` attach; cluster `spotmu-general` recipe | Unit/persist tests; typed live fetch in 1.3; `tools/smoke_1_3_ingest.sh` (needs Spotmu + loopback API) |
| **1.4** | Carousel template 1080×1080 PNG on local `ARTIFACT_STORAGE_DIR`; `POST /api/v1/generate/carousel` → **draft** | `tools/smoke_1_4_carousel.sh` (offline from Spotmu) |
| **1.5** | Review queue approve/reject/PATCH; cadence caps; `POST /api/v1/schedule` | `tools/smoke_1_5_approve_schedule.sh` |
| **1.6** | `PublishAdapter`; **mock default**; `POST /api/v1/publish/run/{id}` | `tools/smoke_1_6_publish.sh` → `mock-instagram-…` ids |
| **1.7** | Manual/stub metrics; cluster **median** views; steer pause/kill/resume (double_down log-only); `agent-summary` | `tools/smoke_1_7_measure_steer.sh` |
| **1.8** | Thin ops console: Sources · Queue · Schedule · Accounts · Results | Local Vite; 1.8 agent walked pages (health-only API in that env) |
| **1.9** | Agent docs + batch-generate dry-run playbook (this close) | Docs + `tools/agent_batch_generate.sh` |

`GET /health` still starts **without** `DATABASE_URL` (`/api/v1`
unmounted). Interactive docs: `http://127.0.0.1:8000/docs` when the
URL is set.

Coding PRs documented Badger deploy/restart; they did **not** SSH-apply
every slice on `twerva-server`. On-box procedure:
[`docs/ops/deploy.md`](../ops/deploy.md). Treat “works on box” as:
health is live; schema/API are meant to be synced from `main`; the
full loop is proven on loopback smokes, not as a public website flow.

---

## What’s mock (publish adapter)

**Publish is mock.** `PUBLISH_ADAPTER=mock` (default).
`MockPublishAdapter` always succeeds with
`platform_post_id=mock-{platform}-{post_job.id}` and
`https://example.invalid/…` URLs. No OAuth, no IG/TikTok, no Ayrshare
HTTP.

Spike lock: adapter now; first live vendor **Ayrshare** when Mu adds
`AYRSHARE_API_KEY` + connected test accounts + a public-or-uploaded
media path (`docs/reports/task_1_6_publish_spike.md`). Zernio is the
swap candidate. Native Meta/TikTok parked.

Metrics stub (`POST /api/v1/post-jobs/{id}/metrics/stub`) only accepts
those `mock-` platform ids (documented counts: views 100 / likes 10 /
comments 2 / shares 1). Real numbers are a manual POST until a vendor
insights adapter exists.

---

## Spotmu ingest live smoke status

**Path (locked 1.3a):** unauthenticated
`GET {SPOTMU_API_BASE_URL}/api/v1/interests/slug/{slug}` plus
`/sitemap.xml`. Default origin `https://spotmu.com`. SPA
`/interests/slug/{slug}` is not JSON.

**Earlier overnight:** live ingest through Twerva was blocked when
Spotmu returned **502/503** (Twerva maps upstream failures to HTTP
502/504 on ingest routes). 1.3 still shipped mocked client/upsert tests
and a typed live fetch of `ai-agents` while Spotmu was up during that
slice.

**Re-check (this report, 2026-09-15, from the coding environment):**

| URL | Result |
|---|---|
| `https://spotmu.com/api/v1/interests/slug/ai-agents` | HTTP **200**, JSON slug `ai-agents`, title `AI Agents` |
| `https://spotmu.com/sitemap.xml` | HTTP **200** (~53 KB urlset, `/interest/…` locs) |
| `https://spotmu.com/` | HTTP **200** |
| `https://twerva.com/health` | HTTP **200** `{"status":"ok"}` |

Spotmu public JSON is **up** as of this re-check. This environment has
**no Postgres**, so `tools/smoke_1_3_ingest.sh` (Twerva upsert +
cluster attach) was **not** re-run here. On-box ingest still needs
loopback/SSH tunnel to `/api/v1` after Badger has the 1.3+ tree.

If Spotmu flaps again, the 1.9 dry-run uses existing DB sources or the
seed `example` row and still stops before approve.

---

## How to run the ops console locally

Both processes. Details: [`apps/ops/README.md`](../../apps/ops/README.md)
and [`apps/server/README.md`](../../apps/server/README.md).

**1. API** (Python 3.11+, Postgres, `DATABASE_URL`):

```bash
cd apps/server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # DATABASE_URL; ARTIFACT_STORAGE_DIR=./data/artifacts
alembic upgrade head
python -m app.seed
uvicorn app.main:application --reload --host 127.0.0.1 --port 8000
```

`GET http://127.0.0.1:8000/health` → `{"status":"ok"}`.

**2. Ops** (Node 20+, second terminal):

```bash
cd apps/ops
npm install
npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). Vite proxies
`/api` and `/health` to `:8000` unless `VITE_API_BASE_URL` is set.

Walk: **Sources** (generate) → **Queue** (approve/caption) →
**Accounts** (cluster + account if needed) → **Schedule** (post job +
**mock** publish) → **Results** (stub metrics + median + agent-summary).
Steer buttons are on **Accounts**.

Do **not** expose ops or `/api` on `https://twerva.com`.

Agent dry-run (drafts only): `tools/agent_batch_generate.sh`.

---

## What Mu should review before Phase 2

1. Human gate is documented and the dry-run **stops before approve**.
2. Publish stays mock until vendor keys / accounts exist.
3. Spotmu ingest is live on the public JSON path today; confirm a
   loopback `tools/smoke_1_3_ingest.sh` on `twerva-server` when
   convenient.
4. Ops console is local-only; public surface remains `/health`.
5. Double-down is log-only; pause/kill share `is_active=false`.
6. No S3, no Celery, no auth — still MVP.

**Phase 2 not started — awaiting Mu review.** Do not pull 2.1–2.5
(bulk lanes, live publish harden, weekly agent steer) until that
happens.
