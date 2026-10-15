# Twerva — Project Overview

*Pronunciation: TWER-vuh*  
*Last updated: 2026-09-14*  
*Status: Authoritative strategic seed. Product design: `docs/prompts/product.md`. What's left: `docs/planning/phase_map.md`. Spotmu handoff notes: `docs/overview.md`.*

---

## I. What Twerva Is

Twerva is a **bootstrap distribution control plane**: software that turns a product’s own information into a high-cadence, platform-native social presence — packaged, published, measured, and steered — without buying ads.

It is not a social network and not a virality engine. The bet is **durable average performance × volume** (hundreds of views per post, enough posts that aggregate reach still compounds), with topical clustering so accounts stay coherent instead of looking like spam farms.

**Working slogan (draft):** Twerva — push it, sell it, share the win. ($0 upfront.)

Spotmu is **customer zero**. This document treats Twerva as if it were (or could become) its own business. Whether it stays an internal machine that makes Spotmu (and later other products) money, or becomes the cut-of-sale platform for many Kevins, both are wins. Design as if another seller could plug in later; do not build self-serve seller ops until the distribution loop works.

### What it does (in one loop)

```
Define content source
  → generate platform-native posts (carousels first; basic short video later)
  → approve / schedule / publish
  → track results
  → feed signal back into agents and ops (kill, double-down, refine)
```

That closed loop is the product. Everything else is a feature of it.

### Content volume vs content variety (critical constraint)

The strategy needs **lots of posts**. Platforms reward cadence; the median-views × volume bet assumes we can keep publishing without looking like a spam farm.

**Spotmu fits this naturally.** It is a media product: Point C briefs, interest headings, overview bullets, fresh stories — an endless hose of *new* informational content. Posting high cadence is aligned with what the product *is*.

**A lone SKU mostly does not.** A lamp, a mug, one pottery bowl, one clever tee — if you repost the same hero (or thin variants) you get **suppressed**, not traction. Autoposters that recycle catalog stills hit this wall. “Connect one product → spam stills” is not a pipeline. Even “clever angles on the same lamp” may not be enough *that* well at the volume we need.

### Working answer: sell brands, not orphan products

The difference between selling **a chair** and selling **Article** (a hip online furniture brand): brand has vibe, story, point of view, and a **suite** of products under one grouping. Content can be about the world of the brand — lifestyle, taste, process, characters, seasons, editorial — while products ride along. That overcomes the single-object content desert.

**Implication:** we probably cannot hand Twerva to the average Joe with one idea and say “have at it, we’ll just sell your thing.” Average-Joe-with-one-SKU is a weak unit of distribution.

**More plausible Phase 3+ shape — Twerva carries into brands:**

1. **Define brands** (house or tightly partnered): e.g. a handcrafted/artisan brand, a funny/slogan brand, other clear vibes — not infinite one-off shops on day one.
2. **Vet and group products** that fit those brands (selection process — we choose what we carry).
3. **Sell the brand** on social: develop ongoing brand content (the hose), with SKUs integrated into that story.
4. Makers/suppliers plug into a brand that already has a content engine — closer to “we carry you” than “self-serve autopilot for anyone.”

That is more extensive (brand-building, curation, editorial). It is also a coherent fix for cadence + variety + topical purity. Self-serve “any Kevin, any single SKU” may stay a later or narrower mode — or never be the core.

**Spotmu** remains the Phase 1–2 content hose while we prove the loop. Non-media expansion assumes **brand-shaped inventory**, not orphan-SKU inventory.

### What it is *not*

- Not Spotmu, and not a second copy of Spotmu’s product UX
- Not a creator studio optimized for one viral hit
- **Not a paid-ads bidder — ever.** That market already exists; anyone with budget is better off buying from the platforms directly. Twerva is the rung *before* ads, not a worse Meta Ads Manager.
- Not multi-tenant SaaS / subscription billing on day one (revenue is a cut of sales when the model is live)
- Not a character / mascot universe on day one (may arrive after the loop works)

