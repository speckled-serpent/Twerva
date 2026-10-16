# Twerva — Phase map

*Last updated: 2026-10-16*  
*Status: What's left to implement. Strategy: `docs/prompts/project.md`. Product design: `docs/prompts/product.md`.*

This is the general list. It replaces the task sheet. Campaign rules is the next design topic. The phases after it are the remaining build, in order. The strategic phases in `docs/prompts/project.md` (Spotmu, then internal brands, then an optional external spin-off) stay as they are.

---

## Done

A theme is the shape of a carousel frame: one background (picture, solid color, or gradient), spacing, and named elements. An element is text or an image, and the name is required. The theme editor covers that frame, autosaves frame and element edits, and previews the frame with lorem ipsum at a word count per text element. It does not ask the operator to mark the theme Draft or Live. A campaign can pick any theme. Adding a text element adds an empty text on every unit of every source bound to that theme. Removing an element removes that text. A text element may omit a Spotmu text source. Unit text is the value stored for that element, under its name.

A source is bound to one theme. Create asks for a name and that theme. There is one kind of source. A unit has a name, at most one image, and one text per named text element. The image field is there only when the theme has a picture background or an image element. A unit can name other units in the same source that it cannot be shown with. Images are a manual upload or a URL import. Opening a unit previews that theme with this unit and does not write an artifact.

The source stores inspiration and rules. Generate drafts the unit's name and text from those. Accept makes that text the live text. Leaving it unreviewed keeps the unit off a run. The call uses OpenAI when a key is set, and stays off otherwise. Images are not generated.

A campaign stores the chosen theme and one source bound to that theme. Run groups the live units into carousels that respect the exclusion rules. It does not call the model and does not draw slides. Create still also asks for platforms and at least one Spotmu interest. A production Spotmu campaign also asks for an account. Run does not read those interests.

The ops console uses a left rail for Content, Run, and Setup.

An earlier loop still renders a shipping carousel from `carousel_template_v1` off one Spotmu interest. The caption is that interest's title, a fixed hashtag set, and the interest URL. The ops console can approve that draft, set a time, mock-publish, and record a metric by hand. The phases below replace that loop.

---

## 1. Campaign rules

**Goal.** Decide what a campaign's rules are before generation turns a run into posts.

**Scope.** Not designed. A run today takes every live unit on the campaign's source and packs them into as many carousels as the exclusion rules allow. There is no slide count, caption, or other instruction on the campaign. The Spotmu interests stored at create are not that design. Run ignores them.

**Open questions.** What a rule contains, where it lives, and how a run applies it. Whether create still requires a Spotmu interest once rules exist.

## 2. Generation

**Goal.** Turn a campaign's assembled carousels into drafts an operator can review, drawn with that campaign's theme and the units' text and image.

**Scope.** `POST /api/v1/generate/carousel` still draws `carousel_template_v1` from one Spotmu interest. Theme preview, including the lorem word counts, does not create an artifact. A campaign run stores which live units sit together. It does not write slides, a caption, or an artifact. This phase replaces that stand-in. Shipping pixels move off `carousel_template_v1`, and the caption stops coming from the interest title. The text is already the reviewed unit text. This phase does not call the model.

**Open questions.** Does each assembled carousel become one draft? Does a draft freeze the unit's image file, or keep a pointer that can change later? When the theme overlaps or a file is missing, theme preview already marks the frame blocked and still writes a PNG. For a shipping draft, is that a blocked row, or no row? Where do the caption, hashtags, and any CTA come from? They are not on the unit.

## 3. Queue & schedule

**Goal.** A person reviews the drafts, approves or rejects them, and sets the posting times.

**Scope.** Queue and Schedule already approve, reject, edit a caption, and create a post job for an artifact from the text template. An account can already carry a per-day cadence cap. This phase runs that gate on the drafts from generation, with times that respect the cap. Approval stays with a person.

**Open questions.** Is the queue one list, or one list per campaign? Who picks the clock time, the operator or a rule inside the cap? Can an approved draft still be edited after it has a time?

## 4. Accounts & publishing

**Goal.** Connect real social accounts and post the approved draft. The first test is Spotmu.

**Scope.** Account rows exist. They do not store a login. Publish today is a mock adapter. An Ayrshare adapter is in the tree and refuses the live call. This phase connects a real account and posts the media and the caption. Instagram and TikTok come first. The pipe can be rented. Paid ads stay out.

**Open questions.** Which Spotmu account is the first connection, and who owns the login? Official API, or a scheduler we already trust? What does the operator see when a post does not go out?

## 5. Measurement

**Goal.** After a post is live, pull views and engagement for that post.

**Scope.** Metric rows, a manual entry route, and a cluster median of the latest view counts exist. A stub can copy mock views onto a mock-published job. This phase reads views and engagement from the platform for each published post and shows them. The median can follow once those per-post numbers are real.

**Open questions.** Which counts are engagement on the first pull: likes, comments, shares, saves? How soon after posting, and how often after that? Is the first place an operator looks the Results page, or the post itself?

---

## Housekeeping

- **S3 image storage.** Unit images, thumbnails, theme previews, and carousel renders sit on disk under `ARTIFACT_STORAGE_DIR`. Move them to S3 behind the same save, open, and delete calls when more than one machine needs the bytes.
- **Word-count warning.** Optional, and not built. A theme text element may warn when the unit text runs long. The lean is a warning while editing, not a stored limit. The lorem word counts on the theme preview are a separate control.
