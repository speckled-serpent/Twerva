# Twerva — Product

*Last updated: 2026-09-15*  
*Status: Big-stroke product design (seed). Strategy: `docs/prompts/project.md`. Build order: `docs/planning/task_sheet.md`. Spotmu handoff notes: `docs/overview.md`.*

---

## I. Product identity

Twerva is an **internal distribution control plane** (own app, own repo, own agents). It runs the middle node of:

```
content / brand world  →  Twerva (generate, approve, publish, measure, steer)  →  social platforms
```

**Phase 1–2 customer:** Spotmu (media hose).  
**Phase 3 proof:** internal brands / internal projects (brand-shaped commerce).  
**Phase 4 optional:** external brands / spin-off.

Not a social network. Not an ads bidder. Not an autoposter that only feeds the seller’s empty accounts.

---

## II. The loop (system heart)

Every feature must serve this loop:

```
1. Source     define what we are promoting (Spotmu interest / brand / SKU suite)
2. Generate   create platform-native artifacts (carousel first; basic short video later)
3. Gate       human approval (early); schedule
4. Publish    post via connected accounts / platform APIs or assisted publish
5. Measure    views (prefer median), CTR/landings when available, suppression signals, later sales
6. Steer      kill / keep / double-down by cluster; feed agents for next generate
```

If a piece does not tighten this loop, it waits.

---

## III. Core objects (conceptual model)

Big strokes only — schemas later.

| Object | Role |
|---|---|
| **Workspace** | Twerva install / ops context (us). |
| **Brand** | Content world + vibe + suite of promotable items. Spotmu acts as a special brand/source in Phase 1–2. Internal house brands in Phase 3. |
| **Source item** | Unit of raw material: Spotmu interest brief fields, or a product in a brand catalog, or an editorial brief. |
| **Cluster / lane** | Topical account group (purity for algorithms + kill/double-down grain). |
| **Account** | Platform identity (IG, TikTok, …) assigned to a cluster/brand. Ownership model TBD (Twerva-operated vs brand-owned). |
| **Artifact** | Rendered post asset(s): carousel slides, caption, optional video, CTA/link. |
| **Post job** | Scheduled/published instance of an artifact on an account. |
| **Metric snapshot** | Performance readback for a post job / cluster / brand. |
| **Steer action** | Kill, pause, boost cadence, change template — driven by metrics + human/agent. |

---

## IV. Phase 1–2 product shape (Spotmu pipeline)

### Ingest (Source)

First source: **Spotmu interest briefs**

- Fields (from Spotmu Point C / public surface): `title`, `interest_heading`, `overview_bullets`, public URL `/interest/:slug`, brand kit / logo refs
- Ingest path **locked** (1.3a): unauthenticated public JSON
  `GET {SPOTMU_API_BASE_URL}/api/v1/interests/slug/{slug}` plus sitemap
  `GET {SPOTMU_API_BASE_URL}/sitemap.xml` for slug discovery. Default
  origin `https://spotmu.com`. Live `/interests/slug/{slug}` without the
  `/api/v1` prefix is the SPA shell, not JSON. Brand-kit / logo refs are
  not on the public payload today (store `null`; keep extras in
  `raw_payload`). See `docs/reports/task_1_3_ingest_spike.md`.
- Each interest maps into a **cluster/lane** (vertical topical purity;
  manual `cluster_source_items` attach in 1.3e)

### Generate (Artifacts)

**MVP artifact: carousel**

- Slide sequence (draft): cover → heading → bullets (1–n) → CTA (spotmu.com + `/interest/:slug`, brand mark)
- Visual: calm, text-led; follow Spotmu design language where it does not fight platform norms
- Caption + hashtags generated with the carousel
- **Basic short video** only if it rides the same job pipeline without delaying carousel MVP

**Variety:** Spotmu’s changing briefs *are* the hose. Do not require a general brand-editorial engine in Phase 1.

### Gate