---

## II. The Problem

Early products often sit in the **valley of death**: no ad budget, no fame, no network that converts at volume. Classic channels either need capital (ads, influencers), time that does not scale (manual niche grind), or assets the founder does not have yet (audience, partnerships).

Meanwhile the product already *has* information worth distributing — landing pages, briefs, specs, offers — but turning that into a steady, measurable social presence is still mostly hand labor: rewrite for each platform, babysit accounts, guess what worked, repeat.

**Twerva’s gap:** get a real product in front of people and **require $0 upfront** — distribute, sell, take a cut only when something actually sells. That is the rung before paid acquisition works.

---

## III. Business Proposition (as a separate business)

Treat Twerva as its own company for planning purposes, even if ownership and ops stay under the same roof as Spotmu for a long time.

### The unique idea (product)

**Twerva is the middle-node distribution machine:** hook products into a **brand-shaped** push on real social pipelines (not just your empty accounts); we sell / route to purchase; we measure and steer. Orphan one-off SKUs are a weak unit; curated brands with product suites are the working content answer outside Spotmu.

That is the product distinction vs ~$25/mo auto-posters (they only post to *your* accounts). **How we charge for that** — cut of sales vs subscription vs hybrid — is still an open strategic choice (see “Money model options” below). The leading story has been cut + $0 upfront; subscription is back on the table because it is easier to cash-flow and harder to differentiate.

### The three-node pipeline

```
Creator (Kevin)  →  Twerva (middle)  →  Discovery platforms (IG / TikTok / YouTube / …)
idea + product        marketing, sales,        where buyers actually see it
                      ops, measurement
```

- **Upstream:** the idea person — clever product, little or no capital, little or no reach. They should be able to stay focused on the product.
- **Middle:** us — the hard operational part: package, push, sell, track, steer. Take a cut when it works.
- **Downstream:** the social platforms — the discovery pipe we do not own.

Threats run **both directions along this chain.** Platforms can squeeze or copy Twerva (see SWOT). Twerva can also look like a threat *to Kevin*: we see which products sell, we run the promotion, and for easily copied goods we could be tempted to cut him out. Kevin is not an idiot forever — if that temptation is credible, he never joins (or leaves fast). **Ripping off sellers is not a business model; it collapses the funnel.** Trust with the creator node is as structural as platform dependency.

### Offer

A company (or founder) connects a product or service. Twerva:

1. Turns that product’s information into high-cadence, platform-native posts
2. Puts it in front of people
3. Routes buyers to a purchase path (eventually a basic Twerva-generated storefront when needed)
4. Under the **cut** money option: takes a cut when a sale happens ($0 upfront). Under a **subscription** option: charges for access to the pipeline (and still should kill what does not work).

Leading story is still cut-aligned: if nothing sells, Kevin should not be funding hope. Subscription trades that purity for steadier cash — see money model options.

### The Kevin story (canonical example)

Kevin designs clever-slogan T-shirts. He knows fashion and humor. He has almost no capital — maybe enough for a few samples. He can work with a supplier so that **if** a shirt sells, the unit cost is covered in the price; he does not need a warehouse full of inventory to start.

What he cannot do is get anyone to *see* the shirts. He cannot pay TikTok, Google, or Meta for ads.

He makes a Twerva account, hooks in the shirts, and creates samples to push. Twerva promotes and sells for him, taking a cut per sale, requiring **no money upfront**. If the shirts do not sell, Kevin is out nothing on Twerva fees; we stop pushing him — fine, other Kevins are on the platform. If they do sell, both win. If they do *really* well, Kevin may eventually buy ads from the big platforms to scale further and maybe graduate off Twerva. That is okay. There are a lot of Kevins — and now Kevin is making money too.

