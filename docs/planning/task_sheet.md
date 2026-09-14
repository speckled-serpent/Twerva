# Twerva — Task Sheet

*Last updated: 2026-09-14*  
*Status: Big-stroke build plan. Strategy: `docs/prompts/project.md`. Product design: `docs/prompts/product.md`.*

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
- [ ] S3 bucket/prefix for artifacts — **parked** until carousel/media generate needs object storage
- [ ] Twerva-prefixed secrets in AWS SM/SSM — **parked**; Phase 1 secrets stay on-box (`/opt/twerva/*.env` mode 600)
- [x] Choose stack for ops console + workers: FastAPI + React/Vite/TS + Postgres (Celery/Redis later) — Spotmu-aligned
- [x] Empty app shells: `apps/server` (FastAPI healthcheck) + `apps/ops` (Vite React stub)
- [x] Healthcheck endpoint on the Twerva URL (`https://twerva.com/health` → systemd `twerva-api` / uvicorn on `127.0.0.1:8000`)

### 1.2 Domain model (minimal)
- [ ] Persist Brand/Source (Spotmu interest as first source type), Cluster, Account, Artifact, Post job, Metric snapshot
- [ ] IDs and statuses for draft → approved → scheduled → published → measured

### 1.3 Spotmu ingest
- [ ] Decide ingest path (API vs export vs public) — spike then lock
- [ ] Ingest `interest_heading`, `overview_bullets`, title, `/interest/:slug`, brand kit refs
- [ ] Map interests → clusters/lanes (manual assignment OK for MVP)

### 1.4 Carousel generate
- [ ] Carousel template (cover → heading → bullets → CTA + mark)
- [ ] Render pipeline to platform-ready images + caption
- [ ] Generate job: source item → artifact draft in review queue

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
- S3 / object storage for generated media (create when carousel/video pipeline needs it)
- AWS Secrets Manager / SSM (Phase 1 uses on-box env files)

- Character / mascot universes
- Outfy-class “post only to seller’s own empty accounts” as the product
- Average-Joe one-SKU fully self-serve
- Paid ads bidding
- Multi-platform sprawl before IG+TikTok are boringly reliable
- Merging Twerva into Spotmu’s app process (same AWS account is OK)
- Building our own multi-network publish stack before a vendor adapter is proven too limiting

---

## Suggested first coding slice (when we leave docs)

1. Domain + AWS service (Spotmu account) + empty app on `twerva.*` URL  
2. Domain model + empty ops console shells  
3. Spotmu ingest spike (one interest → stored source)  
4. Carousel render → object storage  
5. PublishAdapter spike (vendor) + one-platform publish  
6. Manual approve + metric/steer stubs  

That is the thinnest path to Phase 1 exit.
