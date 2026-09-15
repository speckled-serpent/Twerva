# Playbook: batch generate from Spotmu cluster X (dry-run)

Agent dry-run for Phase 1.9a-ii. **Generate drafts, then stop.** A
human approves on **Queue** (or `POST .../approve`). This playbook does
not schedule or publish.

Companion: [`README.md`](README.md). Script:
[`tools/agent_batch_generate.sh`](../../tools/agent_batch_generate.sh).

---

## What “dry-run” means

| Does | Does not |
|---|---|
| Use sources already on cluster X, **or** ingest when Spotmu is up | Call approve / reject |
| `POST /api/v1/generate/carousel` per linked source (new **draft** each time) | `POST /api/v1/schedule` |
| Optional `GET .../agent-summary` after generate | `POST /api/v1/publish/run/{id}` |
| Print artifact ids for the human queue | `POST .../steer` (propose in text only) |

Re-generate always inserts a new Artifact (1.4d). Running the playbook
twice creates more drafts; it does not replace old ones.

---

## Prerequisites

1. Local (or tunneled) API with `DATABASE_URL` so `/api/v1` is mounted.
   `GET http://127.0.0.1:8000/health` → `{"status":"ok"}`.
2. Schema at Alembic head `12bk_domain_schema`; seed optional
   (`python -m app.seed` from `apps/server`).
3. `ARTIFACT_STORAGE_DIR` writable (local `./data/artifacts`).
4. Public nginx is `/health` only — use loopback:

```bash
export TWERVA_API_BASE_URL=http://127.0.0.1:8000
```

Cluster **X** in this recipe is Brand `spotmu` / cluster
`slug=spotmu-general` (1.3e). Override with `CLUSTER_SLUG` or
`CLUSTER_ID`.

---

## Step 0 — health + brand + cluster

```bash
curl -sS "${TWERVA_API_BASE_URL}/health"
curl -sS "${TWERVA_API_BASE_URL}/api/v1/brands"
curl -sS "${TWERVA_API_BASE_URL}/api/v1/clusters"
```

If Brand `spotmu` is missing, `POST /api/v1/brands`
`{"slug":"spotmu","name":"Spotmu"}` (or run seed). If cluster
`spotmu-general` is missing:

```bash
curl -sS -X POST "${TWERVA_API_BASE_URL}/api/v1/clusters" \
  -H 'Content-Type: application/json' \
  -d '{"brand_id":"<spotmu-brand-id>","slug":"spotmu-general","name":"Spotmu general"}'
```

`GET /api/v1/clusters/{id}` → `source_item_ids`.

---

## Step 1 — sources: existing, or ingest if Spotmu is up

**Prefer existing links.** If `source_item_ids` is non-empty, skip
ingest unless you intend a refresh (`SPOTMU_INGEST=1` on the script).

**If the cluster is empty** and Spotmu public JSON is up:

```bash
# one real slug (1.3 smoke default)
curl -sS -X POST \
  "${TWERVA_API_BASE_URL}/api/v1/ingest/spotmu/interests/ai-agents"

# or a small sitemap window
curl -sS -X POST "${TWERVA_API_BASE_URL}/api/v1/ingest/spotmu/sync" \
  -H 'Content-Type: application/json' \
  -d '{"limit": 5}'
```

Then attach each new SourceItem (same brand; idempotent):

```bash
curl -sS -X POST \
  "${TWERVA_API_BASE_URL}/api/v1/clusters/<cluster-id>/source-items/<source-item-id>"
```

CLI equivalent: `python -m app.ingest.spotmu_interest ai-agents` from
`apps/server`.

**If Spotmu is down (502/503/timeout):** do not fail the whole
playbook if a DB source exists. Attach the seed SourceItem
(`external_key=example`) or any other `GET /api/v1/source-items` row
under Brand `spotmu`, then generate from that. Note in the run log that
ingest was skipped. Full ingest smoke:
`tools/smoke_1_3_ingest.sh`.

Spotmu origin (API process, not this curl): `SPOTMU_API_BASE_URL`
default `https://spotmu.com`. JSON path is
`/api/v1/interests/slug/{slug}` — not the SPA `/interests/slug/{slug}`.

---

## Step 2 — generate carousels for cluster X

For each `source_item_id` on the cluster (cap with `MAX_SOURCES` on the
script; default 20):

```bash
curl -sS -X POST "${TWERVA_API_BASE_URL}/api/v1/generate/carousel" \
  -H 'Content-Type: application/json' \
  -d '{"source_item_id":"<source-item-id>","cluster_id":"<cluster-id>"}'
```

Expect HTTP **201**, `status=draft`, `format=carousel`, non-empty
`caption`, `slides` with `role` / `text` / `asset_ref`.

Passing `cluster_id` is required for this playbook so
`GET /api/v1/clusters/{id}/agent-summary` lists the new drafts.

---

## Step 3 — stop (human gate)

List the queue; do **not** approve:

```bash
curl -sS "${TWERVA_API_BASE_URL}/api/v1/artifacts?status=draft"
```

Hand the artifact ids to a human. They use **Queue** at
[http://127.0.0.1:5173](http://127.0.0.1:5173) or:

```bash
# human only — not this dry-run
curl -sS -X POST \
  "${TWERVA_API_BASE_URL}/api/v1/artifacts/<artifact-id>/approve" \
  -H 'Content-Type: application/json' \
  -d '{}'
```

After approve: **Schedule** → mock publish → **Results** (see
[`README.md`](README.md)). Still not this playbook.

---

## Step 4 — optional agent-summary

```bash
curl -sS "${TWERVA_API_BASE_URL}/api/v1/clusters/<cluster-id>/agent-summary"
curl -sS "${TWERVA_API_BASE_URL}/api/v1/clusters/<cluster-id>/agent-summary?format=markdown"
```

Use this to **propose** steer in prose (kill / pause / double_down /
resume + reason). Do not `POST .../steer` from the dry-run.

On a cluster that has only drafts and no measured jobs,
`median_views` is JSON `null`. That is expected.

---

## One-shot script

API already running:

```bash
# from repo root
tools/agent_batch_generate.sh
CLUSTER_SLUG=spotmu-general tools/agent_batch_generate.sh
SPOTMU_INGEST=1 SPOTMU_SMOKE_SLUG=ai-agents tools/agent_batch_generate.sh
FETCH_SUMMARY=0 MAX_SOURCES=3 tools/agent_batch_generate.sh
```

The script exits 0 after printing draft ids and a **HUMAN GATE** line.
It never calls approve.

---

## Failure notes

| Symptom | What to check |
|---|---|
| `/api/v1` 404 | Process started without `DATABASE_URL` (health-only) |
| Ingest 502/504 | Spotmu origin down or non-JSON; use existing sources |
| Generate 404 | Bad `source_item_id` / `cluster_id` |
| Generate 400 | Cluster and source brands differ |
| Empty `source_item_ids` after ingest | Forgot attach POST |