**Caveat on the shirt example:** T-shirts are easy to understand and easy to *duplicate* (trust risk). A *single* tee is also a weak content hose (variety risk). Better unit: a **funny/slogan brand** with a rotating suite of designs under one vibe — Kevin as contributor to a brand we carry, not as a one-SKU autopilot client. See content/brand section above and Etsy/trust notes in competitive landscape.

### Who it is for

1. **Internal / founder-operator (near term):** us — Spotmu first (learning the loop; Spotmu is already “brand-shaped” media content).
2. **Products that fit Twerva-carried brands (Phase 3 thesis):** makers/suppliers whose goods can live under a curated vibe (handcrafted, funny, etc.) — not necessarily “any lone SKU from any Joe.”
3. **Scaled graduates (if applicable):** brands or sellers who outgrow Twerva into their own ads. Healthy churn if the brand roster refills.
4. **Self-serve average Joe with one idea:** *skeptical / deferred.* Content economics argue against this as the default unit.

### Why it might matter

Paid ads work better *after* you have signal and cash flow. Twerva is the rung before that — **never an ads bidder**. If the distribution loop is good, Twerva matters first as Spotmu’s channel and as the engine for **internal brands / projects**. External brands or a spin-off are a mature upside — **not required** for the project to have been worth it. Exact monetization is undecided; the product must stay “real pipeline,” not “prettier posts on a dead feed.”

### Money model options (open — cut vs subscription)

Auto-posters (Outfy, Xyla, etc.) charge ~$20–50/mo to post to **your** accounts. They mostly suck as a *growth* product for no-reach Kevin — but their **subscription** cash model is simple: paid whether or not anything sells. Twerva should not copy their product; we might still copy (or reject) their *pricing shape*. Both options stay live:

#### Option A — Cut of sales ($0 upfront)

**Shape:** promote → sell → take a cut. Kevin pays nothing until something sells.

| Pros | Cons |
|---|---|
| Matches the “no money” half of Kevin | Need enough winners to cover losers (goldilocks + churn pressure) |
| Easy to explain vs ads and vs autoposters (“we only win if you win”) | Harder cash-flow early; we fund the pipe |
| Incentive alignment is the category story | Temptation/trust issues on easy-copy goods; cut design is delicate |
| True $0-upfront pitch | Spotmu (subscription product) is an awkward first “cut” customer |

#### Option B — Subscription (SaaS)

**Shape:** Kevin (or a small brand) pays monthly for access to Twerva’s **real** pipeline — not autopost-to-yourself, but Twerva-operated distribution / ops (and maybe storefront tools).

| Pros | Cons |
|---|---|
| Paid regardless of whether this week’s SKU is a winner — less pressure to “fish for whales” | Collides with “Kevin has $0” — who can pay $29/mo still isn’t the broke creator |
| Simpler ops and forecasting | **Differentiation gets harder:** story becomes “our pipeline is better than Outfy,” not a different deal |
| Familiar buyer motion for brands that already have *some* cash | Looks like another social SaaS in a crowded shelf |
| Can still attach usage / success tiers later | Risk of product sliding into autoposter feature-parity wars |

#### Option C — Hybrid (possible later)

e.g. low/no sub for true bootstrap + cut; or sub for capacity + lower cut; or cut that depreciates with volume. Not designed yet — flag only.

### Tentative staging (either money model)

| Stage | What matters |
|---|---|
| Phase 1 — MVP | Build the loop. Revenue model can wait. |
| Phase 2 — Spotmu | Learn on the media hose (traffic / signups). |
| Phase 3 — Internal brands | Brand-shaped proof; **trial cut vs sub** on inventory we control. Storefront if needed. |
| Phase 4 — External / spin-off | Optional mature state. **Still not** an ads bidder. Success does not require reaching here. |

**Non-goals (either model):** becoming a paid-ads bidder; competing with Meta/Google/TikTok ads managers; becoming “Outfy with a Twerva logo” (post-only-to-your-accounts).

