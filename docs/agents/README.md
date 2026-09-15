# Twerva agent hooks (Phase 1)

How agents (Sparky, Canary, and later loops) draft artifacts, stop at
the human approval gate, and **propose** steer — without guessing
routes.

Product loop: `docs/prompts/product.md` §II / §VIII. Build order:
`docs/planning/task_sheet.md` §1.9. Interactive API:
[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) when the
local process has `DATABASE_URL`.

There is **no auth**. `/api/v1` is loopback or an SSH tunnel only.
Public nginx on `https://twerva.com` stays `/health` only
(`docs/ops/deploy.md`).

---

## Role split (locked for Phase 1)

| Who | May do | Must not do |
|---|---|---|
| **Agent** | Ingest/sync sources, generate **draft** carousels, read queues/metrics, write a steer **proposal** from `agent-summary` | Auto-approve, auto-reject, schedule, publish, or `POST .../steer` unless a human already ratified the action |
| **Human** | Approve / reject / edit caption on **Queue**; schedule + mock-publish on **Schedule**; apply steer on **Accounts** | Skip the gate for live-looking drafts |

`POST /api/v1/clusters/{id}/steer` **applies** pause/kill/resume
immediately (`is_active` flips). That is not a proposal inbox. Agents
propose in text (or a PR/comment) from the summary; humans POST or use
the ops buttons.

Phase 2.5 is “agents propose weekly steer; humans ratify; system
applies.” Do not start that work from this folder.

Dry-run playbook (generate, then stop):
[`playbook_batch_generate_spotmu_cluster.md`](playbook_batch_generate_spotmu_cluster.md).
Helper: [`tools/agent_batch_generate.sh`](../../tools/agent_batch_generate.sh).

---

## Draft artifacts

Each generate creates a **new** `Artifact` row (`status=draft`,
`format=carousel`). Re-generate keeps history; it does not replace the
previous draft.

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/generate/carousel \
  -H 'Content-Type: application/json' \
  -d '{"source_item_id":"<uuid>","cluster_id":"<uuid-or-omit>"}'
```

- `source_item_id` is required.
- Pass `cluster_id` when the source is on a lane so Queue / Results /
  `agent-summary` see the draft on that cluster.
- PNGs land under `ARTIFACT_STORAGE_DIR` (`slides[].asset_ref`).
- Caption + CTA come from the 1.4 template
  (`docs/planning/carousel_template_v1.md`).

**Ops:** **Sources** — list/create a source, generate carousel
(optional cluster). There is **no ingest UI**; ingest stays API/CLI.

Seed-only DBs have Brand `spotmu` plus SourceItem `external_key=example`
(`python -m app.seed`). That row is fake; prefer a real ingest when
Spotmu is up.

---

## Human approval gate

Drafts are not schedulable. `POST /api/v1/schedule` returns **409**
unless `status=approved`.

| Action | Route | Notes |
|---|---|---|
| List review queue | `GET /api/v1/artifacts?status=draft` | Newest first |
| Edit caption / CTA | `PATCH /api/v1/artifacts/{id}` | Draft or approved only |
| Approve | `POST /api/v1/artifacts/{id}/approve` | Optional `{"caption":"..."}`; sets `approved_at` |
| Reject | `POST /api/v1/artifacts/{id}/reject` | Terminal. Optional `reason` is **ignored** (no column) |

Transitions: `draft → approved | rejected`; `approved → rejected`.
Rejected cannot be re-approved — generate a new artifact
(`docs/planning/domain_statuses.md`).

**Ops:** **Queue**.

Batch-generate playbooks **stop here**. Do not chain approve in a
script unless a human is driving that step.

---

## After the gate (not part of the dry-run)

Humans (or a later, explicit runbook) continue:

| Step | Route | Ops page |
|---|---|---|
| Schedule | `POST /api/v1/schedule` `{artifact_id, account_id, scheduled_for}` | **Schedule** |
| Mock publish | `POST /api/v1/publish/run/{post_job_id}` | **Schedule** (mock-publish button) |
| Enter metrics | `POST /api/v1/post-jobs/{id}/metrics` | — |
| Stub metrics (mock ids only) | `POST /api/v1/post-jobs/{id}/metrics/stub` | **Results** |
| Cluster median | `GET /api/v1/clusters/{id}/metrics/summary` | **Results** |

Default `PUBLISH_ADAPTER=mock`. Fake platform ids look like
`mock-{platform}-{post_job.id}`. Live Ayrshare is **not** wired
(`docs/reports/task_1_6_publish_spike.md`). Cadence caps:
UTC day of `scheduled_for` vs `accounts.cadence_cap_per_day` (null = no
cap; at/over cap → 409).

**Ops:** **Accounts** to create a cluster + account if seed did not.

---

## Propose steer

Read, then write a recommendation. Do **not** POST steer as the
proposal step.

```bash
curl -sS "http://127.0.0.1:8000/api/v1/clusters/<cluster-id>/agent-summary"
curl -sS "http://127.0.0.1:8000/api/v1/clusters/<cluster-id>/agent-summary?format=markdown"
curl -sS "http://127.0.0.1:8000/api/v1/clusters/<cluster-id>/metrics/summary"
```

JSON includes `is_active`, `metrics.median_views` (`null` when empty —
not zero), recent artifacts / post jobs / steer actions (cap 10).

When a human ratifies, apply with `created_by` set to the agent name
(not the default `human`):

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/clusters/<cluster-id>/steer \
  -H 'Content-Type: application/json' \
  -d '{"action":"pause","reason":"median below floor","created_by":"sparky"}'
```

