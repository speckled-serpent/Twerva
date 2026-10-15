# Twerva — Phase map

*Last updated: 2026-10-15*  
*Status: What's left to implement. Strategy: `docs/prompts/project.md`. Product design: `docs/prompts/product.md`.*

This is the general list. It replaces the task sheet. The six phases below are the remaining build, in order. The strategic phases in `docs/prompts/project.md` (Spotmu, then internal brands, then an optional external spin-off) stay as they are.

---

## Done

Campaigns can be created and listed. The themes editor covers the frame, elements, and live preview. Sources cover albums, units, resources, and images, including upload and URL import onto a new unit. Theme picture and image controls pick a concrete album image.

An earlier loop still renders a shipping carousel from the text template, and the ops console can approve a draft, set a time, mock-publish, and record a metric by hand. The phases below are the real versions of that loop.

---

## 1. Combining rules

**Goal.** A campaign says which sources and which themes it pulls from, and how those pieces mix into one post.

**Scope.** Two mixes are already described. An album can be used as units, so each unit's text stays with its images. Or a resource holds the writing and an image-only album supplies pictures, chosen by tags. The campaign also names the theme or themes. Create and list already exist; they do not store this mix yet. See `docs/planning/sources_v2.md`.

**Open questions.** Does one campaign use one theme, a list, or a rotation? Is the mix a rule the operator picks, or a choice the model makes per draft? Can one campaign name several albums and several resources, or one of each?

## 2. Model / instruction sets

**Goal.** An instruction set tells a model how to write the caption and the text on the frame from the sources a campaign named.

**Scope.** The set is the voice and the limits: what to pull from a unit or a resource, what to leave out, how long, and whether a CTA is required. It produces words. It does not render slides. The caption on today's text-template carousel is a stand-in, filled from a Spotmu interest title.

**Open questions.** Is a set global, per campaign, or per theme? Which model runs it, inside Twerva or through a rented API? Does the set emit only the caption and the overlay lines, or also hashtags and the CTA?

## 3. Generation

**Goal.** A campaign produces real carousel drafts: combining rule, instruction set, and theme, rendered into slides an operator can review.

**Scope.** `POST /api/v1/generate/carousel` still draws the text template from one Spotmu interest. Theme samples stay previews and do not create an artifact. This phase writes a draft artifact — slides on disk, caption, and the theme's image paths — from a campaign. Shipping pixels move off `carousel_template_v1` here.

**Open questions.** One draft per run, or a batch? Does a draft freeze the chosen image files, or keep a pointer that can change later? Where does a layout that overlaps or misses a file go — a blocked draft, or no row?

## 4. Queue & schedule

**Goal.** A person reviews the drafts, approves or rejects them, and sets the posting times.

**Scope.** Queue and Schedule already approve, reject, edit a caption, and create a post job for the older artifact. This phase runs that gate on the campaign drafts from phase 3, with times that respect a cadence cap. Approval stays with a person.

**Open questions.** Is the queue one list, or one list per campaign? Who picks the clock time, the operator or a rule inside the cap? Can an approved draft still be edited after it has a time?

## 5. Accounts & publishing

**Goal.** Connect real social accounts and post the approved draft. The first test is Spotmu.

**Scope.** Account rows exist. Publish today is a mock adapter. This phase connects a real account and posts the media and the caption. Instagram and TikTok come first. The pipe can be rented. Paid ads stay out.

**Open questions.** Which Spotmu account is the first connection, and who owns the login? Official API, or a scheduler we already trust? What does the operator see when a post does not go out?

## 6. Measurement

**Goal.** After a post is live, pull views and engagement for that post.

**Scope.** Metric rows and a manual entry route exist. This phase reads views and engagement from the platform for each published post and shows them. A cluster median can follow once the per-post numbers are real.

**Open questions.** Which counts are engagement on the first pull: likes, comments, shares, saves? How soon after posting, and how often after that? Is the first place an operator looks the Results page, or the post itself?

---

## Housekeeping

- **S3 image storage.** Album images, thumbnails, and resource files sit on disk under `ARTIFACT_STORAGE_DIR`. Move them to S3 behind the same save, open, and delete calls when more than one machine needs the bytes. Theme samples and carousel renders that use the same directory can follow.