**Status:** Cut + $0 upfront remains the **leading narrative** and the sharpest wedge on paper. Subscription is a **credible alternative** if cut economics or Kevin-trust prove too hard — accept that the pitch then rests on pipeline quality, not deal structure. Decision deferred until we have loop proof (and ideally one Phase 3 experiment). Details (cut rate, sub price, payouts, storefront) = later docs.

### Relationship to Spotmu

| Spotmu | Twerva |
|---|---|
| What the product *is*, positioning, Interest SEO, in-app Share | Packaging, accounts, publish, monitor, feedback loop |
| Content brain for customer zero (interest briefs, brand kit, landings) | Distribution machine |
| Marketing agents (e.g. Maddy) own the *what* | Twerva agents own the *how* |

Twerva must not become a second Spotmu. Spotmu remains the content and brand source for customer zero; Twerva ships and measures.

---

## IV. Competitive landscape

Checked 2026-09-13. **Pieces of this exist. The exact combo does not look like a crowded category.** That is not a free pass — it means stay sharp on differentiation.

### The customer we actually serve

Most tools assume the seller has **money** *or* **reach** (or both). Twerva’s Kevin has **neither**. That is still most people with an idea: a real product (or samples + a supplier), no ad budget, no audience.

### What already exists (adjacent, not twins)

| Neighbor | What they do | Why they are not Twerva |
|---|---|---|
| **Creator / affiliate commerce** (TikTok Shop affiliates, ByTheLook, Sendd, Favly, link-in-bio shops, etc.) | Brand pays a cut only when a *creator with an audience* sells. Often $0 upfront for the brand on commission. | Kevin still needs someone else’s reach. Twerva *is* the reach machine. |
| **AI social for your store** (Outfy, Xyla, Apaya, similar) | Auto-generate posts from a catalog; schedule to **the seller’s own** accounts (~$20–50/mo). | Weak as a growth pipeline (no owned reach). Strong as proof that **subscription** for “social help” sells. Twerva must not become this; we might still debate copying the fee shape. |
| **Performance agencies** (revenue-share / “we fund the ads”) | Agency takes ad risk; brand pays a cut of attributed sales. | That is **ads risk transfer**. Twerva is never a paid-ads bidder. |
| **POD / Shopify / store builders** | Help Kevin make, list, and fulfill product. | Marketing is still his problem (or paid ads / hoping affiliates show up). |
| **Etsy-like marketplaces** | Destination shop: sellers list; buyers who already go to Etsy discover them. Historically “Amazon for handmade.” | Etsy does **not** run outbound social distribution for you. Discovery is “come to the mall.” Twerva is **mall + marketing team**, paid on sales. |

### Primary competitor framing: Etsy (with a twist)

We go about this differently from ads tools, but the **category gravity** to watch is closer to **Etsy** than to Meta Ads Manager:

| | Etsy (classic pitch) | Twerva |
|---|---|---|
| Discovery | Buyers learn to go to Etsy | Twerva **pushes** the product out to where attention already is |
| Seller job | Make / list / hope for search & traffic inside the mall | Make the product; Twerva handles marketing + sales path |
| Money | Listing / transaction fees on the destination | **Cut of sales**, **$0 upfront** for promotion |
| Long pivot rhyme | Owned marketplace | “Surprise” path toward **Etsy-with-marketing** / storefront gravity if scale warrants |

Etsy’s notorious failure mode is also a warning: **dupes** — dropshipped lookalikes crowding out real small makers until buyers cannot tell the old lady’s garage pottery from the factory copy. Twerva inherits a version of that problem the moment many sellers list near-identical easy goods (twelve Kevins, one slogan shirt).

### Hard-to-copy goods (trust niche) vs burning any fuel

**Honest pitch problem:** if Kevin’s product is a clever slogan on a blank tee hooked to a print shop, Twerva’s own data will eventually ask: *why keep paying Kevin?* We run the promo; the shirt is commoditized; we could clone it. Contracts that say “we will not steal your idea” help on paper, but:

