# Twerva: Theory of the Case

*Author: the founder. Drafted 2026-10-18; revised the same evening. Status: current.*
*Audience: me, future team members, and agents working on Twerva.*
*Relation to existing docs: `docs/prompts/project.md` (Sept 2026) is still the strategic spine. Where this doc and that one disagree, this one reflects newer thinking. The specific changes are listed in "What changed since the September framing." A candid companion reassessment, kept outside the repo, asks whether this is still worth building.*

---

## 1. The problem in one sentence

We are building a system that puts out content that moves product better than what anyone else can put out.

Reach matters only when it turns into sales or signups. **But I'm assuming we cannot measure sales per post.** An organic carousel can't carry a clickable button. People who are convinced search for the brand later, so a sale can't be matched back to the carousel that caused it. That's probably why nobody does per-carousel sales matching for organic content. So we optimize for the best signals we *can* measure, the ones that show real intent, and we treat them as a proxy for moving product.

## 2. The catch-22: three ways to make social content

**Option 1: total human control.** You hand-make every slide or video in Canva or Photoshop, or you film it. This gives you the most creativity and individuality. It is also slow. Realistically a small team makes fewer than one post a day, and most posts die in the competition for attention. You never get enough volume.

**Option 2: full automation.** This is ReelFarm and tools like it. You pick Pinterest or AI images, write a short prompt such as "5 tips to lose fat this summer" or "how to look expensive on a budget," and the tool posts every day. It's simple, and the output is phrased to go viral. The problem is that everyone paying for these tools posts nearly the same content. Supply of slop runs far ahead of the attention available. Platforms suppress it, and eventually every account doing it dies.

The evidence for this is mostly the vendors' own words:

- ReelFarm's tutorial begins: "find a TikTok page you want to automate… see if there is a repeatable format I can pull from it." Its prompt guide says to keep prompts "short and directive."
- When a user said "When I use API the accounts eventually just die down to 300 views," the founder replied that "posting via API is 95% account warming."
- One Product Hunt review says: "0% of our customers got sales with this slop."

These are anecdotes, not a study, but they fit the structural argument: same input, same output.

**Option 3: real user control and automation together.** This is Twerva. The user doesn't write a one-paragraph prompt. They upload real material: Markdown or PDF documents (implementation rules, research and source material, product specs) and image sets (Albums). The system generates from that material at volume. Humans review and iterate. The model helps refine exactly what to push and helps tell a coherent story across the brand. The output is specific and niche enough to have a real chance of resonating with someone.

The data we collect is different too. Competitors learn which carousels or templates worked. We want to learn which **research, subjects, topics and angles** worked, so the next round gets smarter about what to say and not only how to format it.

## 3. Control is the point

**The level of control over the content is the whole point.** It's what still makes Twerva worth building, even without sales tracking.

Control means the brand's own research decides what gets said, its rules decide what can't be said, its images and layouts decide how it looks, and its team decides which story to push next. Automation supplies the volume. Control is what makes that volume worth posting.

## 4. Market logic: easy means oversupply, and the paradox

Every competitor sells ease: one click, "set it and forget it," "runs forever," "no brief to write." **If something is easy, it isn't worth doing**, because everyone else can do it too. Once an easy tool is public, the value of using it trends toward zero. Its users flood the same feeds with the same kind of post.

The target is a middle zone: **hard enough to be undersupplied, easy enough for one team to manage.** The user's input has to change the output in a meaningful way. If it doesn't, nobody can stand out.

This creates a paradox. **What users need isn't what they want to buy, and what they want to buy isn't what they need.** Most buyers want a get-rich-quick, no-effort scheme, and that's what the market sells them. The no-effort product is exactly what produces oversupply, so it can't deliver what they actually want. I want an actual tool I can use to move product, and that means accepting effort.

**Positioning, not a decision:** Twerva is first a tool for Spotmu and our own house brands (customer zero). Any external market is a smaller, serious segment of people willing to do the work. It's not the mass market the one-click tools serve.

## 5. Why competitors don't do this (hypothesis)

My intuition from the start was that I'd have to build this myself. **Hypothesis, not established fact:** competitors avoid letting users upload large research documents for two reasons.

- **(a) It costs them more in tokens.** Long research documents in every generation make each post more expensive. That hurts a business priced at roughly $0.20–$0.50 per slideshow.
- **(b) It makes the product seem intimidating.** "Upload your research corpus and rules" doesn't fit a "no brief to write" pitch.

What we know: the tools that accept large document sets (Jasper, Typeface) are text-first or enterprise, and no organic carousel tool we checked has a persistent document corpus.

## 6. The thesis

Twerva should be both:

- **Fully automated**: no human bottleneck on each post.
- **Fully user-managed**: calibrated to the brand's message, product facts and rules, so the volume stays on-message and specific.

