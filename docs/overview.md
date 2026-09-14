# Twerva

*Pronunciation: TWER-vuh*  
*Status: Seed note — 2026-09-13. Strategic spine: `docs/prompts/project.md`. Product: `docs/prompts/product.md`. Tasks: `docs/planning/task_sheet.md`.*  
*Relation: Sibling to Spotmu. Spotmu marketing owns the *what* to say; Twerva owns the *how* to package, push, and measure it across social platforms.*

---

## What it is

Twerva is an internal control plane for **bootstrap distribution**: take product content, turn it into platform-native posts (carousels first), publish at high cadence, and monitor results — without buying ads.

It is not a social network and not a virality engine. The bet is **durable average views × volume** (hundreds per post, enough posts that aggregate reach still hits millions), with topical clustering so accounts don’t look like spam farms.

Spotmu is **customer zero**. Twerva should stay general enough that another product or founder could plug in later.

---

## What we want it to be

### Near term (internal tool)
- A separate app (own folder, own build, own agents) that:
  - Ingests content sources (first: Spotmu interest briefs — title, `interest_heading`, `overview_bullets`, public `/interest/:slug` URL, logo/brand kit)
  - Renders calm, stylish carousel cards (text does the talking; brand mark + site on the last slide)
  - Queues / schedules / publishes to a small set of platforms (start narrow: Instagram + TikTok; expand later: YouTube, X, Threads, Bluesky)
  - Tracks performance (median views, not just mean; CTR / landing hits when available; suppression signals)
  - Supports kill / double-down by vertical cluster

### Later (possible product)
- The unique money model: sellers hook a product in; Twerva pushes and sells; **take a cut of each sale, $0 upfront** (never a paid-ads bidder). See `docs/prompts/project.md`.
- Sellers who graduate to buying platform ads directly are healthy churn — there are always more Kevins.
- Multi-source inputs (not only Spotmu); basic storefront when checkout must live in-path.
- Multi-brand / multi-account ops with warm-up rules and cadence caps

Design as if another seller could plug in later; don’t build self-serve seller ops until Spotmu’s distribution loop works.

---

## Business proposition (future)

**Problem:** Early products often have no capital for ads, no fame, and no network that converts at volume. Classic “valley of death” distribution.

**Offer:** Software that turns a product’s own information into a high-cadence, average-performing social presence — measurable, controllable, cheap to run relative to paid acquisition.

**Why it might matter:** Paid ads work better *after* you have signal and cash flow. Twerva is the rung before that — and if the system is good, it may be sellable as its own category (bootstrap marketing ops), not only Spotmu’s channel.

---

## MVP goals (help push Spotmu)

v0 is **Spotmu-shaped**, not generalist theater:

1. **Source:** Pull (or export) live Spotmu interest briefs — Point C fields + slug URLs.
2. **Artifact:** Interest-brief **carousels** (cover → heading → bullets → CTA with spotmu.com + `/interest/:slug`). Optional bot-reader video is later, not MVP.
3. **Platforms:** 2–3 max to start (IG + TikTok first).
4. **Ops:** Human approval gate before publish; topical account clustering; cadence caps; basic results dashboard.
5. **Success for MVP:** Spotmu landings get real traffic from Twerva posts; we can see which verticals repay effort; accounts stay above suppression floor (average views, not lottery virality).

Out of scope for MVP: character/mascot universes, full multi-tenant SaaS, paid-ads bidding, every platform on day one.

---

## Boundaries

| Spotmu (marketing / product) | Twerva (this project) |
|---|---|
| What Spotmu *is*, positioning, Interest SEO, In-app Share | Packaging, accounts, publish, monitor |
| Interest library + public slug pages as landing targets | Does not host Spotmu product UX |
| Maddy / Spotmu marketing agents interface when ready | Built & iterated by other agents |

Twerva must not become a second copy of Spotmu. Spotmu remains the content brain for customer zero; Twerva is the distribution machine.

---

## Open questions

- Exact ingest path from Spotmu (API vs export vs scrape of public pages)
- Brand kit + carousel visual template ownership
- Which vertical clusters to run first for Spotmu
- When (if ever) to open Twerva to a second internal product

---

## Name

**Twerva** — nonsense brand, spelled as heard: *TWER-vuh*. Domain availability to confirm at a registrar before purchase.