1. Kevin will anticipate the temptation and may never onboard easily-copied SKUs — or will leave when he notices.
2. Even if *we* never clone him, **sellers rip each other off** (and factories rip everyone). Ranking / fairness across near-duplicates is a mess.
3. A platform that lives on ripping its upstream cannot refill the funnel.

**Implication (big picture, not a freeze):** when marketing Twerva *to sellers*, lean the face of the brand toward goods that are **harder for us (and others) to duplicate** — handcrafted, made-to-order artisan, personal skill, limited authentic supply — the stuff classic Etsy was supposed to be. That is how we can honestly say: we cannot just plug your pottery into our factory and cut you out.

**Engine implication:** build a distribution engine that can run **brand-shaped** inventories. Easy goods may still appear *inside* a funny/slogan brand (suite of designs), not as lonely one-offs. Do not confuse “pipeline can render a product shot” with “orphan SKU is a viable social product.”

### Our wedge (product locked; money model open)

**Product (locked):** Twerva runs distribution **itself** at volume — generates platform-native content, publishes through a real pipeline (not only the seller’s empty accounts), sells / routes purchase when needed, measures, steers. **Never** an ads bidder. Not another affiliate marketplace. Not another $29/mo auto-poster that only feeds *your* feed.

**Money (open):** cut-of-sales (+ $0 upfront) vs subscription vs hybrid — see §III. Auto-posters prove subscription can sell *tools*; they do not prove subscription is the right price for *being Kevin’s middle node*. If we subscribe, our claim must be “better pipeline,” not “we post to your Instagram too.”

Full SWOT (including platform dependency and goldilocks-seller economics): **§V**.

---

## V. SWOT analysis

Seed SWOT — 2026-09-13 (updated same day: three-node trust + Etsy/dupe). None of the threats below are treated as dealbreakers today; they are things to stay conscious of as we build. Too early to optimize for empire-defense. Not too early to name them.

### Strengths

- **Clear wedge:** no money *and* no reach — still most people with an idea; neighbors usually assume one or the other.
- **Aligned incentives (when we keep them):** paid on sales (a cut), not on hope or ad spend — *if* we do not become Kevin’s competitor on his own SKU.
- **Possible trust niche:** hard-to-copy / handcrafted goods make “we won’t / can’t just rip you off” credible; sets up Etsy-with-marketing positioning.
- **$0 upfront for Kevin:** removes the classic valley blocker (pay for airtime before any proof).
- **Cost shape can be favorable:** we are not buying ads; AI + owned posting keeps marginal promotion cost low if we stay disciplined (Spotmu lesson: manage costs, take the profit — do not need heroic hit rates).
- **Customer zero exists:** Spotmu lets us build and harden the loop before the cut-of-sale thesis has to carry the company.
- **Graduation is healthy churn:** winners who leave for Meta/TikTok ads free capacity for the next Kevin — if we can refill the funnel.

### Weaknesses

- **Goldilocks / transitory seller slice (biggest structural weakness on paper).** We need products good enough to sell *some* units, but not so strong (or so well-funded) that Kevin immediately cuts us out and buys ads himself. How wide that band is — and how long a product stays in it — is debatable. Most ideas are bad; that is reality, not cynicism.
- **Aggressive winner churn.** Success graduates sellers off the platform. We must replace winners fast enough while covering the cost of losers. The business is less “maximize one whale” and more “fish for the few viable products, keep costs low, harvest the middle.”
- **Cold-start economics.** We eat content and account cost before any cut lands.
- **Spotmu fit mismatch.** Customer zero is a subscription product, not a classic SKU cut — great for learning the loop; Phase 3 is when the money thesis is really tested.
- **Account ownership unresolved.** Kevin may need ownership of accounts made for his brand; model deferred (see open questions).
- **Ops complexity.** Multi-account, multi-platform, anti-spam discipline is hard even when the idea is simple.
- **Middle-node temptation / trust deficit.** We see the sales data and run the promo. For easily copied goods, cloning Kevin is economically tempting and strategically suicidal if he (and the next hundred Kevins) can see it coming.
- **Dupe / derivative swamp.** Even with clean hands toward Kevin, many near-identical listings (or factory lookalikes) create fairness, ranking, and brand-trust problems — Etsy’s open wound.
- **Orphan-SKU content desert.** High cadence needs *new* posts. Spotmu has news; one lamp/tee/bowl does not. Single-product promotion at Twerva volume is likely a **killer** for the naive Phase 3 plan. Brand-shaped suites are the proposed fix — and they raise the bar (curation, editorial, not pure self-serve).

