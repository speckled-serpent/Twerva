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

`POST /api/v1/clusters/{id}/steer` (1.7c) appends a `steer_actions` row.

Side effects on the cluster (account rows are **not** paused/disabled in MVP):

- `kill` / `pause` → `clusters.is_active = false`
- `resume` → `clusters.is_active = true`
- `double_down` → log-only (row written; `is_active` unchanged; no cadence bump)

## Measure (1.7)

`POST /api/v1/post-jobs/{id}/metrics` appends a `metric_snapshots` row
(latest-wins still applies). Optional
`POST /api/v1/post-jobs/{id}/metrics/stub` copies documented mock
counts (`views=100`, `likes=10`, `comments=2`, `shares=1`) only when
`platform_post_id` starts with `mock-` (HTTP 409 otherwise). There is
**no** real analytics vendor pull.

A `published` or `failed` PostJob moves to `measured` when a snapshot
is stored. `scheduled` / `publishing` / already-`measured` keep their
status (snapshots are still stored).

`GET /api/v1/clusters/{id}/metrics/summary` takes each post job on
accounts in the cluster, uses the latest snapshot by `captured_at`,
and reports the **median** of non-null `views`. Empty cluster, no
snapshots, or all-null views → `median_views` is JSON `null` (not
zero). Even-length lists use the mean of the two central values
(may be a half).

`GET /api/v1/clusters/{id}/agent-summary` (`?format=json` default, or
`markdown`) returns recent artifacts, post jobs (with latest views),
the median block, and recent steer actions.

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

## Campaign (`campaign_status`)

Closed vocabularies on `campaigns` (Alembic `campaigns_create_ui`,
lifecycle values in `campaign_status_lifecycle`):

| Enum | Values |
|---|---|
| `campaign_type` | `spotmu`, `spotmu_test`, `other` |
| `advertisement_type` | `carousel` |
| `campaign_status` | `ready`, `running`, `paused`, `finished` |

Create persists a definition with status **`ready`**. `other` is
rejected by the API (`400`). `spotmu` and `spotmu_test` share the
create flow (name, carousel, platforms, ≥1 Spotmu interest). `spotmu`
also requires ≥1 linked account; `spotmu_test` may persist with an
empty `account_ids` list (provided accounts still must match the
selected platforms). `slug` and `hashtag` (`#slug`) are unique and
derived from `name`. Platforms are a JSONB list of `instagram` /
`tiktok`. Accounts and Spotmu interests live on `campaign_accounts` and
`campaign_interests`.

Existing rows stored as `not_started` (create-only slice) become
`ready` by renaming the enum value.

Start / pause / resume / finish are **status flips only** — they do not
ingest interests or generate carousels. Illegal transitions and
already-in-target actions are HTTP **400**.

Allowed transitions (also `CAMPAIGN_STATUS_TRANSITIONS`):

| Action | From | To |
|---|---|---|
| `POST .../start` | `ready` | `running` |
| `POST .../pause` | `running` | `paused` |
| `POST .../resume` | `paused` | `running` |
| `POST .../finish` | `running`, `paused` | `finished` |

`ready` cannot jump to `finished`. `finished` is terminal.

## Theme

`themes` (Alembic `themes_create`, status in `themes_status`, spacing
in `themes_spacing`, background in `themes_background`) stores visual
styling for carousels. Short video is not implemented. The table reuses
`advertisement_type` (`carousel` only).

| Enum | Values |
|---|---|
| `theme_status` | `draft`, `live` |
| `background_kind` | `picture`, `color`, `gradient`. Texture is dropped for now and may return as a default album of texture images. |

| Column | Notes |
|---|---|
| `name` | Required, operator-facing |
| `slug` | Unique, derived from `name` |
| `advertisement_type` | `carousel` |
| `template_key` | Optional unique link to a carousel generator (`spotmu_paper_v1`, `spotmu_bold_v1`). Null when the theme is not tied to a generator yet |
| `status` | `ThemeStatus`. Default `draft`. A name-only create stores `draft`. `POST /api/v1/themes` stores a present `status`. `PATCH /api/v1/themes/{id}` may set `draft` or `live` |
| `page_margin` | One integer, applied on every edge of the frame. Default **96**. `PATCH` may change it. Negative is HTTP 400 |
| `element_gap` | One integer, applied between elements. Default **0**. Negative is HTTP 400 |
| `element_margin` | One integer, applied on every edge of an element rectangle. Default **0**. Negative is HTTP 400 |
| `background_kind` | One background. Default `color`. Not null |
| `background_color` | Nullable text. Default `#F6F1E8` (paper). Hex is `#` plus six hex digits. Blank stores null |
| `background_gradient` | Nullable JSONB. Locked shape: `{"angle_deg": <0–360>, "stops": [{"offset": <0–1>, "color": "#rrggbb"}, ...]}` with at least two stops |
| `background_asset_ref` | Nullable text. Relative path, no `..`, no scheme, suffix `.svg`, `.png`, `.jpg`, or `.jpeg` |
| `created_by` | Nullable `ops_users` id |

`draft` is the style the operator is editing. `live` is the style
generation will use for posts that ship. Shipping
`POST /api/v1/generate/carousel` does not read `status` yet.