And it should **optimize for resonance and intent signals, measured by subject.** Those are the signals that suggest a viewer cared, not just scrolled past. They're the best available proxy for moving product.

None of these alone is new. Overlap with competitors is fine, and building commodity parts in-house is fine where it avoids stacking subscriptions. **Twerva's originality is the combination: deep user control over content, plus learning by subject and angle rather than by post or template.**

## 7. What we are building, concretely

**Grounding.** Every claim in a post traces back to the brand's Research. Versioned Instructions carry the brand's rules: required claims, banned claims, product facts, tone. A checker enforces them on generated slides. A slide that fails goes to a human, and a slide that passes moves on. This is what makes unattended volume safe.

**Tagging.** At creation, every post is tagged with its research source(s), topic or subject, angle, claims, skeleton, album and account. Results then roll up by subject, not just by post. We should be able to say "posts built on the sourcing research get saved and shared more than posts built on the price-comparison research," not just "post #4471 did well."

**Learning on intent signals.** Per post, we collect saves, shares, comments, profile visits, follows, bio-link clicks (where available), and completion or swipe-through. Raw views are context, not the target. We capture snapshots over time (planned at 1h, 1d, 3d and 7d) and track account health, such as rolling median views and suppression flags. Then we aggregate by research source, subject, angle, claim, skeleton, album and account. Because organic sample sizes are small, every comparison shows its sample size. A post that broke a rule is never used as a model for the next round, however well it did.

Signal availability varies by platform and provider (Upload-Post and Zernio document watch-time, retention and follows; Instagram has no per-slide insights), so we verify each before relying on it.

**The loop.** From those results, the model proposes the next brief: which research to lean on, which angles to push, what story to tell next. A human approves it. Autonomy is earned over time. Once a type of content keeps passing review without edits, it can run with less oversight, and any rule failure or edit puts it back under review. (Postdom does a version of this: autopilot is offered once 9 of your last 10 posts are approved without edits.)

**Volume with variety.** The goal is many distinct stories per product, drawn from different research, angles and subjects, not one prompt cloned a thousand times. That keeps us out of the slop flood. It also carries forward the September doc's constraint: high cadence needs a content world, not one object on repeat.

**Possible later option, not core:** a coupon code on the last slide (on some posts) could sometimes show which campaigns drove purchases. It would be coarse and partial, and it is not part of the current plan.

## 8. How this differs from what's on the market

We checked 20 tools on 2026-10-18 (`twerva_option3_check.md`). **None does Option 3 as one product, organic or paid.** Several have real pieces of it:

| Tool | What it has | What it lacks, relative to Twerva |
|---|---|---|
| **Typeface (Arc Graph + Arc Loop)** | Closest overall. Brand docs become enforced, linted rules; learns per message on a chosen metric; writes learnings into the next brief; humans decide. | Enterprise and demo-only; email and ads; no organic TikTok/IG carousels; no learning by research source. |
| **Genviral** | Closest organic. Brand briefs, content labels with a performance track record, Weekly Briefs from engagement. | No user document upload; no research-grounded rules. Whether its labels are user topics is unknown. |
| **Fastlane** | Angle-level loop; **claims** post-level revenue attribution. | Does its own research and picks its own angles; no user docs or rules documented; attribution method undocumented. |
| **Carouscale** | TikTok Shop photos, generic claim cleaning, a library of winning structures. | Learns from market views, not your material. |
| **Motion** | Angle- and theme-level reporting. | Paid Meta ads only; no creation. |
| **Jasper** | The strongest document grounding (PDF/MD, tags, Product IQ). | No performance loop; text-first. |
| **Postdom** | Earned autopilot from approvals. | No documents; no topic-level reporting. |
| **Omneky, Adlore, AdCreative** | Optimize on ROAS and conversions. | Paid ads only. |

**To be honest:** Fastlane and the ad tools claim revenue attribution, and we don't. Twerva's differentiation is not "optimizes for sales." It's two things together:

1. **The depth of user control:** a persistent corpus of research and documents, enforced rules, locked layouts and approved images.
2. **Learning by subject, angle and research source** rather than by post or template.

Nobody we found reports results by research source or claim.

## 9. Creation vs. posting: what we build, what we rent

TikTok controls posting, not creation. **Decision: Twerva focuses on content creation and learning, and posting goes to a third-party provider.**

```
Twerva (create, tag, review, learn) → posting provider → TikTok / Instagram / Pinterest / …
```

- **Upload-Post** is the leading choice. It prices per profile: $24 for 5, $50 for 25, $147 for 75, $438 for 225, with unlimited posts. It supports TikTok, Instagram and Pinterest carousels and runs its own approved TikTok app. Its analytics are among the richest we found.
- **Ayrshare** is the safer, more mature alternative, at roughly 10× the price in our 20-brand cost example.
- X is the least important platform.