### Opportunities

- **Huge top-of-funnel of Kevins** if the loop works at low cost — AI makes testing many ideas cheaper than it used to be.
- **Vetting / betting layer.** Pre-test content or product signal before full push; kill losers early; keep the portfolio profitable without needing a massive success rate.
- **Cut design levers.** e.g. higher cut early, depreciating as unit volume grows — compensates for graduation risk and funds losers. Exact schedule later.
- **Etsy-with-marketing.** Same long rhyme as storefront gravity: promote authentic makers outbound, take a cut, maybe later own more of discovery+checkout — without requiring Kevin to already have mall traffic.
- **Lead with hard-to-copy categories** in seller marketing (pottery, artisan, skill-bound goods) while still allowing the engine to run broader fuel.
- **Brand-led carry model.** Create/operate a small set of brands; vet products into them; sell the brand vibe with a product suite underneath. Solves cadence/variety; becomes “Etsy-with-marketing” via curated houses rather than infinite one-off shops.
- **Editorial as moat.** Brand storytelling + grouping is harder to copy than catalog autopost — useful under cut *or* subscription.
- **Multi-platform non-coordination.** Even if one network copies or squeezes us, they do not move as one; diversification across IG / TikTok / YouTube / others is structural optionality.
- **Internal success is enough.** Spotmu + internal brands can justify Twerva even if external carry / spin-off never happens.

### Threats

- **Platform dependency (downstream vulnerability).** TikTok, Instagram, YouTube, etc. control the marketing pipe. If Twerva worked at serious scale they would be incentivized to cut off posting access (hard, but possible) or — more likely — **offer a similar “we promote, you pay on results” service themselves**.
  - *Why this is not a dealbreaker now:* we would already have to be successful enough to be worth their attention — which is already a win. Platforms will not perfectly coordinate. At that scale, pivots exist (e.g. lean harder into owned storefront / Etsy-like gravity, deepen multi-platform, other surfaces). **Note it; do not build the company around fearing it yet.**
- **Upstream trust failure (mirror threat).** If sellers believe Twerva will skim winning SKUs (or cannot stop a dupe free-for-all), they never supply the top of the funnel. Contracts help; **category choice and visible non-compete norms** matter more. Sustaining by ripping off customers does not work.
- **Etsy-dupe dynamics.** Easy-to-copy catalog + success signal → flood of derivatives → buyers lose trust → real makers leave. Same disease, different mall.
- **Spam / suppression / ToS.** High-cadence multi-account ops can look like a spam farm; platforms can throttle or ban without “copying” us. Repetitive product-still posting is a fast path to the same death.
- **Unit economics failure mode.** If vetting is weak and most ideas are noise, loser costs swamp winner cuts even with cheap AI posting.
- **Cut compression.** Sellers (or competitors) push take-rates down; graduates leave before we have recouped acquisition/ops cost.
- **Category confusion.** Market lumps us with ads tools or $29 auto-posters and we fail to explain the wedge.

### How we think about viability (for now)

**If cut (Option A):** probably **not** viable if it requires a massive hit rate. May be viable if marginal cost stays low, losers die cheap, cuts on winners cover the rest, and graduates are replaced fast. Spotmu spirit: cost control, then take the profit.

