# Twerva — Task Sheet

*Last updated: 2026-09-15*  
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
- [x] **1.4a-i** Write `docs/planning/carousel_template_v1.md`: slide roles (`cover`, `heading`, `bullet`, `cta`), canvas size (lock **1080×1080** IG-friendly unless spike says otherwise), typography/color tokens (calm, text-led; cite Spotmu palette lightly or neutrals), CTA rules (`cta_url` = source `canonical_url` or `https://spotmu.com/interest/{slug}`).
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
- [ ] Review queue UI (or CLI acceptable for first cut) — approve / reject / edit caption
- [ ] Cadence caps per account (simple rules)
- [ ] Scheduler: attach artifact → account → time

### 1.6 Publish (IG + TikTok)
- [ ] Spike **buy vs build publish**: unified API (Ayrshare / Zernio / Postiz) vs native Meta + TikTok APIs — prefer adapter + vendor for MVP unless spike says otherwise
- [ ] Implement `PublishAdapter`; connect 1–2 test accounts
- [ ] Publish worker; record platform post id / URL on success
- [ ] Failure handling + retry/backoff basics

### 1.7 Measure & steer
- [ ] Pull or enter views (automate what we can; manual OK at first)
- [ ] Cluster rollup with **median** views
- [ ] Kill / pause / double-down controls (even if coarse)
- [ ] Export or agent-readable summary for feedback into next generate

### 1.8 Ops console (thin)
- [ ] Sources · Generate queue · Calendar · Accounts/clusters · Results
- [ ] Ugly is fine; loop must be visible end-to-end

### 1.9 Agent hooks
- [ ] Document how agents draft artifacts and propose steer actions
- [ ] One dry-run playbook: “batch generate from Spotmu cluster X”

**Phase 1 done when:** a real Spotmu interest cluster has completed the loop at least once with human gate.

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

- Character / mascot universes
- Outfy-class “post only to seller’s own empty accounts” as the product
- Average-Joe one-SKU fully self-serve
- Paid ads bidding
- Multi-platform sprawl before IG+TikTok are boringly reliable
- Merging Twerva into Spotmu’s app process (same AWS account is OK)
- Building our own multi-network publish stack before a vendor adapter is proven too limiting

---

## Suggested next coding slice

**§1.4 done** (local carousel generate; S3 still parked). **Start at 1.5** (approval & schedule). No Engineer subs.

After 1.4: 1.5 approve → 1.6 publish adapter → 1.7 measure/steer stubs → 1.8 thin ops console.