This avoids building posting and, for now, TikTok's Content Posting API audit (public product required, no "accounts you or your team manages" tools, per-post consent UX, about 15 posts per account per day). **Twerva still needs a light review and approve step, with batch approval**, because providers pass TikTok's consent fields straight through, so our UI has to satisfy TikTok's guidelines. We also have to watch Upload-Post's silent `fallback_to_inbox` drafts.

## 10. What exists today

- **Skeletons**: locked 9:16 layouts with picture or gradient backgrounds and named text elements.
- **Albums**: reusable image sets.
- **Research**: text documents.
- **Carousels**, built in stages:
  - **Basic**: label, skeleton, generation 1.
  - **Instructions** (phase 5): versioned Markdown docs in the database, run through a swappable LLM provider such as OpenAI.
  - **Content**: attach an album and an ordered list of research.
  - **Slides**: manual for now, AI later.
  - **Final** (phase 7): assembly for review.

Phases 1–4 are complete but not deployed. Planned phases 8–12 cover variant generations, a campaign timeline, accounts, measurement, and the next generation built from results. The parts that make this Option 3 (the rule checker, tagging and subject-level learning) aren't built yet.

## 11. Who it's for

- **Spotmu and our house brands first.** Spotmu is a media product with a steady supply of fresh material, so it's a natural fit for high cadence.
- **Later, possibly:** brands with real products and real material, willing to put in real input. This narrows the September "Kevin with one SKU" story: a lone product can't supply enough varied content.

## 12. What we are not building

A posting system; phone farms or warmed accounts; a paragraph-prompt slop generator; a paid-ads bidder (never); a per-post sales-attribution system (for now).

## 13. Risks and open questions

- **The proxy may be wrong.** Saves, shares and profile visits may not track purchases. We can't confirm the link without sales data. This is the biggest unknown in the thesis.
- **Small numbers.** Organic per-subject samples are noisy, so we can over-read luck. We show sample sizes and avoid strong conclusions from thin data.
- **Signal availability.** Some signals (profile visits, bio-link clicks, completion) depend on the platform, provider and lane. We have to verify them in a pilot.
- **Brands may just buy paid carousels,** where ad tools optimize on real conversion data.
- **One team has to manage it.** "Undersupplied" becomes "too hard to use" if research upkeep and review take hours a day.
- **Token cost.** If my hypothesis in section 5 is right, it applies to us too: large research inputs make each generation more expensive. We'll need to retrieve only the relevant chunks rather than send whole documents. That is an assumption to test.
- **TikTok enforcement on providers.** Audits can be revoked (SocialBee apparently lost public posting), so we keep the posting layer swappable.
- **Cold start.** No winner library. We could seed with public winning *structures*, for hooks and formats only, filtered through the brand's rules.
- **Copying.** Genviral could add document upload, and Typeface could move into organic. Our defense is execution and the corpus a brand builds up inside Twerva, which is unproven.
- **Still open from September:** the money model, account ownership, and the brand-carry model.

## 14. What changed since the September framing

| September `project.md` | Now |
|---|---|
| A "bootstrap distribution control plane" and middle node operating real pipelines | A **creation-and-learning system**. Posting is rented. |
| "Durable average views × volume"; measure sales and cut once selling | Volume still matters. **Sales can't be tracked per post (assumption).** The loop runs on **intent signals by subject.** |
| Twerva publishes through its own pipeline | **Outsourced: Upload-Post leading, Ayrshare as the fallback.** |
| "Human gate early" | Kept, and extended: rule checker plus batch approval, then **earned autonomy**. |
| Kevin and self-serve sellers as the upside story | **Customer zero first** (Spotmu and house brands). External buyers would be a smaller, serious segment (positioning, not a decision). |
| "Sell brands, not orphan products"; content-variety constraint | **Still holds.** Option 3 is the mechanism for variety. |
| Never an ads bidder; money model open | **Unchanged.** |

The October market review's advice to "only build what's unique" is not adopted. Overlap with competitors is fine as long as every part serves the combination.

## 15. What this implies for the roadmap (proposals, not yet approved)

1. **Build the rule checker with phase 5**, so Instructions carry executable rules (required and banned claims, product facts, each claim traced to Research), not only prose.
2. **Add tagging at creation now.** Record research sources, subject, angle, claims, skeleton, album and account on every carousel, before measurement exists. Untagged data can't be recovered later.
3. **Focus the measurement phase on intent signals by subject.** Snapshots of saves, shares, comments, profile visits, follows, bio-link clicks and completion, rolled up by tag, with sample sizes shown. Not a per-post views dashboard.
4. **Rescope the "accounts" phase** as provider integration (Upload-Post) plus a batch approval screen that satisfies TikTok's consent fields.
5. **Run a small provider pilot early** (2–3 real accounts) to confirm that carousels go public and to see which intent signals actually come back, and how quickly.

These are proposals. I haven't approved a reordering.
