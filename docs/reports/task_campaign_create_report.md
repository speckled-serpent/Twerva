# Task — Campaign create UI

*2026-09-21*

Replace the Sources page with a **Campaigns** create/list flow.
Operators save a marketing campaign definition (name, type, carousel,
platforms, accounts, Spotmu interest bucket). Creating a campaign does
**not** start it, ingest interests, or generate carousels.

## Done

- Alembic revision **`campaigns_create_ui`** (head after
  `artifact_template_id`):
  - `campaigns`: `id`, `name`, unique `slug` + `hashtag`,
    `campaign_type` (`spotmu` | `other`), `advertisement_type`
    (`carousel`), `status` (`not_started`), `platforms` JSONB,
    optional `created_by` → `ops_users`, timestamps.
  - `campaign_accounts`: unique (`campaign_id`, `account_id`).
  - `campaign_interests`: unique (`campaign_id`, `spotmu_slug`) plus
    optional `spotmu_interest_id` / `title` snapshot.
- API (auth + existing RBAC: readers GET, admins write):
  - `GET/POST /api/v1/campaigns`
  - `GET /api/v1/campaigns/{campaign_id}`
  - `GET /api/v1/spotmu/interests/search?q=`
- Slug/hashtag are generated from the name (`My Campaign` →
  `my-campaign` / `#my-campaign`). Collisions append `-2`, `-3`, …
- `campaign_type=other` is HTTP 400 (“not implemented”). Zero accounts
  and zero interests are allowed.
- Ops console: nav **Campaigns**, list + **New Campaign** form.
  Clusters, Brand / heading / overview / URL / external-key fields, and
  generate-on-create are gone from this page.

## Spotmu live search

Probed 2026-09-21 against `https://spotmu.com` (`SPOTMU_API_BASE_URL`):

| Path | Result |
|---|---|
| `GET /api/v1/interests/search?q=ai` | **200** JSON array (guest). `limit` honored. Keys include `slug`, `title`, `interest_hash_id`. |
| `GET /api/v1/interests/autocomplete?q=ai` | **401** `Not authenticated` |
| `GET /interests/search` / `/interests/autocomplete` | **200** SPA HTML |

Locked proxy path: **`GET {origin}/api/v1/interests/search?q=&limit=`**.
Mapped to `{slug, title, spotmu_interest_id, interest_heading}`.
No service door required for guest search. Autocomplete still needs
auth if we want a lighter typeahead later.

Blank `q` returns `[]` without calling Spotmu. Failures are HTTP 502/504
with a clear detail string for the ops form.

## Trade-offs

- `source_items` / generate / cluster APIs stay. Queue/Schedule still
  use artifacts. This PR only replaces the first ops page.
- Accounts remain clustered in the domain model; campaign create just
  picks existing handles. Empty account list is intentional so the UI
  can be tested without real IG.
- Create does not upsert `source_items`. Interests are slug snapshots
  only until a later start/generate task.

## Verified

- Server unit tests: 188 collected, 14 persist skips (no Postgres in
  this environment). Includes slug, schemas, routes, models, Alembic
  head, mocked Spotmu search, Other-type 400.
- `npm run build` in `apps/ops` (`tsc -b` + Vite `dist/`).
- Health still import-light (`GET /health` without `DATABASE_URL`).

## Out of scope

- Start campaign / batch carousel generate / schedule
- Clusters on the Campaigns page
- Other campaign types
- Autocomplete (401 without a Spotmu service door)

## Scripts / files touched

- `apps/server/app/models/campaign.py`, `enums.py`, `models/__init__.py`
- `apps/server/app/campaigns/slug.py`
- `apps/server/alembic/versions/campaigns_create_ui.py`
- `apps/server/app/api/v1/campaigns.py`, `spotmu.py`, `router.py`, `schemas.py`
- `apps/server/app/ingest/spotmu.py` (guest search client)
- `apps/ops/src/pages/CampaignsPage.tsx` (replaces `SourcesPage.tsx`)
- `apps/ops/src/components/NavBar.tsx`, `App.tsx`, `api/*`
- `docs/startup.md`, `docs/planning/domain_statuses.md`
