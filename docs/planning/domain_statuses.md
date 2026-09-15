# Domain statuses and closed vocabularies

*Locked in task 1.2b–1.2k. In-code source: `apps/server/app/models/enums.py`.*

## Storage approach

**Native Postgres ENUM types** for every closed vocabulary (statuses,
platform, source type, steer action). Not check-constrained text.

Why this side of the 1.2b fork:

- The Phase 1 sets are small and stable.
- `\dT` and column definitions show the allowed values.
- SQLAlchemy `Enum(..., native_enum=True, values_callable=...)` persists
  the lowercase `.value` strings (`draft`, not `DRAFT`).

Adding a value later is `ALTER TYPE ... ADD VALUE` in a new Alembic
revision. Do not switch a type to free text without a dedicated migration.

1.2j listed steer `action` as “text check in (…)”. The same closed set is
enforced by ENUM `steer_action_type` (`kill`, `pause`, `double_down`,
`resume`) so the schema has one constraint style.

## UUID primary keys

Every domain table uses Postgres `UUID` with server default
`gen_random_uuid()`. Documented on the `app.models` package. The first
domain revision (`12bk_domain_schema`) runs
`CREATE EXTENSION IF NOT EXISTS pgcrypto` so the function exists on
images that only expose it via that extension.

## ArtifactStatus (`artifact_status`)

| Value | Role |
|---|---|
| `draft` | Generated or hand-entered; not publishable yet |
| `approved` | Human gate passed; eligible to schedule |
| `rejected` | Terminal for MVP |

Allowed transitions (also `ARTIFACT_STATUS_TRANSITIONS`):

- `draft` → `approved`
- `draft` → `rejected`
- `approved` → `rejected`

`rejected` is terminal. The database stores the string only; 1.5
review routes (`POST .../approve`, `POST .../reject`) enforce the graph.
Re-approve of a rejected row is not allowed — generate a new Artifact.

## PostJobStatus (`post_job_status`)

| Value | Role |
|---|---|
| `scheduled` | Queued for a time / account |
| `publishing` | Adapter in flight |
| `published` | Platform accepted the post |
| `failed` | Publish (or later) error; `last_error` may be set |
| `measured` | At least one metric pull recorded as complete |

Happy path: `scheduled` → `publishing` → `published` → `measured`.

Failure and retry (locked 1.2b-iii):

- `publishing` → `failed`
- `published` → `failed`
- `failed` → `scheduled` (retry from the queue)
- `failed` → `publishing` (retry immediately)
- `failed` → `measured` (treat as closed after a failed publish if we
  still want a terminal measure mark — matches the written chain
  `published → failed → measured`)

`measured` is terminal. The written chain
`scheduled → publishing → published → failed → measured` is the state
order plus the failure branch, not a requirement that every job visit
`failed`.

Allowed transitions (also `POST_JOB_STATUS_TRANSITIONS`):

| From | To |
|---|---|
| `scheduled` | `publishing` |
| `publishing` | `published`, `failed` |
| `published` | `measured`, `failed` |
| `failed` | `scheduled`, `publishing`, `measured` |
| `measured` | — |

## Platform (`platform`)

- `instagram`
- `tiktok`

Others later. Do not add values in 1.2.

## SourceType (`source_type`)

- `spotmu_interest` — Phase 1 ingest (1.3)
- `brand_product` — reserved; unused in Phase 1
- `editorial_brief` — reserved; unused in Phase 1

Do not build brand-product or editorial-brief flows in 1.2.

## AccountStatus (`account_status`)

- `active`
- `paused`
- `disabled`

## SteerActionType (`steer_action_type`)

- `kill`
- `pause`
- `double_down`
- `resume`

Stub table only. No HTTP API in 1.2b–k.

## Account uniqueness (1.2f-ii)

Unique on (`platform`, `handle`). The same handle may exist on another
platform. `external_account_id` is not part of the unique key.

## Source item uniqueness (1.2d-ii)

Partial unique index `uq_source_items_brand_type_external_key` on
(`brand_id`, `source_type`, `external_key`) **where `external_key` is not
null**. Rows with a null external key do not collide.

## Metric snapshots (1.2i-i)

Multiple rows per `post_job_id` are allowed. There is **no** unique
constraint on `post_job_id` (that would collapse history).

**Latest-wins:** queries that need “current” metrics for a post job take
the row with the greatest `captured_at`:

```sql
SELECT *
FROM metric_snapshots
WHERE post_job_id = :post_job_id
ORDER BY captured_at DESC
LIMIT 1;
```

Use index `ix_metric_snapshots_post_job_id` plus the sort. Cluster
medians (1.7) are queries over this grain, not a second stored table.

## Cadence caps (1.5b)

`accounts.cadence_cap_per_day` null means no cap. The schedule helper
counts existing `post_jobs` for that account whose `scheduled_for` falls
on the **UTC calendar day** of the proposed time and whose status is not
`failed`. Meeting or exceeding the cap is HTTP 409.

## Schedule coherence (1.5c)

`POST /api/v1/schedule` requires Artifact `approved`. The Account's
Cluster `brand_id` must match the Artifact brand. When the Artifact has
`cluster_id` set, the Account must belong to that cluster; when it is
null, any Account under the same brand is allowed.

## Publish (1.6)

`POST /api/v1/publish/run/{post_job_id}` runs a `scheduled` or `failed`
PostJob through `PublishAdapter` (default **mock**). In-memory
`publishing`, then commit `published` (platform id/URL + `published_at`)
or `failed` (`last_error`). Crash during the adapter leaves the previous
committed status (usually `scheduled`).

Retry is the same endpoint on a `failed` row (no Redis, no backoff
sleep). Already `published` / `measured` / `publishing` is HTTP 409.

`PUBLISH_ADAPTER=mock` (default) writes deterministic fake ids
(`mock-{platform}-{post_job.id}`). `ayrshare` is selected only when
`AYRSHARE_API_KEY` is set; live HTTP is **not** wired in 1.6 (see
`docs/reports/task_1_6_publish_spike.md`).