**If subscription (Option B):** less need to “find winners” for revenue — but Kevin-with-$0 is a worse fit, and we must win on **pipeline quality** against cheap autoposters. Viability then looks more like classic SaaS (retention, differentiation, cost to serve) than portfolio fishing.

Either way: do not buy ads; do not become Outfy-with-extra-steps.

---

## VI. Design Principles (high level)

1. **Loop over features.** Ingest → generate → publish → measure → update agents. If a piece does not serve the loop, it waits.
2. **Median, not lottery.** Optimize for staying above the suppression floor and compounding volume — not for hoping one post explodes.
3. **Topical purity.** Cluster accounts and content by vertical so platforms can route them cleanly and humans can kill or double-down by cluster.
4. **Human gate early.** Approval before publish until trust in the pipeline is earned.
5. **Customer-zero honest, general by design.** Ship Spotmu-shaped first; keep interfaces general enough that a second product is not a rewrite.
6. **Calm packaging.** Text and structure do the talking; brand mark and site land on the last beat. Style follows the source brand (for Spotmu: Cognitive Calm), not engagement-bait chrome.
7. **Measure what steers.** Views (prefer median), landing hits / CTR when available, suppression signals, and — once selling — **sales and cut**, by product/vertical. Enough to change what we generate next.
8. **Money model serves the product.** Prefer outcome alignment (cut) when targeting true $0 Kevins; accept subscription only if we still sell a real pipeline — never hope-as-a-service and never autoposter cosplay.
9. **Do not look like spam.** Cadence, topical clustering, and quality floor protect accounts and sellers. Account ownership / handoff for Kevin is acknowledged as a real issue and deferred — not hand-waved.
10. **Cost control over hit-rate fantasies.** Portfolio must work if only a minority of products succeed. Vet early, kill losers cheap, harvest winners, replace graduates. See SWOT.
11. **Do not eat the upstream.** Twerva competes for attention downstream, not against Kevin’s SKU. Cloning sellers’ winners to cut them out collapses trust and the funnel. Prefer categories where that temptation is structurally weak; never treat rip-offs as strategy.
12. **Brand before orphan SKU.** High volume needs a content world, not one object on repeat. Prefer brand vibe + product suites (Twerva-carried / curated). Do not ship “same lamp photo × 200,” and do not assume average-Joe one-idea self-serve is the default.

---

## VII. Roadmap

Rough phases. Dates are not commitments; exit criteria are.

**Through-line:** Spotmu proves the basic pipeline. **Internal brands** (and other internal projects) are the real proof of concept for brand-shaped commerce. **External brands / spin-off** is the mature state — valuable if we get there, **not required** for Twerva to have been worth building. If MVP + Spotmu + internal brands work well enough, that alone is a win.

### Phase 1 — MVP

**Goal:** Something that works end-to-end.

Build the full loop:

- Define / ingest content (first: Spotmu interest briefs and landing URLs)
- Generate posts — **carousels first**; basic short video only if it does not break the loop
- Publish to a narrow set of platforms (IG + TikTok first)
- Track results
- Feed signal back into agents (kill / keep / double-down)

**Exit:** Spotmu-shaped run can go brief → post → publish → numbers → decision inside Twerva. Not every platform or format — the loop.

### Phase 2 — Spotmu

**Goal:** Use Twerva for real Spotmu distribution; harden the basic pipeline.

Spotmu is the natural content hose (media / news-shaped). Run volume, iterate creative and clustering, prove durable average × volume moves traffic and signups. Ops become steering, not firefighting.

**Exit:** Clear vertical signal; stable Spotmu loop. Pipeline is real, not demo-ware.

### Phase 3 — Internal brands & other internal projects

**Goal:** **Real proof of concept** beyond Spotmu — brand-shaped inventory we control.