- Human approval before first publishes; keep a review queue
- Cadence caps per account/cluster
- Warm-up rules (light touch in MVP; harden in Phase 2)

### Publish

- Platforms: **Instagram + TikTok** first
- Mechanism: start with whatever is reliably automatable (official APIs, approved schedulers, or assisted publish) — exact connector stack is an implementation task, not a strategy debate
- No paid amplification / ads bidding

### Measure

- Per post: views (store distribution; report **median** across a cluster, not only mean)
- Landing hits / CTR when UTM or Spotmu analytics available
- Suppression signals (sudden reach collapse, account flags) — even if coarse at first
- Dashboard: cluster-level rollup sufficient for steer

### Steer

- Kill / pause a cluster
- Double-down (raise cadence or concentrate generate) on clusters above floor
- Agent-readable summaries so next generate batch learns (template tweaks, topic mix)

### Explicitly out of MVP

- Character / mascot universes
- External self-serve sellers
- Storefront / checkout
- Multi-tenant billing
- Every platform
- Orphan-SKU commerce engine

---

## V. Phase 3 product shape (internal brands)

When Spotmu loop is real, extend the **same objects** to brand-shaped commerce:

- **Brand** becomes first-class: vibe, editorial calendar, product suite
- **Source items** = products + brand story briefs (not one hero photo on loop)
- **Content engine** = brand-world posts (lifestyle, process, series, suite features) with SKUs riding along
- **Measure** adds sales / attribution when selling in-path
- **Storefront** (basic) may appear so purchase lives in the loop
- Money model trial: cut vs subscription (see `project.md`) — product must support either without becoming an ads tool

Average-Joe one-SKU self-serve remains out of core scope.

---

## VI. Phase 4 product shape (external / spin-off) — optional

- External makers plug into Twerva-carried brands (vetting/grouping)
- Hardening: account ownership handoff, trust/non-compete posture, dupe policy
- Possible spin-off packaging of Twerva or brand houses
- Still never an ads bidder

Success of Twerva does **not** require Phase 4.

---

## VII. Surfaces (operator UX — big strokes)

MVP is an **ops console**, not a consumer app:

1. **Sources** — connected Spotmu interests / later brand catalog
2. **Generate queue** — draft artifacts awaiting review
3. **Calendar / schedule** — what posts when, on which accounts
4. **Accounts & clusters** — health, cadence caps, lane assignment
5. **Results** — medians, landings, kill/double-down controls
6. **Steer log** — what we changed and why (for agents + humans)

Polish and permissions follow need; Phase 1 can be ugly if the loop is true.

---

## VIII. Agents & automation

Twerva is built to be run with agents:

- Generate drafts from sources
- Propose schedules within caps
- Summarize metrics and recommend steer actions
- Humans keep approval gate until trust is earned

Agent prompts and runbooks live alongside the app; product must expose clean artifacts and metrics for them.

---

## IX. Non-goals (product)

- Rebuilding Spotmu UX inside Twerva
- Posting only to the customer’s pre-existing empty social accounts as the whole product (Outfy-class)
- Buying or bidding platform ads
- Virality-as-a-service / engagement bait that breaks topical purity
- Infinite self-serve orphan SKUs
- Hosting Twerva *inside* the Spotmu app/process (separate service — see §X). Sharing the Spotmu **AWS account** is fine and preferred for now.

---

## X. Separate home & build vs buy

Twerva gets its **own URL and basic server process**, separate from Spotmu’s app. Sibling product, sibling deploy. Spotmu remains a *source* (and Phase 1–2 customer), not the host process.

**AWS account (locked for now):** run Twerva **inside the existing Spotmu AWS account** for one bill and one place to watch cost/IAM. Still a **different service** (own compute, own DB/schema or database, own storage prefix/bucket, own DNS name). If Twerva ever spins out as its own business, split accounts later — easy compared to untangling a shared process. Not a mistake to share the account early.

### Always rent / buy (do not build)