`POST /api/v1/themes` requires a non-empty name. Omitted frame fields
use the defaults. A name-only create stores `page_margin` 96,
`element_gap` 0, and `element_margin` 0, kind `color`, color
`#F6F1E8`, null gradient and asset ref, status `draft`, and zero
elements. Present `status`, spacing, background, and `elements`
fields are stored in that same write. A Live create requires the
payload for its kind. A validation error stores no row.
`DELETE /api/v1/themes/{id}` removes the theme and its elements.
Another table that referenced the theme would block the delete.
`POST /api/v1/themes/preview` renders one 1080 frame from a frame and
element payload and returns the PNG inline. It does not insert a theme,
artifact, or post job, and it does not write a preview file. Readers
may call it. `POST /api/v1/themes/{id}/samples` still renders a saved
theme and writes a preview file; that route stays admin-only.
`PATCH /api/v1/themes/{id}` may set any of those integers and the
background columns; omitted fields stay as they are. Zero is allowed.
A negative spacing value is HTTP 400 and does not write. A Draft may
save a background kind with that kind's payload still empty. A row
that is Live after the patch requires the payload for its kind: a
color hex, a valid gradient, or a non-empty asset ref for `picture`.
Readers may
`GET /api/v1/themes` and `/api/v1/themes/{id}`; writes, including
`PATCH`, stay admin-only via the existing ops RBAC gate
(`require_authenticated_ops_operator` plus the reader mutation check).
Upgrade seeds Spotmu Paper v1 and Spotmu Bold v1, then backfills every
existing row — those two included — to `draft`, spacing 96 / 0 / 0, and
paper background `#F6F1E8`.
Creating a theme does not render slides or attach a campaign.
Both `draft` → `live` and `live` → `draft` are allowed. Layout math is
not applied here.

## Theme elements (`theme_elements`)

Alembic `theme_elements` (parent `themes_background`). One row is one
full-width element. There is no `x`, `y`, or `width` column.
`theme_id` references `themes` **ON DELETE CASCADE**. Unique
(`theme_id`, `band`, `sort_order`). `rectangle_color` null means the
rectangle is clear.

`GET /api/v1/themes/{id}` includes `elements` ordered by band
(`top`, `middle`, `bottom`) then `sort_order`. Writes are
`POST /api/v1/themes/{theme_id}/elements`,
`PATCH /api/v1/themes/{theme_id}/elements/{element_id}`, and
`DELETE` on that element path. They use the same admin write gate as
`POST /api/v1/themes`. `sort_order` is 0-based within the band; the
server compacts it after a create, a move, or a delete. Unknown
`text_source` values, `x` / `y` / `width`, and image refs that are not
svg, png, or jpeg are rejected. This does not measure text or read
image bytes.

`POST /api/v1/themes/{id}/duplicate` inserts a new Draft. The name is
`Copy of {name}`. The slug comes from the existing slug helper.
`template_key` is null. Spacing, background, and every element are
copied; element ids are new and band, order, and content stay the
same. The source row is not updated.

| Enum | Values |
|---|---|
| `theme_element_band` | `top`, `middle`, `bottom` |
| `theme_element_content_kind` | `text`, `image` |
| `theme_element_text_source` | `title`, `interest_heading`, `overview_bullets`, `canonical_url` |
| `theme_element_alignment` | `left`, `center`, `right` |

`text_source` maps to `source_items.title`, `.interest_heading`,
`.overview_bullets`, and `.canonical_url`. No other source keys.

Check `ck_theme_elements_content`:

- `text` requires `text_source`, a non-blank `font_family`, `font_size`
  greater than 0, a non-blank `font_color`, and `alignment`.
- `bold`, `italic`, `underline`, and `strikethrough` are not null and
  default false.
- `font_weight` is null or an integer from 1 through 1000.
- `image` requires `image_asset_ref` and forbids `text_source`.
- `image_asset_ref`, when set, is a relative path with no `..` and no
  scheme, suffix `.svg`, `.png`, `.jpg`, or `.jpeg` (same rule as
  `background_asset_ref`).

## Content sources (`sources`)

Alembic `sources_default_album` (parent `themes_element_rectangle`),
then `sources_resource_files` (parent `sources_default_album`).
An album is a source with `kind = album` and has units. A resource has
one row in `resource_files`. Phase 1 seeds one album, slug `default`,
and does not update `themes`.

| Enum | Values |
|---|---|
| `content_source_kind` | `album`, `resource` |
| `unit_image_media_type` | `svg`, `png`, `jpeg` |
| `unit_image_license` | `cc0`, `public_domain`, `owned`, `licensed` |
| `unit_image_intake` | `upload`, `url` |
| `resource_file_media_type` | `markdown`, `plain` |

`units.tags` is a text array, default empty. `unit_images.license_note`
is empty unless `license` is `licensed`, in which case it is required.
`relative_path` is unique. SVG rows have null width, height, and
thumbnail. Readers may GET a source, the original file, and a
thumbnail when one exists. Admins may create, rename, and delete
albums and units, edit free text, fields, and tags, edit license
metadata, upload SVG/PNG/JPEG (8 MB), and import one http(s) URL.
New bytes go under `ARTIFACT_STORAGE_DIR` at
`albums/<source_id>/<unit_id>/<image_id>.<ext>`. A failure writes no
row and no file. Delete of an image, unit, or album is 409 while a
theme or artifact stores that path, including an uploaded
`albums/…` path and a packaged `theme-defaults/…` path. The theme
picture and image controls list those albums, then units that have an
image, then the images. Pick and Shuffle store one concrete path.
Samples and live preview read that path from the package for
`theme-defaults/` and from `ARTIFACT_STORAGE_DIR` otherwise.
Admins may also create a resource by uploading
a Markdown or TXT file (2 MB) with a provenance note, replace that
file, edit the note, and delete the resource. The bytes stay at
`resources/<source_id>/body.md` or `body.txt` under `ARTIFACT_STORAGE_DIR`.
Readers may open the text and download the file. They cannot upload.