Stand up Twerva-carried **internal brands** (e.g. handcrafted vibe, funny/slogan vibe) and/or plug other internal projects into the same rails. Vet/group products into those brands; develop brand content as the hose; sell the suite. Trial money model (cut vs sub) here with eyes open. Storefront may appear in-path.

This is where we learn whether brand-led carry actually beats orphan-SKU death — on inventory we own or closely control, before trusting the machine with strangers’ livelihoods at scale.

**Exit:** At least one internal non-Spotmu brand (or internal project) has run the full loop with real sales/learning attribution. Content variety under a brand world is demonstrated, not theoretical.

### Phase 4 — Spin-off & external brands

**Goal (mature state, optional):** Open the carry model outward — external makers into Twerva brands, and/or spin Twerva (or brand houses) into a clearer external business. Self-serve only if it does not reintroduce orphan-SKU failure modes.

**Not required for success.** If Phases 1–3 already make Spotmu and internal bets work, Twerva paid for itself. Phase 4 is upside and scale, not the definition of “worth it.”

**Exit (if pursued):** Deliberate external operating shape — curated external carry, spin-off entity, or park and stay internal. **Never** a paid-ads bidder.

### After Phase 4 (etc.)

Only if earlier phases earned it: more brands, denser catalogs, tighter editorial, possible wider marketplace experiments. Do not plan empire details now.

---

## VIII. Near-term product shape (Phase 1 reminder)

Still big-picture, not a spec:

- **Artifacts:** Interest-brief carousels (cover → heading → bullets → CTA with site + deep link). Basic short video only if it rides the same pipeline. Spotmu is the Phase 1 hose; non-media expansion assumes **brand content worlds**, not orphan-SKU stills.
- **Platforms:** Few. Instagram + TikTok first.
- **Ops:** Human approval; topical clusters; cadence caps; basic results dashboard; kill / double-down by cluster.
- **Success for MVP:** Spotmu landings get real traffic from Twerva posts; verticals can be ranked by repayment; accounts stay above a suppression floor.

Out of scope until later phases: character universes, self-serve seller billing UX, storefront MVP details, every platform on day one. **Permanently out of scope:** paid-ads bidding.

---

## IX. Open questions (parked for later docs)

- Exact ingest path from Spotmu
- Brand kit and template ownership
- First vertical clusters to run
- When to open Twerva to a second (sellable) product — Phase 3 trigger
- **Money model choice:** cut vs subscription vs hybrid (and what Phase 3 experiment decides it)
- Cut rate, payouts, chargebacks, and storefront MVP shape (including whether early cut is higher and depreciates with volume)
- If subscription: price, who can pay, and how we stay visibly different from Outfy/Xyla-class tools
- Vetting / betting process so losers die cheap before full push
- How Spotmu (subscription product) maps onto a cut-of-sale story vs staying a pure distribution customer-zero
- Account ownership model for Kevin (Twerva-operated vs seller-owned; handoff when he graduates or churns)
- Anti-spam / platform-ToS operating rules at volume
- How wide the goldilocks seller band really is (empirically, in Phase 3+)
- Platform-dependency pivots only if/when scale makes them real (owned storefront gravity, etc.)
- Seller-trust / non-compete posture (policy, contract, and especially category focus)
- Whether seller-facing niche leads with hard-to-copy / handcrafted goods while the engine still accepts broader fuel
- **Brand carry model:** which first house brands (handcrafted, funny, …), how vetting/grouping works, maker contracts, and how cut/sub applies at brand vs SKU level
- Brand content engine (editorial, vibe, series) vs thin per-SKU promo tricks
- Whether any self-serve orphan-SKU path survives, or is permanently out of core scope
- Dupe / derivative policy across sellers (ranking, clustering, takedowns) — learn from Etsy’s failure mode
- How literally to position against Etsy (“Etsy with marketing”) in public copy vs keep that as internal framing

---

## X. Name

**Twerva** — nonsense brand, spelled as heard: *TWER-vuh*. Domain availability to confirm at a registrar before purchase.