| Need | Lean default | Why |
|---|---|---|
| **Domain** | `twerva.com` or available variant (confirm registrar) | Brand + stable ops URL |
| **App host** | Own service on **Spotmu’s AWS** (ECS/EC2/App Runner/Lightsail — pick whatever Spotmu already operates comfortably) | Separate process; same bill |
| **Database** | Managed Postgres on that account (own instance or clearly separated DB/schema) | Do not share Spotmu app tables |
| **Object storage** | S3 on that account (own bucket or hard prefix) | Carousel frames, video, exports |
| **Secrets** | AWS Secrets Manager / SSM (Twerva-prefixed) | Platform tokens never in git |
| **TLS / DNS** | ACM + Route53 (or existing Spotmu DNS pattern) for the Twerva hostname | Table stakes |

### Buy first for MVP publish (replace later if needed)

Instagram + TikTok official publish APIs work but are slow to certify (Meta app review / business verification; TikTok audit before public posts). For an **internal** multi-account control plane, a **unified publish API** is usually the right first spike:

- Candidates: **Ayrshare**, **Zernio** (formerly Late), Buffer API (weaker multi-tenant), open-source **Postiz** if we want self-host
- Job: OAuth accounts → schedule/publish → return platform post ids; optionally pull basic analytics
- We still **own** generate, approve, clusters, steer, Spotmu ingest — the product

Wire a thin `PublishAdapter` so swapping vendor ↔ native Meta/TikTok later does not rewrite the app.

### Build (this *is* Twerva)

- Domain model + ops console
- Spotmu ingest + (later) brand catalog
- Carousel / artifact render aligned to brand
- Approval, cadence caps, cluster steer
- Metric rollups (median) + agent hooks
- Phase 3 brand content engine + optional storefront

### Build only when painful to buy

- Deep custom analytics beyond vendor/platform insights
- Exotic anti-detect multi-browser farms (avoid as long as official/API path works; ToS/spam risk)
- Full CMS / Shopify clone (Phase 3 storefront = thinnest checkout that closes the loop)

### Rule of thumb

**Rent pipes. Build the brain.** Hosting, storage, and “post this media to account X” are pipes. Source → generate → gate → measure → steer is the brain.

### Stack (locked for Phase 1)

Prefer Spotmu alignment to reduce friction:

| Layer | Choice |
|---|---|
| **Ops UI** | React + TypeScript + Vite (+ Tailwind as needed) |
| **API** | Python 3.11+ / FastAPI |
| **DB** | PostgreSQL (SQLAlchemy) — own DB on Spotmu AWS |
| **Jobs** | Celery + Redis when we need async render/publish/metrics (not day-one blocking) |
| **Layout** | Monorepo: `apps/server`, `apps/ops` (console), `packages/`, `tools/` |

Do not invent a third stack without revisiting this table.

---

## XI. Open product questions

- Spotmu ingest path — **locked**: public JSON + sitemap
  (`docs/reports/task_1_3_ingest_spike.md`)
- Carousel template ownership vs Spotmu brand kit
- Publish connectors (API vs assisted) per platform
- Account ownership model
- Metric plumbing into Spotmu analytics
- Brand content engine design (Phase 3)
- Storefront MVP shape (Phase 3+)
- Cut vs sub instrumentation
- Exact AWS service shape beyond current EC2+nginx (RDS vs Postgres-on-box for early Phase 1; S3 bucket name)
- Publish adapter: Ayrshare vs Zernio vs Postiz vs native APIs first

---

## XII. Success criteria (by phase)

| Phase | Product success |
|---|---|
| 1 MVP | One Spotmu cluster can complete the loop with human gate |
| 2 Spotmu | Multiple clusters; median views above suppression floor; steer actions routine; Spotmu traffic signal visible |
| 3 Internal brands | One internal brand world cadences without still-spam; sales or strong proxy attribution |
| 4 External | Optional — external carry or spin-off without breaking trust/content math |