`action`: `kill` | `pause` | `double_down` | `resume`. Pause/kill set
`clusters.is_active=false`; resume sets true; **double_down is
log-only** (no cadence bump). Account `status` is not flipped.

**Ops:** steer buttons on **Accounts**; median + markdown pane on
**Results**.

---

## Key `/api/v1` routes

No auth. Prefix is `/api/v1`. Health is **not** under v1:
`GET /health`.

### Sources / ingest

| Method | Path | Agent use |
|---|---|---|
| GET | `/brands` | Find Brand `slug=spotmu` |
| POST | `/brands` | Create if missing (409 if slug taken) |
| GET | `/source-items` | List raw material |
| POST | `/source-items` | Manual/fake source (offline) |
| POST | `/ingest/spotmu/interests/{slug}` | Fetch+upsert one live interest |
| POST | `/ingest/spotmu/sync` | `{slugs?:[], limit?:int}` sitemap or explicit list |
| POST | `/clusters` | Create lane (`slug=spotmu-general` recipe) |
| GET | `/clusters` | List; includes `source_item_ids` |
| GET | `/clusters/{id}` | One cluster + linked source ids |
| POST | `/clusters/{id}/source-items/{source_item_id}` | Attach (idempotent) |
| DELETE | `/clusters/{id}/source-items/{source_item_id}` | Detach |

CLI ingest: `python -m app.ingest.spotmu_interest <slug>` from
`apps/server`.

### Generate / gate

| Method | Path | Agent use |
|---|---|---|
| POST | `/generate/carousel` | **Draft** carousel (this is the generate hook) |
| GET | `/artifacts?status=draft` | Review queue |
| GET | `/artifacts/{id}` | One artifact |
| PATCH | `/artifacts/{id}` | Caption/CTA (human or assisted) |
| POST | `/artifacts/{id}/approve` | **Human gate** |
| POST | `/artifacts/{id}/reject` | **Human gate** |

### Schedule / publish / measure / steer

| Method | Path | Agent use |
|---|---|---|
| POST | `/schedule` | After approve only |
| GET | `/post-jobs` | Calendar list |
| POST | `/publish/run/{post_job_id}` | Mock publish (default) |
| POST | `/post-jobs/{id}/metrics` | Manual snapshot |
| POST | `/post-jobs/{id}/metrics/stub` | Mock `platform_post_id` only |
| GET | `/clusters/{id}/metrics/summary` | Median views |
| GET | `/clusters/{id}/agent-summary` | Proposal input (`?format=markdown`) |
| POST | `/clusters/{id}/steer` | Apply after human ratify |

Persist-proof `POST /artifacts` and `POST /post-jobs` still exist from
1.2l. They do **not** run generate, approval, cadence, or the publish
adapter. Agents should use the loop routes above.

---

## Ops console pages

Local Vite UI (`apps/ops`). No react-router — five nav buttons.

| Nav | File | Loop step |
|---|---|---|
| **Sources** | `apps/ops/src/pages/SourcesPage.tsx` | List/create sources; generate carousel |
| **Queue** | `apps/ops/src/pages/QueuePage.tsx` | Human gate (approve / reject / caption) |
| **Schedule** | `apps/ops/src/pages/SchedulePage.tsx` | Schedule + mock publish |
| **Accounts** | `apps/ops/src/pages/AccountsPage.tsx` | Clusters, accounts, cadence cap, **steer** |
| **Results** | `apps/ops/src/pages/ResultsPage.tsx` | Median, stub metrics, agent-summary |

How to run: [`apps/ops/README.md`](../../apps/ops/README.md) and
[`docs/reports/phase_1_exit_report.md`](../reports/phase_1_exit_report.md).

Open [http://127.0.0.1:5173](http://127.0.0.1:5173) with the API on
`:8000`.

---

## Local API origin

```bash
export TWERVA_API_BASE_URL=http://127.0.0.1:8000
```

Smoke scripts and the batch-generate helper use that variable (default
loopback). Do not point them at `https://twerva.com` — `/api` is not
public.

---

## Out of scope

- New product features or agent-only API routes (1.9 is docs + a thin
  script)
- Phase 2 (bulk ingest, live vendor publish, weekly agent steer loop)
- Auto-approve / unattended publish
