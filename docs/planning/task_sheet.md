# Twerva — Task Sheet

*Last updated: 2026-10-03*  
*Status: Build plan. Strategy: `docs/prompts/project.md`. Product design: `docs/prompts/product.md`. Task grain follows Spotmu `docs/task_sheet.md` / historical `road_map.md`: lettered IDs, one concrete deliverable per leaf checkbox, paths/types/endpoints named, explicit out-of-scope notes.*

Roadmap alignment: **1 MVP → 2 Spotmu → 3 Internal brands → 4 External / spin-off (optional).**

Checkbox legend: `[ ]` todo · `[~]` in progress · `[x]` done

---

## Phase 1 — MVP (the loop)

**Exit:** One Spotmu-shaped cluster can go source → generate carousel → approve → publish → metrics → steer decision inside Twerva.

### 1.1 Repo, home & skeleton
- [x] Confirm Twerva repo layout (`apps/` `packages/` `tools/` `docs/`); README pointing at project/product/task docs
- [x] Copy Spotmu `style_guide.md` + Twerva `.cursorrules` + `directory.md` (coding discipline)
- [x] Register Twerva domain (`twerva.com`)
- [x] Public URL + TLS on Spotmu AWS (EC2 `twerva-server`, EIP `3.19.233.237`, Spaceship A → nginx + Let's Encrypt)
- [x] Compute + Postgres on EC2 `twerva-server` (Docker Postgres 16, localhost-only `:5432`; DB URL in `/opt/twerva/database_url.env`) — RDS deferred
- [x] **DEFERRED** S3 bucket/prefix for artifacts — until carousel/media generate needs object storage (see Parking lot)
- [x] **DEFERRED** Twerva-prefixed secrets in AWS SM/SSM — Phase 1 secrets stay on-box (`/opt/twerva/*.env` mode 600) (see Parking lot)
- [x] Choose stack for ops console + workers: FastAPI + React/Vite/TS + Postgres (Celery/Redis later) — Spotmu-aligned
- [x] Empty app shells: `apps/server` (FastAPI healthcheck) + `apps/ops` (Vite React stub)
- [x] Healthcheck endpoint on the Twerva URL (`https://twerva.com/health` → systemd `twerva-api` / uvicorn on `127.0.0.1:8000`)

### 1.2 Domain model (minimal)

**Exit:** Postgres holds the Phase 1 objects from `docs/prompts/product.md` §III; Alembic migration applied on `twerva-server`; FastAPI can create/read each object against the live DB; one seed Brand (`Spotmu`) + one Source item round-trips. **No** ingest from Spotmu yet (that is 1.3). **No** carousel render, publish, or ops UI polish.

**Out of scope for 1.2:** Celery/Redis, S3, auth/multi-user, Soft delete UI, Phase 3 brand-editorial fields beyond nullable stubs, Steer as a full product surface (table + enum only if needed for FK targets).

**Numbering:** `1.2a` = parent slice · `1.2a-i` = leaf (one PR-sized / one-sitting deliverable). Tick leaves; parent is done when all its leaves are `[x]`.

#### 1.2a — DB plumbing
Wire SQLAlchemy + Alembic to the existing EC2 Postgres (`DATABASE_URL` from `/opt/twerva/database_url.env`). Empty models package OK until 1.2b+.

- [x] **1.2a-i** Add DB deps to `apps/server` (`sqlalchemy`, `psycopg` or `psycopg2-binary`, `alembic`, `pydantic-settings` as needed). Pin ranges in `requirements.txt` / `pyproject.toml` consistent with Spotmu-aligned stack.
- [x] **1.2a-ii** Settings module reads `DATABASE_URL` from env (fail fast on missing URL in non-test). Document local override in `apps/server/README.md`.
- [x] **1.2a-iii** SQLAlchemy engine + `SessionLocal` / session dependency for FastAPI (`apps/server/app/db.py` or equivalent).
- [x] **1.2a-iv** Alembic init under `apps/server` (`alembic.ini`, `alembic/env.py` using same `DATABASE_URL`). Empty migration chain ready for 1.2b+.
- [x] **1.2a-v** Smoke: from `twerva-server`, app (or `alembic current`) connects to Postgres on `127.0.0.1:5432` using the on-box env file. Note command in README.

#### 1.2b — Shared types & status enums
Single source of truth for IDs and lifecycle strings used by Artifact / Post job.

- [x] **1.2b-i** Define UUID primary-key convention (Postgres `UUID`, generated in DB or app — pick one, document in model module docstring).
- [x] **1.2b-ii** `ArtifactStatus` enum: `draft` → `approved` → `rejected` (reject terminal for MVP). Store as Postgres enum or check-constrained text; document choice.
- [x] **1.2b-iii** `PostJobStatus` enum: `scheduled` → `publishing` → `published` → `failed` → `measured` (allow `failed` → retry back to `scheduled` or `publishing` — document allowed transitions in a short comment or `docs/planning/domain_statuses.md`).
- [x] **1.2b-iv** `Platform` enum: at least `instagram`, `tiktok` (string enum). Others later.
- [x] **1.2b-v** `SourceType` enum: at least `spotmu_interest` (Phase 1). Leave room for `brand_product` / `editorial_brief` as unused values or comments only — do not build those flows.

#### 1.2c — Brand
First-class Brand row. Phase 1–2: Spotmu is the seed brand.

- [x] **1.2c-i** Table `brands`: `id`, `slug` (unique), `name`, `created_at`, `updated_at`. Optional nullable `notes` text. No Phase 3 vibe/voice columns required yet (add nullable `voice_notes` only if it costs nothing).
- [x] **1.2c-ii** SQLAlchemy model `Brand` mapped to `brands`.
- [x] **1.2c-iii** Alembic revision creating `brands` (or combined 1.2 schema revision — if combined, still list as done when migration includes this table).

#### 1.2d — Source item
Raw material unit. Phase 1 shape = Spotmu interest fields (ingest comes in 1.3; schema must be ready).

- [x] **1.2d-i** Table `source_items`: `id`, `brand_id` FK → `brands`, `source_type` (`spotmu_interest`), `external_key` (nullable unique per brand+type — e.g. Spotmu interest id/slug), `title`, `interest_heading` (nullable), `overview_bullets` (JSONB array of strings), `canonical_url` (nullable — `/interest/:slug` absolute URL), `brand_kit_refs` (JSONB nullable), `raw_payload` (JSONB nullable for forward-compat), `created_at`, `updated_at`.
- [x] **1.2d-ii** Unique constraint on (`brand_id`, `source_type`, `external_key`) where `external_key` is not null.
- [x] **1.2d-iii** SQLAlchemy model `SourceItem` + relationship to `Brand`.

#### 1.2e — Cluster / lane
Topical account group — steer grain and purity.

- [x] **1.2e-i** Table `clusters`: `id`, `brand_id` FK, `slug` (unique per brand), `name`, `description` (nullable), `is_active` (bool default true), `created_at`, `updated_at`.
- [x] **1.2e-ii** Optional join `cluster_source_items` (`cluster_id`, `source_item_id`, unique pair) — manual assignment target for 1.3. If deferred to 1.3, leave an explicit `[ ]` parked note here and do not invent another mapping path.
- [x] **1.2e-iii** SQLAlchemy model `Cluster` (+ association if 1.2e-ii ships).

#### 1.2f — Account
Platform identity assigned to a cluster.

- [x] **1.2f-i** Table `accounts`: `id`, `cluster_id` FK, `platform` (`instagram`/`tiktok`), `handle` (text), `external_account_id` (nullable — vendor/platform id), `status` (`active`/`paused`/`disabled`), `cadence_cap_per_day` (int nullable), `created_at`, `updated_at`.
- [x] **1.2f-ii** Unique (`platform`, `handle`) or (`platform`, `external_account_id`) when present — document which uniqueness rule you lock.
- [x] **1.2f-iii** SQLAlchemy model `Account` + relationship to `Cluster`. **Do not** store OAuth tokens in plaintext in this task; token columns deferred until publish spike (1.6) or a dedicated secrets note.

#### 1.2g — Artifact
Rendered (or draft) post asset. Media bytes stay out of DB for now (S3 parked); store metadata + caption + structured slide plan.

- [x] **1.2g-i** Table `artifacts`: `id`, `brand_id` FK, `source_item_id` FK nullable, `cluster_id` FK nullable, `status` (`ArtifactStatus`), `format` text default `carousel`, `caption` text nullable, `cta_url` text nullable, `slides` JSONB nullable (ordered list of `{role, text, asset_ref?}` — `asset_ref` unused until S3), `created_at`, `updated_at`, `approved_at` nullable.
- [x] **1.2g-ii** SQLAlchemy model `Artifact` + relationships. Rejected/draft transitions allowed in app layer later; DB only stores status.

#### 1.2h — Post job
Scheduled/published instance of an artifact on an account.

- [x] **1.2h-i** Table `post_jobs`: `id`, `artifact_id` FK, `account_id` FK, `status` (`PostJobStatus`), `scheduled_for` timestamptz nullable, `published_at` timestamptz nullable, `platform_post_id` text nullable, `platform_post_url` text nullable, `last_error` text nullable, `created_at`, `updated_at`.
- [x] **1.2h-ii** SQLAlchemy model `PostJob` + relationships to `Artifact` and `Account`.

#### 1.2i — Metric snapshot
Performance readback grain (per post job first; cluster rollups are queries later in 1.7).

- [x] **1.2i-i** Table `metric_snapshots`: `id`, `post_job_id` FK, `captured_at` timestamptz, `views` bigint nullable, `likes` bigint nullable, `comments` bigint nullable, `shares` bigint nullable, `raw` JSONB nullable, unique (`post_job_id`, `captured_at`) or allow multiple rows and always take latest in queries — **pick one and document**.
- [x] **1.2i-ii** SQLAlchemy model `MetricSnapshot`.

#### 1.2j — Steer action (stub table only)
Enough to attach later agent/human decisions; no UI.

- [x] **1.2j-i** Table `steer_actions`: `id`, `cluster_id` FK, `action` text check in (`kill`, `pause`, `double_down`, `resume`), `reason` text nullable, `created_at`, `created_by` text nullable (freeform for MVP — `human` / agent name).
- [x] **1.2j-ii** SQLAlchemy model `SteerAction`. No API required beyond optional list in 1.2l.

#### 1.2k — Migration package & indexes
- [x] **1.2k-i** Single (or ordered) Alembic revision(s) creating all 1.2c–1.2j tables + enums/constraints. `alembic upgrade head` clean on empty DB.
- [x] **1.2k-ii** Indexes: FK columns; `brands.slug`; `clusters(brand_id, slug)`; `source_items(brand_id, source_type)`; `post_jobs(status, scheduled_for)`; `artifacts(status)`.
- [x] **1.2k-iii** Apply migration on `twerva-server` against Docker Postgres; record revision id in `docs/reports/task_1_2_report.md` when 1.2 closes (or interim note).

#### 1.2l — Minimal HTTP API (persist proof)
Thin FastAPI routes — enough to prove the model; not the ops console (1.8).

- [x] **1.2l-i** Pydantic schemas for create/read of Brand, SourceItem, Cluster, Account, Artifact, PostJob (MetricSnapshot create optional).
- [x] **1.2l-ii** `POST/GET` (list + by id) for Brand, SourceItem, Cluster, Account under a prefix e.g. `/api/v1/...`. No auth.
- [x] **1.2l-iii** `POST/GET` Artifact including status field; `POST/GET` PostJob including status field.
- [x] **1.2l-iv** Keep `GET /health` working; deploy updated API to `twerva-api` on EC2 (or document local-only until deploy task — prefer deploy so Badger’s `/health` monitors the same process that has models).
- [x] **1.2l-v** Smoke script or README curl recipe: create Brand `spotmu` → SourceItem → Cluster → Account → Artifact `draft` → PostJob `scheduled`, then GET each. Commit script under `tools/` if non-trivial.

#### 1.2m — Seed data
- [x] **1.2m-i** Idempotent seed: Brand `slug=spotmu`, `name=Spotmu`.
- [x] **1.2m-ii** One example SourceItem (fake Spotmu-shaped fields: title, interest_heading, 3 overview_bullets, canonical_url `https://spotmu.com/interest/example`). Not real ingest.
- [x] **1.2m-iii** Seed runnable via `python -m ...` or Alembic data migration — document in README.

**1.2 done when:** all leaves above `[x]`; migration on server; curl (or script) round-trip documented; short `docs/reports/task_1_2_report.md` written.


### 1.3 Spotmu ingest

**Exit:** Twerva can pull at least one **real** Spotmu interest into `source_items` (Brand `spotmu`) with title, `interest_heading`, `overview_bullets`, canonical `/interest/:slug` URL, and any available brand-kit refs; interest can be manually assigned to a `cluster` via `cluster_source_items`. Fake seed example may remain but is no longer the only path.

**Out of scope:** carousel generate (1.4), auth to Spotmu private APIs unless spike proves public path insufficient, bulk Phase-2 sync polish, scraping HTML when a JSON public API exists.

**Parallelism:** **serial** — path lock → fetch one → upsert → list/sync → cluster map. No Engineer N subs.

**Numbering:** `1.3a` parent · `1.3a-i` leaf.

#### 1.3a — Ingest path spike & lock
Compare options; write a short lock decision; prefer the cheapest reliable path.

- [x] **1.3a-i** Spike notes in `docs/reports/task_1_3_ingest_spike.md`: (1) Spotmu **public JSON** `GET /interests/slug/{slug}` (`PublicInterestPageResponse`), (2) sitemap/`/sitemap.xml` for slug discovery, (3) authenticated Spotmu API/export, (4) HTML scrape of `/interest/:slug`. For each: auth needs, field coverage vs Twerva `source_items`, failure modes.
- [x] **1.3a-ii** **Lock** MVP path in that report (expected: public JSON by slug + sitemap for discovery unless spike finds a blocker). Update `docs/prompts/product.md` open ingest question to point at the lock.
- [x] **1.3a-iii** Document Spotmu base URL config (`SPOTMU_API_BASE_URL` or similar, default `https://spotmu.com` or the live API origin the spike confirms — record exact origin used by the SPA/API).

#### 1.3b — Fetch one interest by slug
- [x] **1.3b-i** HTTP client module under `apps/server` (e.g. `app/ingest/spotmu.py`) that GETs one slug and returns a typed structure (Pydantic) with at least: `slug`, `title`, `interest_heading`, `overview_bullets`, canonical URL, optional logo/brand kit fields if present on the public payload, plus `raw_payload`.
- [x] **1.3b-ii** Clear errors for 404 / non-JSON / timeout; no silent empty upserts.
- [x] **1.3b-iii** Unit test with mocked HTTP response shaped like Spotmu public payload.

#### 1.3c — Upsert into `source_items`
- [x] **1.3c-i** Idempotent upsert into Brand `slug=spotmu` (create brand if missing): `source_type=spotmu_interest`, `external_key=slug`, map fields onto `source_items` columns; store full JSON in `raw_payload`.
- [x] **1.3c-ii** `POST /api/v1/ingest/spotmu/interests/{slug}` (or equivalent under `/api/v1`) that runs fetch+upsert and returns the `SourceItem` read schema. No auth (same as other v1 routes; remains localhost-only publicly).
- [x] **1.3c-iii** CLI: `python -m app.ingest.spotmu_interest <slug>` (or similar) documented in README.
- [x] **1.3c-iv** Integration test (Postgres) or carefully mocked DB test for upsert idempotency (second pull updates fields, same id).

#### 1.3d — Discover / batch pull (thin)
- [x] **1.3d-i** Helper to list candidate slugs from Spotmu sitemap (or public list endpoint if spike prefers it) — cap configurable (default small, e.g. 20) for MVP.
- [x] **1.3d-ii** `POST /api/v1/ingest/spotmu/sync` (body: optional `slugs[]` or `limit`) that upserts each; return counts created/updated/failed + errors per slug.
- [x] **1.3d-iii** Do **not** build a scheduler yet — on-demand only.

#### 1.3e — Map interests → clusters (manual OK)
- [x] **1.3e-i** API: attach/detach `source_item` ↔ `cluster` via `cluster_source_items` (e.g. `POST/DELETE /api/v1/clusters/{id}/source-items/{source_item_id}`).
- [x] **1.3e-ii** Ensure list cluster (or GET) can show linked source item ids (minimal — enough for ops later).
- [x] **1.3e-iii** Seed or README recipe: one real ingested interest assigned to a cluster `slug=default` (or `spotmu-general`) under Brand spotmu.

#### 1.3f — Verify, report, deploy notes
- [x] **1.3f-i** Smoke script or README: ingest one **real** slug from production Spotmu (pick any live sitemap slug), show SourceItem via GET API.
- [x] **1.3f-ii** Update `docs/reports/task_1_3_report.md` + tick leaves on this sheet.
- [x] **1.3f-iii** Note for Badger: deploy + any new env vars; no nginx `/api` public change.

**1.3 done when:** real Spotmu interest in DB, cluster link works, report written, Badger can deploy.


### 1.4 Carousel generate

**Exit:** Given a Spotmu-shaped `source_item`, Twerva can produce an `artifact` in status `draft` with: ordered `slides` JSON (cover → heading → bullets → CTA), rendered PNG (or JPEG) files on disk, `caption` + hashtags text, and `cta_url`. Callable via API and a small CLI/smoke script.

**Out of scope:** approval UI (1.5), publish (1.6), Celery/Redis (sync generate OK), short video, S3 (still parked — use **local filesystem** artifact store), fancy brand-kit design parity beyond a calm text-led MVP template.

**Parallelism:** **serial** (template → render → persist artifact → API). No Engineer N.

**Storage lock for MVP:** `ARTIFACT_STORAGE_DIR` (default `/opt/twerva/artifacts` on server, local `./data/artifacts` in README). `slides[].asset_ref` = relative path under that dir. Revisit S3 when volume or multi-host needs it.

#### 1.4a — Template spec
- [x] **1.4a-i** Write `docs/planning/carousel_template_v1.md`: slide roles (`cover`, `heading`, `bullet`, `cta`), canvas size (lock **1080×1920**, the theme frame), typography/color tokens (calm, text-led; cite Spotmu palette lightly or neutrals), CTA rules (`cta_url` = source `canonical_url` or `https://spotmu.com/interest/{slug}`).
- [x] **1.4a-ii** Caption/hashtag rules: short caption from title/heading + 3–8 generic/safe hashtags; no scraped spam tags.
- [x] **1.4a-iii** Bullet slide policy: 1 bullet per slide (or max N chars); overflow → extra slides; empty bullets skipped.

#### 1.4b — Local artifact storage
- [x] **1.4b-i** Settings: `ARTIFACT_STORAGE_DIR`; ensure directory creatable; document in README + `docs/ops/deploy.md` note for Badger.
- [x] **1.4b-ii** Helper to write bytes → `{artifact_id}/{slide_index}_{role}.png` and return `asset_ref` relative path.
- [x] **1.4b-iii** Do **not** create AWS S3 in this section.

#### 1.4c — Render pipeline
- [x] **1.4c-i** Add render deps (e.g. `Pillow`) pinned like other requirements.
- [x] **1.4c-ii** `app/generate/carousel.py` (or similar): input = source fields → list of slide specs + rendered images on disk + caption string + cta_url.
- [x] **1.4c-iii** Unit test: render from a fake source payload produces ≥3 PNG files and a non-empty caption (tmp dir).

#### 1.4d — Persist as Artifact draft
- [x] **1.4d-i** Service: create `Artifact` with `format=carousel`, `status=draft`, `slides` JSON including `role`, `text`, `asset_ref`, link `brand_id`/`source_item_id`/`cluster_id` when provided.
- [x] **1.4d-ii** Idempotency: optional — if re-generate, new artifact row (keep history) unless you document replace-in-place; prefer **new draft each generate** for MVP.
- [x] **1.4d-iii** Test: generate persists artifact readable via existing GET schema.

#### 1.4e — API + CLI
- [x] **1.4e-i** `POST /api/v1/generate/carousel` body: `source_item_id` (required), optional `cluster_id`; returns Artifact read schema.
- [x] **1.4e-ii** CLI: `python -m app.generate.carousel_cli <source_item_id>` documented in README.
- [x] **1.4e-iii** Smoke script `tools/smoke_1_4_carousel.sh`: use seeded or ingested source → generate → GET artifact; works offline from Spotmu (DB source only).

#### 1.4f — Report & deploy notes
- [x] **1.4f-i** `docs/reports/task_1_4_report.md`; tick leaves on this sheet.
- [x] **1.4f-ii** Badger notes: create `ARTIFACT_STORAGE_DIR`, pip install, restart; disk growth watch; still no public `/api` nginx.

**1.4 done when:** draft carousel artifact with on-disk slides + caption from a source_item via API.

### 1.5 Approval & schedule

**Exit:** Operator can list draft artifacts, approve/reject/edit caption, and create a `post_job` scheduled to an account at a time, respecting simple cadence caps. CLI acceptable; thin API required. Full calendar UI can wait for 1.8.

**Out of scope:** Real social publish (1.6), ops React polish (1.8), Celery beat (sync schedule create OK).

**Parallelism:** serial.

#### 1.5a — Review queue API
- [x] **1.5a-i** `GET /api/v1/artifacts?status=draft` (and by id already exists) — review queue list.
- [x] **1.5a-ii** `POST /api/v1/artifacts/{id}/approve` → status `approved`, set `approved_at`; optional body `{caption}` to edit caption before/at approve.
- [x] **1.5a-iii** `POST /api/v1/artifacts/{id}/reject` → status `rejected` (terminal); optional `{reason}` stored only if easy (else ignore).
- [x] **1.5a-iv** `PATCH /api/v1/artifacts/{id}` for caption (and maybe cta_url) while `draft` or `approved` (not `rejected`).
- [x] **1.5a-v** Tests for transitions; reject cannot re-approve without new artifact.

#### 1.5b — Cadence caps
- [x] **1.5b-i** Helper: given `account_id` + proposed `scheduled_for` (day in UTC or account-local — document UTC), count existing `post_jobs` that day not in `failed` (or count all non-failed); compare to `accounts.cadence_cap_per_day` (null = no cap).
- [x] **1.5b-ii** Schedule endpoint returns **409** with clear error when cap exceeded.
- [x] **1.5b-iii** Unit tests for under/at/over cap.

#### 1.5c — Schedule post job
- [x] **1.5c-i** `POST /api/v1/schedule` body: `artifact_id`, `account_id`, `scheduled_for` (ISO timestamptz). Artifact must be `approved`. Creates `post_job` status `scheduled`.
- [x] **1.5c-ii** Validate account belongs to same brand/cluster coherence as artifact when cluster set (reasonable check; document).
- [x] **1.5c-iii** CLI: approve + schedule recipe in README; smoke `tools/smoke_1_5_approve_schedule.sh` using seed/generate path offline.

#### 1.5d — Report
- [x] **1.5d-i** `docs/reports/task_1_5_report.md`; tick leaves; Badger deploy note (no new host deps expected).

**1.5 done when:** draft → approve → scheduled post_job works via API + smoke.

### 1.6 Publish (IG + TikTok)

**Exit:** A `PublishAdapter` interface exists; MVP ships a **dry-run/mock** adapter that “publishes” scheduled jobs to `published` with fake platform ids **and** a spike lock choosing the real vendor for later. Optional live vendor only if env credentials present — do not block Phase 1 on Ayrshare signup.

**Out of scope:** Paid ads, real OAuth account connection UI (store `external_account_id` manually OK), Celery required (sync publish endpoint/CLI OK).

**Parallelism:** serial.

#### 1.6a — Buy vs build spike
- [x] **1.6a-i** `docs/reports/task_1_6_publish_spike.md`: Ayrshare vs Zernio vs Postiz vs native Meta/TikTok — recommendation for Twerva MVP+Phase2.
- [x] **1.6a-ii** Lock: implement adapter interface now; **mock adapter default**; real vendor behind env flag when keys exist.

#### 1.6b — PublishAdapter
- [x] **1.6b-i** Interface: `publish(post_job, artifact, account, media_paths) -> {platform_post_id, platform_post_url}`.
- [x] **1.6b-ii** `MockPublishAdapter`: succeeds, writes deterministic fake ids; logs media paths counted.
- [x] **1.6b-iii** Settings: `PUBLISH_ADAPTER=mock|ayrshare` (or similar); only mock required to work in CI.

#### 1.6c — Publish worker path
- [x] **1.6c-i** `POST /api/v1/publish/run/{post_job_id}` (or `/publish/due`) — load scheduled job, set `publishing`, call adapter, on success `published` + platform fields + `published_at`; on failure `failed` + `last_error`.
- [x] **1.6c-ii** Basic retry: optional second attempt or document manual re-run; backoff note in report (no Redis required).
- [x] **1.6c-iii** Resolve slide `asset_ref` files from `ARTIFACT_STORAGE_DIR` for adapter input.
- [x] **1.6c-iv** Tests with mock adapter; smoke script offline.

#### 1.6d — Report
- [x] **1.6d-i** `docs/reports/task_1_6_report.md`; tick leaves; note live vendor as follow-up when Mu adds keys.

**1.6 done when:** scheduled job can be mock-published to `published` with platform ids recorded.

### 1.7 Measure & steer

**Exit:** Manual (or stub) metric capture into `metric_snapshots`; cluster median views endpoint; steer actions kill/pause/double_down/resume recorded; agent-readable summary JSON/markdown endpoint or CLI.

**Out of scope:** Celery/Redis, ops UI (1.8), real analytics vendor / platform insights pull.

**Parallelism:** serial.

#### 1.7a — Metrics in
- [x] **1.7a-i** `POST /api/v1/post-jobs/{id}/metrics` body views/likes/comments/shares — append `metric_snapshots` row (latest-wins already documented).
- [x] **1.7a-ii** Optional stub puller that no-ops or copies mock views for mock-published jobs — document.

#### 1.7b — Cluster median
- [x] **1.7b-i** `GET /api/v1/clusters/{id}/metrics/summary` — median views across post jobs that have snapshots (document empty behavior).
- [x] **1.7b-ii** Unit test for median helper.

#### 1.7c — Steer controls
- [x] **1.7c-i** `POST /api/v1/clusters/{id}/steer` body `{action, reason?}` → insert `steer_actions`; if `kill`/`pause`, set cluster `is_active=false` or account statuses paused as documented; `resume`/`double_down` documented behavior (double_down may only log for MVP).
- [x] **1.7c-ii** Tests for pause/resume side effects you implement.

#### 1.7d — Agent summary
- [x] **1.7d-i** `GET /api/v1/clusters/{id}/agent-summary` (or CLI) returning markdown/JSON: recent artifacts, post jobs, medians, last steer actions.
- [x] **1.7d-ii** `docs/reports/task_1_7_report.md`; tick leaves; smoke script.

**1.7 done when:** metrics → median → steer → summary works via API.

### 1.8 Ops console (thin)

**Exit:** `apps/ops` shows ugly-but-usable pages: Sources, Generate queue (drafts + approve actions), Schedule/Publish stubs, Accounts/Clusters, Results (median + steer). Can walk the loop in the browser against local API (vite proxy to API).

**Out of scope:** Auth, pretty design, mobile polish.

**Parallelism:** serial (one frontend PR). May depend on 1.5–1.7 APIs — implement against those routes.

#### 1.8a — App shell & API client
- [x] **1.8a-i** Vite proxy or `VITE_API_BASE_URL` to Twerva API (default `http://127.0.0.1:8000`).
- [x] **1.8a-ii** Simple nav layout: Sources · Queue · Schedule · Accounts · Results.

#### 1.8b — Pages
- [x] **1.8b-i** Sources: list source_items; button to generate carousel.
- [x] **1.8b-ii** Queue: list drafts; approve / reject / edit caption.
- [x] **1.8b-iii** Schedule: pick approved artifact + account + time; list post_jobs; button mock-publish.
- [x] **1.8b-iv** Accounts/Clusters: list; cadence_cap display; steer buttons.
- [x] **1.8b-v** Results: cluster summary + agent-summary pane (pre/plaintext OK).

#### 1.8c — Ship notes
- [x] **1.8c-i** README how to run ops + API locally; optional static build note for later nginx (not required to expose publicly tonight).
- [x] **1.8c-ii** `docs/reports/task_1_8_report.md`; tick leaves.

**1.8 done when:** ops UI can drive generate → approve → schedule → mock publish → metrics/steer against API.

### 1.9 Agent hooks

**Exit:** Docs + one dry-run playbook so agents (Sparky/Canary/etc.) can batch-generate and propose steer without guessing APIs.

**Parallelism:** serial; docs-heavy; tiny helper scripts OK.

#### 1.9a — Operator/agent docs
- [x] **1.9a-i** `docs/agents/README.md` — how agents draft artifacts, approve gates, propose steer; link API routes.
- [x] **1.9a-ii** `docs/agents/playbook_batch_generate_spotmu_cluster.md` — dry-run: ingest/sync (or use existing sources) → generate carousels for cluster X → stop before approve (human gate) → optional summary.
- [x] **1.9a-iii** Optional `tools/agent_batch_generate.sh` implementing the dry-run against localhost API.

#### 1.9b — Close Phase 1 sheet
- [x] **1.9b-i** Tick 1.9 leaves; `docs/reports/task_1_9_report.md`.
- [x] **1.9b-ii** Short `docs/reports/phase_1_exit_report.md`: what works end-to-end, what’s mock (publish), Spotmu ingest smoke status, what Mu should review before Phase 2. **Do not start Phase 2.**

**1.9 / Phase 1 done when:** playbook exists + phase_1_exit_report written.

**Phase 1 done when:** loop works on box with mock publish (real Spotmu ingest when Spotmu up); human gate documented; `phase_1_exit_report.md` written for Mu review. **Stop — do not start Phase 2.**

---

## 1.10 — Carousel theme frame (locked model)

**Exit:** An operator can save a carousel theme as **Draft** or **Live**, set its background and spacing, add text and image elements, duplicate it into a new Draft, and run **Generate samples**. Samples are previews. They are not artifacts and not post jobs. Layout follows [`docs/planning/themes_v1.md`](themes_v1.md). Overlap on a concrete frame is an error: that instance is blocked and highlighted, and other bands are not pushed aside.

**Source of truth:** [`docs/planning/themes_v1.md`](themes_v1.md). There is no open cell or skeleton leaf on this sheet. Do not add one, and do not implement a cell/skeleton layout beside this model.

**Already shipped (do not redo):** Alembic `themes_create` and `themes` (`name`, `slug`, `advertisement_type`, `template_key`, `created_by`). `POST/GET /api/v1/themes` and `GET /api/v1/themes/{id}` in `apps/server/app/api/v1/themes.py`. Ops **Themes** list and **Create Theme** (name + carousel type) in `apps/ops`. Seeded Spotmu Paper v1 and Spotmu Bold v1. Create stays name-only; new columns use the defaults below so that route keeps working.

**Still the ship path until a later slice:** carousel pixels for posts that ship come from [`carousel_template_v1.md`](carousel_template_v1.md) and `apps/server/app/generate/carousel.py`. 1.10 does not point `POST /api/v1/generate/carousel` at a Live theme.

**Out of scope for 1.10:** short video and any non-carousel advertisement type; edge layouts (side-by-side elements, free placement, partial-width rectangles); image upload, an `assets` table, object storage, and serving design; text sources other than the four Spotmu fields below; binding a Live theme into shipping generate; campaign binding; restyling existing artifacts; Phase 2.

**Parallelism:** serial — frame → elements → duplicate → layout → measure → overlap → samples → ops editor. No Engineer N.

**Numbering:** `1.10a` parent · `1.10a-i` leaf. Tick leaves; the section is done when every leaf is `[x]`.

**Storage note:** a picture and an image element store a **reference** only (`background_asset_ref` / `image_asset_ref`): a relative path, same idea as `slides[].asset_ref`. Texture is dropped for now and may return as a default album of texture images. No new bucket. Sample render may read a file that is already under `ARTIFACT_STORAGE_DIR`. It does not grow an upload pipeline.

**Canvas for this section:** **1080×1920**. Do not add a per-theme size column.

#### 1.10a — Persist the frame

New Alembic revision after `themes_create`. Do not edit `themes_create`. Native Postgres enums, same approach as `docs/planning/domain_statuses.md`. Document the new values there.

- [x] **1.10a-i** `ThemeStatus` (`draft`, `live`) and `themes.status`, default `draft`. Backfill existing rows, including Spotmu Paper v1 and Spotmu Bold v1, to `draft`. Add `PATCH /api/v1/themes/{id}` (partial) and include `status` on `ThemeReadResponse`. Create ignores a status body and always stores `draft`. Same write gate as `POST /api/v1/themes` (`require_authenticated_ops_operator`); ops writes stay behind `useCanWriteOps`. **Done when:** a test patches one theme to `live` and back to `draft`, GET returns it, and existing create-by-name still returns `draft`. **Out of scope:** spacing, background, elements, the ops editor, using Live inside `POST /api/v1/generate/carousel`.

- [x] **1.10a-ii** Integer columns `page_margin`, `element_gap`, `element_margin`. One value each, applied on every edge (rules in themes_v1). Defaults: `page_margin` **96**, `element_gap` **0**, `element_margin` **0**. Reject negatives (400). Backfill existing rows with those defaults. Extend the same PATCH and read schema. **Done when:** a test round-trips a non-default triple, rejects `-1`, and a newly created name-only theme reads back 96 / 0 / 0. **Out of scope:** layout math, elements, drawing.

- [x] **1.10a-iii** One background per theme, columns on `themes` (not a second table): `background_kind` enum `picture` | `color` | `gradient`. Texture is dropped for now and may return as a default album of texture images. `background_color` text nullable; `background_gradient` JSONB nullable; `background_asset_ref` text nullable. Default kind `color`, color `#F6F1E8` (paper from `carousel_template_v1`), gradient and asset ref null. Gradient shape, locked in the schema docstring: `{"angle_deg": <0–360>, "stops": [{"offset": <0–1>, "color": "#rrggbb"}, ...]}` with at least two stops. Hex colors are `#` plus six hex digits. `background_asset_ref` is a relative path with no `..` and no scheme; suffix `.svg`, `.png`, `.jpg`, or `.jpeg`. Draft may save a kind with its payload still empty. A row that is **Live** (this patch or already live) requires the payload for its kind: color hex, a valid gradient, or a non-empty asset ref for `picture`. **Done when:** tests cover each kind round-trip, a Live color theme with a blank color is 400, and a Draft picture with a null ref saves. **Out of scope:** rendering, upload, elements.

#### 1.10b — Persist elements

- [x] **1.10b-i** Table `theme_elements` (model `apps/server/app/models/theme_element.py`): `id`, `theme_id` FK → `themes` ON DELETE CASCADE, `band` enum `top` | `middle` | `bottom`, `sort_order` int, `content_kind` enum `text` | `image`, `rectangle_color` text nullable, text columns (`text_source`, `font_family`, `font_size`, `font_color`, `bold`, `italic`, `underline`, `strikethrough`, `font_weight`, `alignment`), `image_asset_ref` text nullable, timestamps. Unique (`theme_id`, `band`, `sort_order`). No x, y, or width column — every element is the full content width. `rectangle_color` null means the rectangle is clear. `text_source` enum is only `title`, `interest_heading`, `overview_bullets`, `canonical_url` (maps to `source_items.title`, `.interest_heading`, `.overview_bullets`, `.canonical_url`). `alignment` enum: `left` | `center` | `right`. Check: `text` requires `text_source`, `font_family`, `font_size` (positive int), `font_color`, and `alignment`; booleans default false; `font_weight` is optional (1–1000 or null). `image` requires `image_asset_ref` (same path rules as `background_asset_ref`) and forbids `text_source`. **Done when:** migration applies on a clean DB and the model maps those columns. **Out of scope:** HTTP, layout, wrap, ops, upload.

- [x] **1.10b-ii** Element API under the theme write gate: `GET /api/v1/themes/{id}` includes `elements` ordered by band (`top`, `middle`, `bottom`) then `sort_order`. `POST/PATCH/DELETE /api/v1/themes/{theme_id}/elements` and `.../elements/{element_id}`. `sort_order` is 0-based within the band; the server compacts it after writes. Reject unknown sources, partial-width or x/y fields, and image refs that are not svg/png/jpeg. **Done when:** tests create a clear text element and an image element, reload them in order, move one to another band, and reject `text_source` values outside the four Spotmu keys. **Out of scope:** measuring text, reading image bytes, the ops editor.

#### 1.10c — Duplicate

- [x] **1.10c-i** `POST /api/v1/themes/{id}/duplicate`. New row, new id, status `draft`, name `Copy of {name}`, slug from the existing slug helper. Copy background, the three spacing values, and every element (new element ids; same band, order, and content). Leave the source row untouched, including its status and `updated_at`. Set `template_key` null on the copy (`template_key` is unique). **Done when:** a test duplicates a Live theme that has a gradient and two elements; the source is still Live with the same ids; the copy is Draft; the copy's `template_key` is null; element ids differ. **Out of scope:** the ops button (1.10h), samples.

#### 1.10d — Layout math

- [x] **1.10d-i** Pure function in `apps/server/app/themes/layout.py`. Input: the 1080×1920 frame, the three spacing ints, and elements that already have a content height, grouped by band and `sort_order`. Output: integer rectangles `{element_id, x, y, width, height}` plus the content area. Content area is the frame inset by `page_margin` on every edge; element `x` is that left edge and element width is that width. Element height = content height + `element_margin` above + `element_margin` below. `element_gap` sits between rectangles in the same band only (not before the first, not after the last, not inside page margin). **Top:** first element’s top is `page_margin` down from the frame top; later top elements stack downward. **Bottom:** the first element is the lowest, its bottom `page_margin` up from the frame bottom; later bottom elements stack upward. **Middle:** one block whose height is the sum of the middle heights plus gap between them; place it so its center is the vertical center of the content area. An odd leftover pixel goes below the block (`top = content_top + floor((content_height - block_height) / 2)`). Do not center only the first or last middle element. An empty band adds no rectangles. Zero elements returns no rectangles and is valid. **Done when:** unit tests cover a single top element, two top elements with gap only between them, two bottom elements stacking upward, three middle elements centered as a group, a one-band theme, and zero elements. **Out of scope:** font measurement, image bytes, overlap policy, PNG files, pushing another band.

#### 1.10e — Measure text and images

- [x] **1.10e-i** `apps/server/app/themes/sources.py` resolves one text element from a `SourceItem`: `title`; `interest_heading` (blank when null); `overview_bullets` as the non-empty strings joined with `\n` into **one** block (do not emit a frame per bullet); `canonical_url` (blank when null). No other source keys. **Done when:** a unit test maps a fake Spotmu source item, including three bullets as one string, and a disallowed key never appears in the enum. **Out of scope:** non-Spotmu sources, wrap, HTTP.

- [x] **1.10e-ii** `apps/server/app/themes/measure.py` turns resolved content into content heights, then calls the 1.10d layout so the band reflows. Text wraps inside the content width (element width minus `element_margin` on the left and right). Use Pillow, already pinned for carousel render. Family, size, bold/italic, and weight (when the face supports it) affect measurement. Underline and strikethrough do not change height. Alignment does not change width or height. A missing face uses the same fallback as `app/generate/carousel.py` (DejaVu / Liberation / Pillow default) — do not add a font package. Empty text is one line of that face. After wrap, top reflows downward from the first top element, bottom reflows upward from the lowest, and middle recenters the whole middle block. **Done when:** a test shows a long string growing height and moving only the later sibling in the same band, and a second test shows an underline flag leaving height unchanged. **Out of scope:** overlap errors, writing PNGs, the ship-path carousel template.

- [x] **1.10e-iii** Image content height from a file already on disk. Resolve `image_asset_ref` under `ARTIFACT_STORAGE_DIR` and reject paths that escape it. Keep aspect ratio. Width is the content width; that scaled height is the content height. PNG and JPEG via Pillow. SVG via the stdlib XML parser (`width`/`height`, else `viewBox`) — do not add an SVG library. A missing or unreadable file is a structured measure error for that element, not a guessed size. **Done when:** a tmp PNG with a known aspect ratio produces the expected height, a tiny SVG viewBox does the same, and a missing file returns the error without a rectangle. **Out of scope:** upload, thumbnailing, background rendering.

#### 1.10f — Overlap

- [x] **1.10f-i** `apps/server/app/themes/overlap.py`. After placement, rectangles from **different** bands overlap when their areas intersect. Sharing an edge is not an overlap. Do not change coordinates. Do not push Middle or Bottom. Return `{blocked, overlaps: [{band_a, band_b, element_ids}]}`. Zero elements is not blocked. A same-band stack with gap ≥ 0 is not an overlap. **Done when:** tests show a tall top element intersecting middle as blocked with the original `y` values unchanged, an edge-touching pair as allowed, and a two-instance call that flags only the colliding instance. **Out of scope:** the highlight UI, samples HTTP, artifacts, post jobs.

#### 1.10g — Generate samples

- [x] **1.10g-i** `POST /api/v1/themes/{id}/samples` body `{source_item_id}`. One request, one frame (do not split bullets into slides, and do not read slide roles from `carousel_template_v1`). Source item must be `source_type=spotmu_interest`; otherwise 400. Resolve, measure, place, and overlap-check that frame. Render a PNG with Pillow into `{ARTIFACT_STORAGE_DIR}/theme-previews/{theme_id}/{preview_id}.png`. `GET /api/v1/themes/{theme_id}/samples/{preview_id}/image` streams it for a signed-in operator. Draw the background filling the frame: solid color; linear gradient from the locked JSON (no radial); picture scaled to fill (no tiling). Texture is dropped for now and may return as a default album of texture images. Then draw each element rectangle (skip the fill when `rectangle_color` is null) and its content. Overlap still renders the PNG so the operator can see it, and the response sets `blocked` true with the overlap payload. A missing picture or image file sets `blocked` true with `block_reason` `missing_asset` and does not invent a fill. Response also carries `block_reason` null | `overlap` | `missing_asset` | `measure_error`, and `detail`. Works for Draft or Live. Does not change theme status. **Done when:** a test writes a preview file and asserts no new `artifacts` row and no new `post_jobs` row; a second test with a colliding layout returns `blocked` true and `block_reason` `overlap`. **Out of scope:** approve, schedule, publish, `POST /api/v1/generate/carousel`, the ops highlight.

#### 1.10h — Ops editor

Extend the Themes detail view (`apps/ops/src/pages/ThemesPage.tsx`, `apps/ops/src/api/client.ts`, `apps/ops/src/api/types.ts`). Keep **Create Theme** as the name-only create; it lands on a Draft. Readers see values and cannot save (`ReadOnlyNotice` / `useCanWriteOps`).

- [x] **1.10h-i** Frame fields on the open theme: Draft/Live, background kind, and the payload for that kind (color, gradient stops + angle, or a text `asset_ref` — no file picker), page margin, element gap, element margin. Save with PATCH. Show the API’s Live-validation error on the form. **Done when:** an admin can set each background kind and the three spacing numbers, reload, and see the same values; a reader cannot save. **Out of scope:** elements, samples, upload.

- [x] **1.10h-ii** Element editor on the same theme: add, edit, delete, reorder within a band, and move among Top / Middle / Bottom. Content is text or image. Rectangle color empty means clear. Text controls: family, size, color, bold, italic, underline, strikethrough, optional weight, alignment, and a source picker limited to title, interest heading, overview bullets, and the public URL. Image control: one `asset_ref` text field for svg/png/jpeg. **Done when:** a text element and an image element survive reload, and the source picker has no other choice. **Out of scope:** free placement, partial width, non-Spotmu sources, upload.

- [x] **1.10h-iii** **Duplicate** calls 1.10c and opens the new Draft. The source theme stays as it was. **Done when:** duplicating a Live theme navigates to a Draft copy and the source list row is still Live. **Out of scope:** bulk duplicate.

- [x] **1.10h-iv** **Generate samples:** pick one Spotmu source item, call the samples endpoint only, and show the preview. A blocked preview stays on screen with a visible error state (banner plus a highlight on that preview) naming the reason — overlap bands, or the missing-asset / measure error. It is not sent to Queue, Schedule, or publish. A non-blocked preview shows the image without that error state. Empty state: no source chosen, the button does not call the API. **Done when:** the click hits `/api/v1/themes/{id}/samples` and does not call `/api/v1/generate/carousel` or create a queue row. **Out of scope:** shipping generate, multi-frame sample batches.

#### 1.10i — Close the section

- [ ] **1.10i-i** `docs/reports/task_1_10_report.md`: what landed, the preview-vs-post split, and the deferred upload / non-Spotmu / ship-path notes. Tick these leaves. **Done when:** the report exists and every 1.10 leaf above is `[x]`. **Out of scope:** starting Phase 2, switching `POST /api/v1/generate/carousel` onto Live themes.

**1.10 done when:** the leaves above are `[x]`; a theme can hold the locked frame and elements; duplicate yields a new Draft; Generate samples shows a preview, including a highlighted overlap, and writes no artifact and no post job.

---

## Sources v2 — albums of units

**Exit:** An operator can read the Default album as six image-only units, then manage albums and units, take in images, store resources, and pick those images from a theme. Campaign combination and the model stay later.

**Source of truth:** [`docs/planning/sources_v2.md`](sources_v2.md). Phases ship in order. Do not start a phase before the previous one is `[x]`.

**Numbering:** `S1` through `S5` are the build phases. Tick a leaf when its done-when holds. Later is not a build leaf.

#### Phase 1 — Model and Default

- [x] **S1** Alembic `sources_default_album` after `themes_element_rectangle`. Do not edit that revision. Tables `sources`, `units`, `unit_fields`, and `unit_images`, including `tags` and the license columns in the design. Seed one album, slug `default`, with six image-only units. Each `relative_path` stays `theme-defaults/…`. License and source come from `default_images/LICENSES.md`. Bytes stay in the package. Read API: `GET /api/v1/sources?kind=album` and `GET /api/v1/sources/{id}`. Readers may GET. **Done when:** a clean database migrates; a test reads Default and the six units with those paths and `cc0` or `public_domain`; a theme that already stores one of those paths still renders; no theme row is rewritten. **Out of scope:** ops pages, upload, URL import, thumbnails, resources, the theme picker, write and delete routes.

#### Phase 2 — Albums and units in ops

- [x] **S2** No migration. Write API for albums and units: create, rename, edit free text, fields, tags, and the license, source, alt, and note on an image that already exists. Reject an empty unit, a license outside the allowlist, a blank image source, and `licensed` with no note. Delete of an image, unit, or album is 409 while a theme or artifact stores that path. Ops: Sources, an Albums tab, a units grid, and a unit editor. The grid shows the packaged JPEG for a `theme-defaults/` path, streamed with the existing package resolver. Admin writes. Reader reads. **Done when:** an admin creates an album and a text-only unit with a field and a tag, reloads, and sees them; deleting a Default image whose path a theme stores returns 409 and the row remains; a reader cannot save. **Out of scope:** new image bytes, URL import, generated thumbnails, the Resources tab, replacing the hard-coded theme album list.

#### Phase 3 — Image intake

- [x] **S3** No migration. Disk storage behind `save`, `open`, and `delete`, prefix `albums/<source_id>/<unit_id>/<image_id>.<ext>` under `ARTIFACT_STORAGE_DIR`. Multipart upload and URL import. The server downloads a URL once. SVG, PNG, or JPEG, 8 MB. The same license gate as Phase 2; a failure writes nothing. Thumbnail JPEG, longest edge 480. SVG has no thumbnail. The unit editor gains upload and import. The grid uses the thumbnail when one exists. **Done when:** an admin uploads a JPEG and imports a PNG from a URL, both appear with license and source, a file over 8 MB or a missing license note is 400 and leaves no row, and a theme path from Phase 1 still resolves. **Out of scope:** S3, WebP, resources, pointing the theme picker at the new albums.

#### Phase 4 — Resources

- [ ] **S4** Migration yes. Table `resource_files`. Upload `.md` or `.txt`, stored as-is, 2 MB, with a required provenance note. Replacing the file is a new upload. Ops: a Resources tab, the note, and the file as text. Delete is allowed, because nothing points at a resource yet. **Done when:** an admin uploads a Markdown file and a note, reloads, and the bytes match; a `.txt` works; a PDF or a blank note is 400; a reader can open the text and cannot upload. **Out of scope:** PDF conversion, auto-synthesis, tags on a resource, campaign links, image changes.

#### Phase 5 — Theme pickers

- [ ] **S5** No migration. Themes keep `background_asset_ref` and `image_asset_ref`. The picture and image controls list albums, then units that have an image, then those images. Text-only units stay off the picker. A caption from free text or the first field is display only. Pick and Shuffle store one concrete path. Samples, live preview, and generate read that path. An unknown path stays "Saved image". This replaces the hard-coded Default catalog. **Done when:** an admin picks one Default image and one uploaded image, reloads, and both stored paths are those files; Shuffle writes a different path once and a second sample uses the saved path; a reader sees the list and cannot upload. **Out of scope:** a unit id on the theme, generate-time random, copying unit text onto the frame, resources in the picker.

**Later (not a leaf):** campaign combination rules and the model, S3, brand or campaign ownership, a texture album, PDF synthesis, and WebP. See the Later section in `sources_v2.md`.

**Sources v2 done when:** S1–S5 are `[x]`.

---

## Phase 2 — Spotmu (harden the pipeline)

**Exit:** Multiple clusters running; medians above suppression floor; steer is routine; Spotmu traffic signal visible.

### 2.1 Scale ingest & lanes
- [ ] Bulk interest import / sync
- [ ] Lane taxonomy for Spotmu verticals; purity rules documented

### 2.2 Publishing reliability
- [ ] Harden connectors; reduce assisted-manual steps
- [ ] Warm-up and cadence policy v1
- [ ] Account health monitoring (flags, sudden reach drop)

### 2.3 Creative iteration
- [ ] Template variants A/B (still carousels-first)
- [ ] Optional basic short-video path **only if** same Post job model
- [ ] Caption/CTA experiments with logging

### 2.4 Metrics → Spotmu
- [ ] UTM / landing attribution into Spotmu analytics (or agreed proxy)
- [ ] Dashboard: cluster kill/double-down with evidence

### 2.5 Agent loop
- [ ] Agents propose weekly steer from medians
- [ ] Humans ratify; system applies

**Phase 2 done when:** Twerva is how Spotmu social distribution is actually run day-to-day for chosen lanes.

---

## Phase 3 — Internal brands & internal projects

**Exit:** At least one internal brand world cadences without still-spam; sales or strong proxy attribution; money model trial possible.

### 3.1 Brand object for real
- [ ] Brand entity: vibe, voice, editorial hooks, product suite
- [ ] Vetting/grouping workflow: which products belong to which brand

### 3.2 Brand content engine
- [ ] Formats beyond product stills (lifestyle, process, series, suite features)
- [ ] Calendar that sells the **brand world**, SKUs ride along
- [ ] Guardrails: topical purity, no orphan-SKU spam

### 3.3 Commerce path
- [ ] Basic storefront or checkout-in-path spike (if selling physical/digital goods)
- [ ] Attribution: post → brand → SKU → sale

### 3.4 Money model trial
- [ ] Instrument cut and/or subscription paths (pick experiment from `project.md`)
- [ ] Internal economics review (cost per post batch vs return)

### 3.5 Other internal projects
- [ ] Plug a second internal project into the same rails (non-Spotmu)
- [ ] Note what generalized vs what stayed Spotmu-specific

**Phase 3 done when:** brand-shaped carry works on inventory we control — real PoC beyond media hose.

---

## Phase 4 — Spin-off & external brands (optional)

**Exit:** Deliberate external shape — or conscious decision to stay internal. Not required for “worth it.”

### 4.1 Trust & carry
- [ ] Maker agreements; non-compete / no-clone posture
- [ ] Account ownership / handoff policy
- [ ] Dupe / derivative policy across listings

### 4.2 External onboarding
- [ ] Vetting pipeline for external products into house brands
- [ ] Limited self-serve **into brands** only if content math holds

### 4.3 Spin-off decision
- [ ] Package Twerva and/or brand houses for external business — or park
- [ ] Confirm still not an ads bidder

---

## Parking lot (do not pull forward early)
- **DEFERRED from 1.1** — S3 / object storage for generated media (create when multi-host/volume needs it; **1.4 uses local `ARTIFACT_STORAGE_DIR`**)
- **DEFERRED from 1.1** — AWS Secrets Manager / SSM with Twerva-prefixed secrets (Phase 1 uses on-box `/opt/twerva/*.env` mode 600)
- **DEFERRED from themes v1 / 1.10** — image upload, storage, and serving (the frame stores a path reference only; sample render may read a file already under `ARTIFACT_STORAGE_DIR`)
- **DEFERRED from themes v1 / 1.10** — text sources other than Spotmu `title`, `interest_heading`, `overview_bullets`, and `canonical_url`
- **DEFERRED from themes v1 / 1.10** — short video, non-carousel theme types, and edge layouts (side-by-side, free placement, partial-width)
- **DEFERRED from 1.10** — binding a Live theme into `POST /api/v1/generate/carousel` (posts that ship stay on `carousel_template_v1` until that later slice)

- Character / mascot universes
- Outfy-class “post only to seller’s own empty accounts” as the product
- Average-Joe one-SKU fully self-serve
- Paid ads bidding
- Multi-platform sprawl before IG+TikTok are boringly reliable
- Merging Twerva into Spotmu’s app process (same AWS account is OK)
- Building our own multi-network publish stack before a vendor adapter is proven too limiting

---

## Suggested next coding slice

**Sources v2, phase 4 (S4).** Source of truth:
[`docs/planning/sources_v2.md`](sources_v2.md). **S1**, **S2**, and **S3** are done.
Do not start the theme picker until S4 is `[x]`.
Do not start product Phase 2. Posts that ship stay on `carousel_template_v1`
until a later slice binds a Live theme into `POST /api/v1/generate/carousel`.

