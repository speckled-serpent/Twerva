# Twerva — Phase map

*Last updated: 2026-11-13*  
*Status: What's left to implement, after the redesign agreed with Mu. Strategy: `docs/prompts/project.md`. Product design: `docs/prompts/product.md`.*

This list replaces the previous one. A Skeleton is the structure of a carousel: the background and the named elements. A Carousel is what an operator builds, in steps. A Slide is one frame of content inside it. Albums and Research are shared libraries. A generation is a snapshot of one carousel. The campaign is the timeline of posts.

The strategic phases in `docs/prompts/project.md` (Spotmu, then internal brands, then an optional external spin-off) stay as they are.

Build in the order below. The rename is a real change to the tables and the routes, so later phases can use the new names. Albums come before the Content step, because today's images sit on the slide and that step needs an album to attach. Research has nothing to import, so it stays a small phase after Albums. The step screen comes once both libraries exist. Instructions come before the model fills slides, because the call should read those documents. Hand entry of slides already works, so Final is not waiting on the model for a carousel someone typed. It still follows Instructions, so the first assembly uses the written rules. Generations come after Final so the snapshot includes the slides that will be posted, including ones the model wrote. The campaign timeline is where those assembled carousels become posts. Accounts, measurement, and the next generation follow the first posts.

---

## Done

A skeleton is the shape of a carousel frame: one background (picture, solid color, or gradient), spacing, and named elements. An element is text or an image, and the name is required. The skeleton editor covers that frame, autosaves frame and element edits, and previews the frame with lorem ipsum at a word count per text element. It does not ask the operator to mark the skeleton Draft or Live. The status column is still on the row. A campaign can pick any skeleton. Adding a text element adds an empty text on every slide of every carousel bound to that skeleton. Removing an element removes that text. A text element may omit a Spotmu text source. Slide text is the value stored for that element, under its name. A picture background or an image element stores a concrete image path.

A carousel is bound to one skeleton. Create asks for a name and that skeleton. There is one kind of carousel. Album and resource are gone, and the `resource_files` table is gone. A slide has a name, at most one image, and one text per named text element. The image field is there only when the skeleton has a picture background or an image element. A slide can name other slides in the same carousel that it cannot be shown with. Images are a manual upload or a URL import, with a license and a source note, stored on disk. The path prefix is `albums/…`, or `theme-defaults/…` for the packaged photos. The file row lives on an album. A slide that has an image points at that album image. Opening a slide previews that skeleton with this slide and does not write an artifact.

The Default carousel (slug `default`) is bound to Spotmu Paper v1, so the required skeleton has a row to point at. Its six packaged photos are the Default album (slug `default`). Paths stay `theme-defaults/…`. A carousel that had slide images points at an album named after that carousel. A carousel with no images has no album. Skeleton picture paths stay concrete files.

The carousel stores inspiration and rules as two text fields. Generate drafts the slide's name and text from those. Accept makes that text the live text. Leaving it unreviewed keeps the slide off a run. The call uses OpenAI when `OPENAI_API_KEY` is set (`TEXT_GENERATION_PROVIDER` is `openai` or `fake`; the model defaults to `gpt-4o-mini`) and stays off otherwise. Images are not generated.

A campaign stores the chosen skeleton and one carousel bound to that skeleton. Older rows can have both empty. Run groups the live slides into `campaign_carousels` that respect the exclusion rules. It does not call the model and does not draw frames. Those rows are a run's assembly, not the carousel. Create still asks for platforms and at least one Spotmu interest. A production Spotmu campaign also asks for an account. A Spotmu test campaign does not. Run does not read the interests.

The ops console is signed in. An admin can change rows. A reader can look. The left rail is Content (Campaigns, Skeletons, Carousels), Library (Albums, Research), Run (Queue, Schedule, Results), and Setup (Accounts, Users). An album is a named set of images. The list has Create Album. The detail adds, removes, and reorders images, edits license, source, alt, and license note, and autosaves. Delete asks first. A research item is one document: a title, a slug, and a body of Markdown or plain text, up to one million characters. The list has Create Research. The detail edits the title and the body and autosaves. There is no upload and no carousel link.

An earlier loop still renders a shipping carousel from `carousel_template_v1` off one Spotmu interest. The caption is that interest's title, a fixed hashtag set, and the interest URL. The ops console can approve that draft, set a time, mock-publish, and record a metric by hand. An account can carry a per-day cadence cap. It does not store a login. Publish is a mock adapter. An Ayrshare adapter is in the tree and refuses the live call. Metric rows, a manual entry route, and a cluster median of the latest view counts exist. A stub can copy mock views onto a mock-published job. Clusters, brands, ingest, and steer from that loop are still in the API. The phases below replace that loop for the new model.

---

## 1. Rename to Skeletons, Carousels, and Slides

**Status.** Done. Revision `skeletons_carousels_slides`.

**Goal.** Use the new names in the database, the API, and the rail, without changing what the rows do.

**Scope.** Themes become Skeletons. Sources become Carousels. Units become Slides. A slide keeps today's shape: a name, an optional image, one text per named text element, the exclusion list, and the draft or live text. Create is still a label plus a skeleton. Preview, exclusions, and generate-from-inspiration keep working under the new names. `campaign_carousels` stays the run assembly. It is not renamed into the new Carousel.

**Migration.** Rename the tables, the routes, and the labels in one revision. A screen-only rename would leave `/api/v1/sources` and `units` under new labels, and the next phases would keep writing the old names.

`themes` and `theme_elements` become `skeletons` and `skeleton_elements`. `sources` becomes `carousels`. `units` becomes `slides`, and the text and exclusion tables move with them. Campaign `theme_id` and `source_id` become `skeleton_id` and `carousel_id`, and they stay optional on older rows. Each existing source becomes one carousel on the skeleton it already uses. The Default source stays a carousel until Albums. Inspiration, rules, and slide images stay put. There is no generation table yet.

**Open questions.** The theme row still has Draft and Live, and the editor does not ask. Does a Skeleton keep that status?

## 2. Albums

**Status.** Done. Revision `albums_from_slides`.

**Goal.** A reusable collection of images, on the rail, that more than one carousel can use.

**Scope.** An album is a named set of images. Keep today's upload, URL import, license fields, and thumbnails. Skeleton picture paths stay concrete files. This phase does not build the Content step. It does store which album a carousel's images came from, so the files are not left on the slide with nowhere to live.

**Migration.** Add albums and album images. For each carousel that has slide images, create one album named after the carousel and move the image rows onto it. The carousel points at that album. A slide that had an image keeps a pointer to that album image. Do not copy the bytes. The Default carousel's six packaged photos become an album named Default. Their paths stay `theme-defaults/…`. Other files stay at the paths they already have. A carousel with no images gets no album. Skeleton backgrounds that store a path are left alone.

**Open questions.** Settled for this phase:

- The album screen shows and edits the license, source, alt, and license note already stored on each image. Upload already requires them. Edits autosave. There is no separate Save button.
- Two slides that each held their own copy stay two album images. The rows are not merged. Each slide image keeps its id and its path.

## 3. Research

**Status.** Done. Revision `research_items`.

**Goal.** A reusable text document a carousel can draw on later.

**Scope.** Minimal. A name and a body of text. Its own rail section. An operator can write and edit it. No upload rules beyond plain text, no synthesis, and no link to a carousel until the Content step.

**Migration.** Add `research_items`: a title, a slug, a body, and timestamps. Do not recreate `resource_files`. The unused helpers `app/carousels/resource_files.py`, `resource_store.py`, and `resource_markdown.py` are removed. Downgrade drops the new table and the rows in it. Albums and carousels stay.

**Open questions.** Settled for this phase:

- One row is one document. A research item does not hold several documents.
- The body is at most 1,000,000 characters. An empty body is allowed. There is no file upload.

## 4. Carousel steps and the Content step

**Status.** Checklist. Head revision on main is `research_items` (PR #76 merged). Implement in the order below. Each box is one PR, and the console still works after that PR.

**Goal.** A carousel is built in stages. Step 0 is the label and the skeleton, and the new row is generation 1. Step 2 attaches an album, research, or both. Step 3 is the slide editor that already exists. Steps 1 and 4 are on the stepper and stay closed.

**What the code does today.** Create (`NewCarouselPage`) asks for a name and a skeleton, then `CarouselsPage` opens one screen: rename, inspiration, rules, Generate slide, and the slide grid. The slide editor (`SlideEditorView`) asks for a name, one text per skeleton text element, exclusions, and — when the skeleton needs a picture — a file upload or a URL import. That upload calls `ensure_carousel_album` in `app/albums/linking.py`, which creates an album named after the carousel the first time a slide gains an image. `carousels.album_id` is already the pointer (nullable, `ON DELETE SET NULL`). It is set by the albums migration and by that helper. The read API returns it. Nothing in the API lets an operator pick an album. `research_items` has a title, a slug, and a body. A carousel has no research link. `test_carousel_has_no_research_link_and_upload_helpers_are_gone` asserts there is no `carousels.research_id` column. There is no generation column and no step column. Inspiration and rules are two text columns, saved from an explicit Save inspiration button. Albums, Research, and skeleton frame edits already autosave through `useSkeletonAutosave` at `SKELETON_AUTOSAVE_DELAY_MS` (700). The ops palette is the Warm Stone and Teal variables in `apps/ops/src/index.css`: `--ops-bg`, `--ops-surface`, `--ops-border`, `--ops-text`, `--ops-text-muted`, `--ops-primary` (`#0d9488`), `--ops-primary-hover`, `--ops-primary-soft`, `--ops-stone-soft`, `--ops-success`. A picture is required when `skeleton_requires_image` is true: `background_kind` picture, or any element with `content_kind` image. The same rule is `skeletonRequiresImage` in `slideSkeletonShape.ts`. The Default carousel (slug `default`) is bound to Spotmu Paper v1 and to the Default album (slug `default`, id from `default_library_album_id()`). Its six slides point at that album's packaged photos.

**Decisions.** Settled with Mu. The tasks below use them.

- `carousels.album_id` stays the attach. One album. The operator sets it on Content. Slide upload stops creating an album.
- A carousel attaches an ordered list of research items through `carousel_research_items`. There is no single research item and no `carousels.research_id` column.
- `generation_number` is an integer on the carousel. Create stores 1. The shell shows "Generation 1" now. Phase 8 still adds the snapshot table and the duplicate action. This phase only stores the number.
- `editor_step` remembers the last open step: 0 Basic, 2 Content, 3 Slides. Instructions and Final are never stored.
- Instructions and Final are visible and disabled. They do not block Content or Slides.
- The album rule is the picture rule above. An attached album with zero images satisfies it. A slide that needs a picture still needs an image chosen from that album before it saves. When the skeleton needs no picture, Slides is available immediately, with or without an album, and without opening Content first.
- Replacing or clearing the album returns 409 while any slide still points at one of that album's images, including the Default album. The screen shows a clear reason, and the album stays attached.
- The skeleton is locked at create and can never be changed, including before the first slide. A different skeleton means delete the carousel and create a new one.
- This phase hides the inspiration and rules form. The columns and their stored text stay. Generate text still reads them. Phase 5 replaces the form with Instructions.
- Slides is done when the carousel has at least two slides, because a carousel requires at least two. Fewer than two, with the album rule passing, leaves the step available.
- Built-in defaults live in global settings. Per-skeleton overrides may come later. The slide-count default is a random value from 5 to 8. That count is the later assembly default. The done mark on Slides is two, and the two numbers are separate. This phase does not add a settings screen.

### Data model

- [x] **4.1 Add generation number, editor step, and the research link**

  Alembic revision `carousel_steps`, down-revision `research_items`. On `carousels`: `generation_number` integer, not null, server default 1, check `generation_number >= 1`; `editor_step` integer, not null, server default 3, check `editor_step IN (0, 2, 3)`. New table `carousel_research_items`: id, `carousel_id` (cascade on carousel delete), `research_item_id` (cascade on research delete), `position` (check `position >= 0`). Unique `(carousel_id, research_item_id)` and unique `(carousel_id, position)`. Upgrade sets `generation_number` 1 and `editor_step` 3 on every carousel, including Default. It leaves `album_id`, inspiration, rules, slides, and `album_image_id` as they are, and it inserts no research links. Downgrade drops the join table and the two columns. Albums, slides, and `research_items` stay.

  Acceptance: upgrade, downgrade, upgrade again keeps Default on the Default album with its six slide pointers, keeps a carousel that has an album, and keeps a carousel with a null `album_id`. Every row reads generation 1 and editor step 3. The join table is empty. `Carousel` still has no `research_id` column.

### API

- [x] **4.2 Return generation, the open step, research, and derived step state**

  `CarouselReadResponse` and `CarouselListItemResponse` gain `generation_number` and `editor_step`. The detail also gains `research`: `{id, title, slug, position}` in position order, one entry per attached item. One helper, next to `skeleton_requires_image`, returns the five step states. `basic` is `done`. `instructions` is `locked`. `content` is `done` when the album rule passes and `available` otherwise. `slides` is `locked` when the album rule fails, `available` when the rule passes and the carousel has fewer than two slides, and `done` when the rule passes and the carousel has at least two slides. `final` is `locked`. The album rule passes when the skeleton needs no picture, or when `album_id` is set. A skeleton that needs no picture passes the rule immediately. Put that object on the detail as `steps`. Readers can call the existing GET routes.

  Acceptance: a picture skeleton with a null album reads `content: available` and `slides: locked`. A color skeleton with a null album and no slides reads `content: done` and `slides: available`. The same color skeleton reads `slides: done` once it has two slides. Default, with six slides, reads `slides: done`, generation 1, editor step 3, its current `album_id`, and an empty research list.

- [x] **4.3 Accept a step change**

  `PATCH /api/v1/carousels/{carousel_id}/step` with `{editor_step}` stores 0, 2, or 3. Admin only, same as the other carousel writes. A value of 1 or 4 is 400. Step 3 is 400 while `steps.slides` is `locked`. The stored step is left unchanged on 400. Create still uses the column default, so a carousel created in this PR opens at step 3. Task 4.7 is what points create at step 0. `PATCH /api/v1/carousels/{carousel_id}` stays the rename.

  Acceptance: an admin can store step 0 or 2 on any carousel, and step 3 only when the album rule passes. A reader is rejected. A picture carousel with no album stays on its previous step when step 3 is refused.

- [x] **4.4 Attach and detach the one album**

  Keep `carousels.album_id`. `PUT /api/v1/carousels/{carousel_id}/album` with `{album_id}` points at an existing album. `POST /api/v1/carousels/{carousel_id}/album` with `{name}` creates an album (same name and slug rules as `POST /api/v1/albums`) and points at it. `DELETE /api/v1/carousels/{carousel_id}/album` clears `album_id` and leaves the album row and its files. Admin only. Unknown album is 404. A blank name is 400. Replace and clear return 409 while any slide's `album_image_id` still points at an image in the album being left, including the Default album. The 409 detail says slides still point at that album's images and to clear those slide images first. The stored `album_id` stays. Two carousels may point at one album. This PR leaves `ensure_carousel_album` on the slide upload path.

  Acceptance: a second carousel can attach the Default album and the files stay one set. Clearing Default, and replacing it with another album, each return 409 with that reason, and Default stays the album. A carousel with no slide images can clear its album and attach another.

- [x] **4.5 Attach, reorder, and remove research**

  `POST /api/v1/carousels/{carousel_id}/research` with `{research_item_id}` appends at the next position. `PUT /api/v1/carousels/{carousel_id}/research` with `{research_item_ids}` replaces the order. `DELETE /api/v1/carousels/{carousel_id}/research/{research_item_id}` drops that link. Admin only. Unknown research is 404. The same id twice in one list is 400. Deleting a research item drops its links and leaves the carousel. Update `test_carousel_has_no_research_link_and_upload_helpers_are_gone` so it still rejects a `research_id` column and asserts the join table.

  Acceptance: two research items round-trip in the stored order. A duplicate id is 400. Deleting one research item removes that link and leaves the carousel and the other link. `carousels` has no `research_id` column.

### Step shell

- [x] **4.6 Put a stepper around the current slide editor**

  The open carousel in `CarouselsPage` shows five steps, labeled with their index: 0 Basic, 1 Instructions, 2 Content, 3 Slides, 4 Final. This PR enables Slides only. The other four controls are visible and disabled. Slides renders the current slide list and slide editor, including upload and Save slide, and hides the inspiration and rules fields and Save inspiration. Generate slide stays on the slide list and still reads the stored columns. Opening a carousel loads `editor_step`; a stored 3 shows Slides. The shell and the list show "Generation 1" from `generation_number`, and the lede says the carousel opens on that step. Use the Warm Stone and Teal variables already on `:root`. The current step is `--ops-primary`. A disabled step uses the existing disabled control. A done step uses `--ops-success`. Default's Slides step is done because it has six slides. A reader sees `ReadOnlyNotice` and the same disabled controls.

  Acceptance: Default opens on Slides, the step shows done, and its six slides still add, edit, preview, and delete. The inspiration and rules fields are absent, and GET still returns their stored text. Basic, Instructions, Content, and Final cannot be selected. The list shows Generation 1 for every current carousel.

### Basic

- [x] **4.7 Add the Basic step, and start a new carousel there**

  Enable step 0. `POST /api/v1/carousels` sets `generation_number` 1 and `editor_step` 0, then the create form opens the shell on Basic. Basic shows "Generation 1", the skeleton name, and the label. The skeleton is locked: the name is text, and there is no control to change it, including when the carousel has no slides. Another skeleton means delete the carousel and create a new one. The label autosaves at 700ms through `useSkeletonAutosave` and `SkeletonAutosaveStatus`, writing the existing rename PATCH, which accepts a name only. A blank name does not save and shows the required-name error. Leaving the step flushes with `leaveAfterAutosave`. Create still requires a trimmed name and a skeleton (`createCarouselFieldError`) and still refuses a reader. The empty list stays "No carousels yet."

  Acceptance: a blank name or a missing skeleton does not create a row. A created carousel reloads on Basic with Generation 1, the chosen skeleton, and editor step 0. With zero slides there is still no skeleton control, and a rename body that includes `skeleton_id` is rejected. A renamed label is still there after a reload. The skeleton id is the one from create.

### Instructions

- [x] **4.8 Add the Instructions step as a closed control**

  Step 1 stays disabled for an admin and a reader. Its accessible name says versioned Markdown instructions are a later phase, and that phase 5 replaces the hidden inspiration and rules form. There is no panel, no document table, and no provider call. The inspiration and rules columns stay as stored.

  Acceptance: the control does not navigate and does not write. A carousel's inspiration and rules read back the same text.

### Content

- [x] **4.9 Add the Content step for choosing an album**

  Enable step 2. The operator attaches an existing album or creates one by name, using the task 4.4 routes. The attached album shows its name and image count, and actions to replace it or clear it. A 409 shows the API's reason in the form: slides still point at that album's images, so clear those slide images first. Copy for the empty and required states: a picture skeleton with no album says the skeleton needs an album and to choose or create one; a skeleton that needs no picture, with no album, says no album is attached and slides for this skeleton do not use a picture; an attached album with zero images says this album has no images yet. Changing step flushes any pending Basic save and PATCHes `editor_step`. A reader can look and cannot attach.

  Acceptance: creating an album here lists it on Albums. Attaching an album sets `album_id` and survives reload. A picture skeleton with no album stays on Content. Clearing Default, and replacing it, each show that reason and leave the Default album attached.

- [x] **4.9a Edit that album's images on Content**

  Once an album is attached, Content reuses the album detail's add, URL import, reorder, and license, source, alt, and license-note fields, including the 700ms autosave those fields already use. New bytes go through `/api/v1/albums/{album_id}/...`. The slide editor still has its own upload until task 4.12a.

  Acceptance: an upload on Content appears on the album and on the Albums page. License edits reach Saved without a Save button. A second carousel attached to the same album sees the new image.

- [x] **4.10 Add optional research on Content**

  Under the album, Content shows the attached research in order. The operator adds an existing item, creates one with a title (empty body is allowed, through `POST /api/v1/research`, then attach), removes a link, or reorders. The body stays on the Research page. None attached says research is optional and none is attached. An empty library says no research yet and offers create. A reader can look and cannot change the list.

  Acceptance: two documents stay in the chosen order after reload. Removing a link leaves the research item on the Research page. A picture skeleton can open Slides, once 4.11 lands, with research still empty.

### Slides

- [x] **4.11 Gate Slides on the album rule**

  The Slides control follows `steps.slides`. Locked, it stays disabled and its name says to attach an album on Content first. Available, it opens and stays unmarked until the carousel has two slides. Done, it uses the done style. A small revision `carousel_editor_step_content` (down-revision `carousel_steps`) sets `editor_step` 2 where the album rule fails, and leaves every other carousel, including Default, on 3. Create of a picture skeleton still lands on Basic (step 0) with Slides disabled until an album is attached. A skeleton that needs no picture has Slides available immediately, with a null album, before Content is opened.

  Acceptance: PATCH step 3 on a picture carousel with no album is 400 and the shell keeps Slides disabled. After attach, Slides enables, and it shows done once the carousel has two slides. Default still opens on Slides and shows done. A color or gradient skeleton with no image element opens Slides with no album while it has fewer than two slides.

- [x] **4.12 Let a slide store an image from the attached album**

  `SlideWriteRequest` and the slide PATCH gain optional `album_image_id`. Null clears the pointer. A set id must be an image on `carousels.album_id`; otherwise 400. A skeleton that needs no picture rejects a set id with the existing image-not-used detail. A skeleton that needs a picture still rejects a save with no image. The existing upload and import routes stay for this PR.

  Acceptance: a slide can point at an image already in the attached album without a new file. An id from another album is 400 and the previous pointer stays. Default's slides still return their six photos.

- [x] **4.12a Pick that image in the slide editor**

  On Slides, replace `ImageIntakeForm` and the new-slide file drafts with a picker of the attached album's images. Choosing one saves `album_image_id`. The preview and the slide card show that image. Name, text elements, exclusions, the draft banner, Generate text, and Accept stay as they are, including the explicit Save slide button. Add slide requires a chosen image when the skeleton needs a picture. An attached album with no images says this album has no images yet and points the operator at Content. The empty slide list stays "No slides yet."

  Acceptance: a new slide on a picture carousel uses an existing album image and writes no new file. Generate text and Accept still run. The upload form is gone from the slide.

- [x] **4.13 Autosave the slide's name, text, and exclusions**

  Those three autosave at 700ms through the shared helper. A blank name does not save and shows the required-name error. The image pick saves on selection. Generate, Accept, and Delete stay explicit buttons. Leaving the slide or the step flushes.

  Acceptance: a text edit is stored after the 700ms delay with no Save slide button. A blank name leaves the previous name in place. Accept still marks the slide live.

### Final

- [x] **4.14 Add the Final step as a closed control**

  Step 4 stays disabled for an admin and a reader. Its accessible name says final assembly is a later phase. It does not call `POST /api/v1/generate/carousel` and it does not write campaign-run rows.

  Acceptance: the control does not navigate. A campaign run and the template generate route behave as they do now.

### Stage guidance

- [x] **4.15 Show the slide-count fallback on Slides**

  Slides shows one hint: the global slide-count default is a random value from 5 to 8, used when a later phase needs a count and this carousel has no guidance. That default lives in global settings. Per-skeleton overrides are later, so the skeleton gains no column for it. The hint does not add or remove slides, and it does not change the done mark, which is two slides. This phase does not add a settings screen.

  Acceptance: the hint is on Slides only and names the global default as a random count from 5 to 8. The skeleton has no slide-count column. Saving a fourth slide and a ninth slide both succeed, and the step is already done at two slides.

### Cleanup

- [x] **4.16 Remove the old carousel editor paths**

  Delete the inspiration and rules form that task 4.6 already hides, and delete the slide file upload and URL import (`ImageIntakeForm`, the new-slide file drafts, `uploadSlideImages`, `importSlideImage`). Point the slide card and preview at the album file URL the Albums page already uses, then remove the carousel slide upload, import, and metadata-write routes that only that form called. Remove `ensure_carousel_album` so storing a slide image cannot create an album. Keep the inspiration and rules columns and their stored text for phase 5, which replaces the form with Instructions. Keep `PATCH /api/v1/carousels/{carousel_id}/guidance`, Generate slide, and Generate text. Keep the album routes, the Research page, and the Default album seed.

  Acceptance: the carousel screen has no inspiration form and no slide file picker. The inspiration and rules columns still hold their text. A new image is added on Content and chosen on the slide. Guidance PATCH and Generate text still respond. Default opens on Slides with its six packaged photos and shows done.

### Open questions

None. Settled with Mu:

1. A carousel attaches an ordered list of research items through `carousel_research_items`.
2. The shell shows "Generation 1" now.
3. Built-in defaults live in global settings. Per-skeleton overrides may come later. The slide-count default is a random value from 5 to 8.
4. This phase hides the inspiration and rules form and keeps the columns and their data. Phase 5 replaces that form with Instructions.
5. The skeleton is locked at create and can never be changed. A different skeleton means delete the carousel and create a new one.
6. Slides is done when the carousel has at least two slides, because a carousel requires at least two.
7. Replacing or clearing an album returns 409 while any slide still points at one of its images, including the Default album, and the screen shows the reason.
8. When the skeleton needs no picture, Slides is available immediately.

## 5. Instructions

**Status.** Checklist. Head revision on main is `carousel_editor_step_content`. Implement in the order below. Each box is one PR, and the console still works after that PR. Each box names the tests that land with it. Task 5.11 runs the full suites.

**Goal.** Step 1 is the carousel's instructions, written in Markdown, that the model follows when it fills slides. One or more documents live on the carousel. The editor shows a preview. Only the current text is stored.

**What the code does today.** Instructions is a closed step. `carousel_step_states` in `app/carousels/slide_skeleton.py` sets `instructions` to `locked`. `STORED_EDITOR_STEPS` is 0, 2, and 3. `CAROUSEL_EDITOR_STEP_CHECK_SQL` is `editor_step IN (0, 2, 3)`, and the check on `carousels` is `ck_carousels_editor_step`. `PATCH /api/v1/carousels/{carousel_id}/step` returns 400 for step 1 (`INSTRUCTIONS_LOCKED_DETAIL`, "Instructions is locked.") and for step 4. `OPENABLE_EDITOR_STEPS` in `apps/ops/src/pages/carouselSteps.ts` omits step 1. The control's accessible name uses `INSTRUCTIONS_CLOSED_DETAIL`. `apps/ops/carouselSteps.test.ts` asserts that sentence.

Inspiration and rules are still two `text` columns on `carousels` (`app/models/carousel.py`), not null, server default `""`. `POST /api/v1/carousels` in `app/api/v1/carousel_writes.py` writes both as `""`. `CarouselReadResponse` still returns them. `PATCH /api/v1/carousels/{carousel_id}/guidance` (`patch_source_guidance` in `app/api/v1/carousel_text.py`) still saves them, capped at `MAX_GUIDANCE_LENGTH` (8000). The ops form that edited them is gone (task 4.16). `patchCarouselGuidance` in `apps/ops/src/api/client.ts` has no caller.

Per-slide generate still reads the columns. `generate_source_slide` is `POST /api/v1/carousels/{carousel_id}/slides/generate` (the Slides button `#generate-slide`, "Generate slide"). `generate_slide_text` is `POST /api/v1/carousels/{carousel_id}/slides/{slide_id}/generate` (the slide editor button `#generate-slide-text`, "Generate text"). Both call `_draft_or_http`, which passes `carousel.inspiration` and `carousel.rules` into `TextGenerationProvider.draft_slide_text`. The fake provider and the OpenAI prompt in `app/carousels/text_generation.py` label those two strings Inspiration and Rules. Dropping the columns in the copy revision would break both routes. Tasks 5.1, 5.9, and 5.10 split the copy, the read switch, and the drop so those two buttons keep drafting.

There is no instruction table. Research is the nearest pattern: `research_items.body` is Markdown or plain text up to `RESEARCH_BODY_MAX_CHARACTERS` (1,000,000), and `carousel_research_items.position` orders the links. Research routes live in `register_source_write_routes` (`POST`, `PUT`, and `DELETE` under `/api/v1/carousels/{carousel_id}/research`). Delete closes positions the way `_close_research_positions` does. The Research page edits a title and a body in a textarea, with no preview. Autosave is `useSkeletonAutosave` at `SKELETON_AUTOSAVE_DELAY_MS` (700), `SkeletonAutosaveStatus`, and `leaveAfterAutosave`. `CarouselsPage` already flushes the open step in `flushOpenEdits` before `handleStep` changes steps. Album image edits join that flush through `AlbumEditorActions`. `apps/ops/package.json` depends on React only. There is no Markdown library.

**Decisions.** Settled with Mu, plus the choices this sheet needs so a task can name a file. The open decisions at the end are the choices Mu can still change.

- A document is one row in `carousel_instructions`: the current body and a `position` starting at 0. Several documents are one prompt later, in position order. This phase does not call the provider from step 1.
- The written text is the instructions. Generate does not return a revised document. Review of slides is phase 6.
- An empty body is stored as `""`. The textarea placeholder is a sample template. The sample is not written unless the operator types it. A carousel with no rows still shows that empty editor, so the sample is visible and Generate stays disabled.
- The copy revision keeps `inspiration` and `rules`. Per-slide generate keeps reading them until task 5.9. Task 5.10 drops the columns after that.
- Instructions do not lock Content or Slides. Final stays locked. Create still opens on Basic.
- One Generate button sits under the instructions editor, for the whole carousel. Phase 5 places it and disables it until some document has real text. Pressing it is phase 6.
- Add, remove, and reorder are explicit actions, the way research links are. The body autosaves. There is no Save button.

### Data model

- [x] **5.1 Add instruction documents and copy inspiration and rules**

  Alembic revision `carousel_instructions`, down-revision `carousel_editor_step_content`. New table `carousel_instructions`: `id`, `carousel_id` (cascade on carousel delete), `position` (check `position >= 0`), `body` (text, not null, server default `""`, check `char_length(body) <= 1000000`), and the timestamp columns from `TimestampMixin`. Unique `(carousel_id, position)`. No title column and no version column.

  `CarouselInstruction` lives in `app/models/carousel.py` next to `CarouselResearchItem`, exported from `app/models/__init__.py`. `Carousel.instructions` is ordered by `position`. `CAROUSEL_INSTRUCTION_POSITION_CHECK_SQL` and `INSTRUCTION_BODY_MAX_CHARACTERS` sit in that file next to `CAROUSEL_RESEARCH_POSITION_CHECK_SQL`. `INSTRUCTION_BODY_MAX_CHARACTERS` is 1,000,000, the same number as `RESEARCH_BODY_MAX_CHARACTERS` in `app/models/research_item.py`.

  Upgrade inserts one row at position 0 when `btrim(inspiration) <> ''` or `btrim(rules) <> ''`. The body is the stored strings under two headings, including a field that is blank:

  ```
  ## Inspiration

  {inspiration}

  ## Rules

  {rules}
  ```

  The trailing newline is part of the body. A carousel whose inspiration and rules both trim to empty gets no row. That includes the Default carousel, whose columns are the server default `""`. The revision does not drop `inspiration` or `rules`, does not change `ck_carousels_editor_step`, and does not move `editor_step`, albums, research, or slides. Downgrade drops `carousel_instructions` and the rows in it. The two columns stay.

  Acceptance: upgrade, downgrade, upgrade again. A carousel with both fields gets one document whose body equals that template filled with the stored strings. A carousel with only rules gets the same shape, with a blank Inspiration section. A carousel with both fields blank, including Default, has no instruction row, and its inspiration and rules still read back. `POST /api/v1/carousels/{carousel_id}/slides/generate` and Generate text still draft from the columns. Tests live in `apps/server/tests/test_carousel_instructions_migration.py`, on the pattern of `test_carousel_steps_migration.py` (skip when Postgres is down). `test_carousel_steps_migration.py` still rejects `editor_step` 1 at revision `carousel_steps`.

### API

- [x] **5.2 Return instruction documents on the carousel detail**

  `CarouselReadResponse` gains `instructions`: `{id, position, body}` in position order, one entry per row. The list item stays without them, the same way research stays off `CarouselListItemResponse`. Serialize beside `_research_in_position_order` in `app/api/v1/carousels.py`. Readers can call the existing GET. `inspiration` and `rules` stay on the detail until task 5.10. This PR does not add write routes and does not change `steps`.

  Acceptance: a copied carousel reloads its one document in order. Default reloads an empty list. A reader can GET the detail. The list route's shape is unchanged.

- [x] **5.3 Store Instructions as an open step**

  Alembic revision `carousel_editor_step_instructions`, down-revision `carousel_instructions`. Replace `ck_carousels_editor_step` so the check matches `editor_step IN (0, 1, 2, 3)`. Update `CAROUSEL_EDITOR_STEP_CHECK_SQL`. Existing rows stay on 0, 2, or 3. Downgrade sets any stored 1 back to 0, then restores `editor_step IN (0, 2, 3)`.

  `carousel_step_states` takes `has_instruction_text`. The caller sets it when any instruction body strips to a non-empty string. `instructions` is `done` when that flag is true and `available` when it is false. It is not locked. `content`, `slides`, and `final` stay on their current rules. Research still does not change step state. `STORED_EDITOR_STEPS` includes 1. `UNKNOWN_EDITOR_STEP_DETAIL` says `editor_step` must be 0, 1, 2, or 3. `PATCH /api/v1/carousels/{carousel_id}/step` stores 1 for an admin. Step 4 is still 400. A reader is still rejected. Create still stores step 0.

  Update the callers and the tests that require `instructions` to be locked: `test_carousel_step_state.py`, `test_carousel_editor_step.py` (including `test_instructions_and_final_are_refused` and `test_refusing_instructions_leaves_inspiration_and_rules`), `test_carousel_album_link.py`, `test_carousel_research_link.py`, `test_carousels.py`, and `test_models.py`. The migration test is `test_carousel_editor_step_instructions_migration.py`.

  Acceptance: an admin can store step 1 on a carousel with no documents and on one that has text. A carousel with a non-blank body reads `instructions: done`. Default reads `instructions: available` and still opens on Slides. Step 4 is 400 and the stored step stays. A picture carousel with no album still refuses step 3. Inspiration and rules are unchanged by the step PATCH.

- [x] **5.4 Create, update, reorder, and delete instruction documents**

  Register these on `register_source_write_routes` in `app/api/v1/carousel_writes.py`, next to the research routes. Admin only. The response is the carousel detail, with `instructions` in position order and `steps` from task 5.3.

  `POST /api/v1/carousels/{carousel_id}/instructions` with `{body}` appends at the next position. A missing body stores `""`. `PATCH /api/v1/carousels/{carousel_id}/instructions/{instruction_id}` with `{body}` replaces that body. `PUT /api/v1/carousels/{carousel_id}/instructions` with `{instruction_ids}` replaces the order. `DELETE /api/v1/carousels/{carousel_id}/instructions/{instruction_id}` drops that row. Positions close up to 0, 1, 2, the way `_assign_research_positions` does, including the park-then-assign move that the unique `(carousel_id, position)` constraint needs.

  Unknown id is 404. The same id twice in one list is 400 and the stored order stays. An id from another carousel is 404. A body longer than `INSTRUCTION_BODY_MAX_CHARACTERS` is 400 and nothing is written. Deleting the carousel drops its documents. These routes do not write `inspiration` or `rules`, do not call `draft_slide_text`, and do not insert slides.

  Acceptance, in `apps/server/tests/test_carousel_instructions.py`: two documents round-trip in the stored order. Reorder survives a reload. Delete closes the gap. A duplicate id is 400. A reader is rejected. A too-long body is 400. After a write, inspiration and rules still read back, and Generate text still drafts from those columns.

### Step shell

- [x] **5.5 Open the Instructions step**

  Enable step 1 in `OPENABLE_EDITOR_STEPS`. `carouselStepAccessibleName` and `carouselStepTitle` stop treating Instructions as a closed later phase. Remove `INSTRUCTIONS_CLOSED_DETAIL`. An available Instructions control is unmarked. A done one uses the existing done style (`--ops-success` through `is-done`). The current step stays `--ops-primary`. Update `apps/ops/carouselSteps.test.ts`.

  `CarouselsPage` shows `CarouselInstructionsStep` when the displayed step is 1, the same way it shows `CarouselBasicStep` and `CarouselContentStep`. Changing step still goes through `handleStep` and `flushOpenEdits`, and PATCHes `editor_step` for an admin. A reader can look, via `displayedEditorStep`, and does not PATCH. Final stays disabled. Slides, Generate slide, and Generate text stay where they are.

  The sample text for an empty document lives in `apps/ops/src/pages/instructionTemplate.ts` as `INSTRUCTION_SAMPLE_TEMPLATE`. Task 5.6 uses that same constant as the textarea placeholder.

  ```
  # What this carousel is for

  Who it is for, and what they should take from it.

  ## Voice

  Short sentences. One idea per slide.

  ## Include

  - The claim this carousel makes
  - A fact that has to stay accurate

  ## Leave out

  - Anything this carousel should not say
  ```

  This PR shows the documents in position order as read-only source. Zero documents shows "No instructions yet." and that sample, labeled as a sample that is not saved. There is no textarea and no Generate button yet. The sample is not written to a row.

  Acceptance: an admin can open Instructions, reload, and land there again (`editor_step` 1). Default can open it and still has no document row. Content and Slides open under the same rules as now. The Instructions control is not described as a later phase. Final still does not navigate.

### Editor

- [x] **5.6 Edit a document with a preview, the sample placeholder, and autosave**

  Replace the read-only body with a textarea and a preview. The textarea's placeholder is `INSTRUCTION_SAMPLE_TEMPLATE` from task 5.5. The value stays `""` until the operator types. The preview is `InstructionMarkdownPreview`, fed by `renderInstructionMarkdown` in `apps/ops/src/pages/instructionMarkdown.ts`. That function escapes HTML and renders ATX headings (`#`, `##`, `###`), paragraphs, unordered lists, and `**strong**` / `*emphasis*`. Those are the marks in the sample. When the draft is empty, the preview renders the sample and says "Sample. Not saved." When the draft has text, the preview renders the draft.

  The body autosaves at 700ms through `useSkeletonAutosave`, `SkeletonAutosaveStatus`, and `SKELETON_AUTOSAVE_DELAY_MS`. The readiness helper lives in `apps/ops/src/pages/carouselInstructions.ts`. A draft with text is ready. A stored document's empty body is ready, and the save PATCHes `""`. An empty draft with no row is idle, so autosave does not POST. The first draft that has text POSTs `/instructions`. A later edit PATCHes that id. Clearing a stored document leaves the row, and the placeholder comes back. The placeholder string is never the saved body.

  `CarouselInstructionsStep` exposes flush and dirty the way `AlbumEditorActions` does. `flushOpenEdits` in `CarouselsPage` awaits it, and `handleStep` and Back keep using `leaveAfterAutosave`. A reader sees `ReadOnlyNotice` and a disabled textarea, and does not schedule a save.

  Tests: `apps/ops/carouselInstructions.test.ts` for the readiness helper (a stored empty body is ready, an empty draft with no row is idle, and the sample is not the stored value) and `apps/ops/instructionMarkdown.test.ts` for the renderer.

  Acceptance: typing into an empty carousel creates one document after the 700ms delay, and a reload shows that text, not the sample. Clearing it stores `""`, the placeholder returns, and Generate text on Slides still uses the inspiration and rules columns. Leaving the step flushes a pending edit. A body the API rejects as too long shows the autosave error and does not drop the previous body.

- [x] **5.7 Add, remove, and reorder documents**

  The step lists documents as Document 1, Document 2, from `position + 1`, in position order. The selected one's body is the editor from task 5.6. Add calls POST with `{body: ""}`, selects the new row, and shows the sample placeholder. Remove calls DELETE. Move up and Move down call PUT with the full id list, the same interaction as `moveAttachedResearch` in `carouselResearch.ts`. There is no drag library.

  Switching documents or removing the open one flushes through `leaveAfterAutosave` first. Removing the last row returns the step to the empty editor from task 5.6, with no id until the next typed save. A reader can look and cannot add, remove, or reorder.

  Acceptance: two documents stay in the chosen order after reload. The preview follows the selected document. Removing one closes the gap in the labels. Add on a carousel that had no rows creates an empty stored document, and the sample is still not the stored body. Reorder does not change either body.

- [x] **5.8 Place Generate, disabled until there is real instruction text**

  One button, `#generate-instructions`, sits below the editor. Its label is "Generate". It is disabled when every document body is empty after trim. The check uses the open draft for the selected document and the stored bodies for the others, via `instructionsGenerateEnabled` in `carouselInstructions.ts`. The sample and a whitespace-only body do not enable it. A reader always sees it disabled. While it is disabled, its accessible name says filling slides from these instructions is a later phase.

  The button has no request. It does not call `generateCarouselSlide`, `generateSlideText`, `generateCarouselArtifact`, or a new route. It does not write slides. A line under it says Generate fills slides in a later phase. `#generate-slide` and `#generate-slide-text` stay on Slides.

  Acceptance, in `carouselInstructions.test.ts`: an empty draft is disabled, a placeholder-only editor is disabled, one non-blank document among blanks is enabled, and a cleared draft with no other text is disabled. Clicking the enabled button leaves the carousel's slides and documents unchanged.

### Per-slide generate

- [x] **5.9 Read instruction documents from Generate slide and Generate text**

  Add `instruction_prompt_text` in `app/carousels/instructions.py`. It takes bodies in position order, drops any body that strips to empty, and joins the rest with a blank line. `_draft_or_http` loads `carousel.instructions` in that order and calls `draft_slide_text` with that string as `inspiration` and `""` as `rules`. `FakeTextGenerationProvider` and `OpenAITextGenerationProvider` keep their two arguments. Phase 6 should use this same join for the instructions button.

  The columns stay in this PR. `PATCH .../guidance` still writes them. Generate slide and Generate text ignore them. A carousel with no documents, or only blank bodies, passes two empty strings, which is what both columns being `""` does today. Direct tests that call `draft_slide_text` with an inspiration and a rules string stay. HTTP tests in `test_slide_text_generation.py` that set the columns and then generate must store instruction documents and expect the joined text in the fake draft.

  Acceptance: a carousel whose only text is the copied document drafts from that body, and a guidance PATCH that changes the columns does not change the next draft. A new carousel with no documents still drafts from two empty strings. Generate slide still creates one draft slide, and Generate text still leaves the live text in place until Accept.

- [x] **5.10 Drop inspiration and rules**

  Alembic revision `carousel_instructions_drop_guidance`, down-revision `carousel_editor_step_instructions`. Drop `carousels.inspiration` and `carousels.rules`. Downgrade adds both columns back as text, not null, server default `""`, and leaves them empty. It does not parse documents back into the columns. Instruction rows stay through both directions.

  Remove the columns from `Carousel`, from `CarouselReadResponse`, and from `CarouselGuidancePatchRequest`. Remove `PATCH /api/v1/carousels/{carousel_id}/guidance` and `patch_source_guidance`. `POST /api/v1/carousels` stops setting the two fields. Delete `patchCarouselGuidance` from `apps/ops/src/api/client.ts`. Update the model notes in `app/models/carousel.py` and `app/models/__init__.py` so the draft is described as coming from `carousel_instructions`. Update `test_models.py` and any HTTP test that still sends a guidance body. Leave the historical assertions in `test_alembic.py` and `test_source_theme_migration.py` that read older revisions of `sources.inspiration`.

  Acceptance: the detail has `instructions` and has neither column. Guidance PATCH is gone. Upgrade from a database that already ran 5.1 keeps the copied documents, and Generate text still drafts from them. Downgrade recreates two empty columns and keeps the documents. Default still has no instruction row.

### Tests

- [x] **5.11 Run the full server and ops suites**

  From `apps/server`, `python -m unittest discover -s tests`. From `apps/ops`, `node --test *.test.ts`. This PR adds no product behavior. It fixes failures that this phase's tasks left, and it does not start a new feature. Migration tests that skip because Postgres is down stay skipped, the same way `test_carousel_steps_migration.py` skips. A skip is not a failure. The phase is done when both suites pass aside from those skips.

### Open decisions

1. The copied document uses the two headings `## Inspiration` and `## Rules`, in that order, even when one field is blank. The sample template is a different text, and only the empty editor shows it.
2. The columns stay through tasks 5.1–5.9 because `_draft_or_http` reads them. Task 5.9 passes the joined document text as `inspiration` and `""` as `rules`, which changes the fake draft and the OpenAI user prompt for a carousel that had both fields. Task 5.10 then drops the columns. Say if the joined text should be the rules argument instead, or if the two headings should be parsed back into the two arguments until phase 6 replaces the call.
3. A document has no title. The list labels it Document 1, Document 2 from `position`.
4. The body cap is 1,000,000 characters, the research cap. The old guidance cap is 8,000 per column. Migrated text fits either cap.
5. The preview is a local renderer for headings, paragraphs, lists, and emphasis. `apps/ops` has no Markdown dependency. Links, fences, and tables can wait for a library.
6. The sample wording is the block in task 5.5.
7. Downgrade of task 5.10 restores empty inspiration and rules columns and does not copy the documents back into them.
8. Phase 8 still calls the generation snapshot "the instruction version." This sheet does not add a version table, and it does not rewrite phase 8.

## Carousel editor

The open carousel is one scrollable page. Links at the top scroll to Basic, Instructions, Content, Slides, and Final. The page does not switch steps, and it does not hide a section. `editor_step` stays on the API and is not what the page uses to choose a panel. Generate sits below Content. It enables when some instruction document has real text, and a reader always sees it disabled. Clicking it does not fill slides until phase 6. A picture carousel with no album still shows Slides, with the note to attach an album on Content first. Final is the last heading and says assembly is a later phase. Hand entry of slides stays on this page.

## 6. AI slide generation

**Status.** Checklist. Head revision on main is `carousel_instructions_drop_guidance`. The single-page editor (PR #103) did not add a revision. Implement in the order below. Each box is one PR, and the console still works after that PR. Each box names the tests that land with it. Task 6.11 runs the full suites.

**Goal.** Pressing Generate, the button below Content, fills a new carousel's empty Slides section with one drafted set. The provider sees every instruction document in position order, the attached album, the attached research, and the exclusion rules. It returns a name, text for each named text element, and an album image id. The operator accepts or discards that set as a whole. Until it is accepted, those slides stay draft and off Final. Hand entry stays.

**What the code does today.** The open carousel is one page. `CAROUSEL_EDITOR_BLOCKS` in `apps/ops/src/pages/carouselPage.ts` stacks Basic, Instructions, Content, then Generate, then Slides, then Final. `CarouselGenerateControl` renders `#generate-instructions` under Content (`#carousel-generate`). The click calls `instructionsAfterGenerateClick`, which returns the same carousel. `INSTRUCTIONS_GENERATE_HINT` says Generate fills slides in a later phase. `instructionsGenerateEnabled` in `carouselInstructions.ts` enables the button for an admin when some instruction body trims to text. The sample placeholder and a whitespace-only body leave it disabled. A reader always sees it disabled. The button does not call `generateCarouselSlide`, `generateSlideText`, or `POST /api/v1/generate/carousel`.

Slides on that page starts empty for a new carousel: `CarouselsPage` shows "No slides yet." Hand entry is `#add-slide` and the slide editor. A hand-entered slide is stored `text_status` `live` in `create_slide` (`app/api/v1/carousel_writes.py`). `#generate-slide` is `POST /api/v1/carousels/{carousel_id}/slides/generate` (`generate_source_slide`). It appends one slide with `text_status` `draft`, an empty exclusion list, and no image. `#generate-slide-text` is `POST /api/v1/carousels/{carousel_id}/slides/{slide_id}/generate` (`generate_slide_text`). `#accept-slide-text` is `POST .../accept-text` (`accept_slide_text`). Both generate routes call `_draft_or_http` in `app/api/v1/carousel_text.py`. That loads `carousel.instructions` in position order, joins them with `instruction_prompt_text` (`app/carousels/instructions.py`), and calls `TextGenerationProvider.draft_slide_text` with that string as inspiration and `""` as rules. A missing key is HTTP 409 via `_provider_or_http`. A provider failure is HTTP 502 and writes nothing.

`FakeTextGenerationProvider` and `OpenAITextGenerationProvider` live in `app/carousels/text_generation.py`. `TEXT_GENERATION_PROVIDER` is `openai` or `fake`. `OPENAI_MODEL` defaults to `gpt-4o-mini`. The fake provider fills one slide from the element label, the inspiration, and the rules, with no network. OpenAI posts one chat completion to `OPENAI_CHAT_COMPLETIONS_URL` with `response_format` `json_object` and a 30 second timeout. `drafted_text_from_openai_response` reads `name` and `texts` (`skeleton_element_id`, `value`). `DraftedSlideText` is one name and one string per text element. There is no collection type and no collection route.

Draft copy is `slide_element_texts.draft_value`. Live copy is `value`. `slides.text_status` is `draft` or `live` (server default `live`). `_store_draft_texts` writes `draft_value` and leaves `value`. `slide_counts_as_live` in `app/carousels/slide_text_review.py` is true only for `live`. `live_slides` is what `app/api/v1/campaigns.py` passes into `assemble_carousels`. A draft slide is already left out of a run. Final is still the locked heading `finalSectionNotice` (`FINAL_CLOSED_DETAIL`). This phase does not open it.

A slide image is `slides.album_image_id`, pointing at `album_images`. The album is `carousels.album_id`. An image row has `alt_text`, `source`, and `license_note`. It has no label column. Research is `carousel_research_items` in `position` order, and the body is `research_items.body`. `CarouselReadResponse.research` returns id, title, slug, and position. It does not return the body. Exclusions are `slide_exclusions`, stored in both directions. `normalized_exclusion_ids` and `assert_slide_pick_allowed` live in `app/carousels/slide_exclusions.py`. A new carousel has no slides, so it has no exclusion rows. The slide-count helper is `slide_count_or_global_default` in `app/global_settings.py`: a passed count is kept, and null draws an integer from 5 to 8 (`SLIDE_COUNT_DEFAULT_LOW`, `SLIDE_COUNT_DEFAULT_HIGH`). Nothing on the carousel stores a count. `generation_number` is the phase 8 snapshot counter and stays 1. There is no review-batch table.

**Settled for this phase.**

- Generate (`#generate-instructions`, below Content) sends every instruction document as one prompt, in position order, using `instruction_prompt_text`. The same prompt includes the attached album and the attached research. The album is the image list on `carousels.album_id`, in `album_images.position` order. Each image is sent as its id, `alt_text`, `source`, and `license_note`. The bytes are not sent. Research is the attached items in `carousel_research_items.position` order, title plus `research_items.body`.
- The provider writes slides: `name`, one string per named text element from `skeleton_text_elements`, and an `album_image_id` chosen from that album. The image is chosen. It is not drawn.
- Review is of the whole generated set. The operator accepts it or discards it. Until it is accepted, those slides stay `text_status` `draft`, so `live_slides` keeps them off a run and off Final. Hand entry stays (`#add-slide`, the editor, `#generate-slide`, `#generate-slide-text`, `#accept-slide-text`). The draft/live gate stays. Accepting the set does not mark an older draft live.
- Exclusion rules are passed into the model: the carousel's `slide_exclusions`, collapsed to one line per unordered pair, with both slide names and ids.
- A new carousel shows "No slides yet." in the Slides section. After Generate, those drafted slides appear in that same section on this page.

The choices below that a task has to name — the count, a second Generate, the JSON shape, the fake provider, and the per-slide buttons — are Open decisions. The tasks use those choices so a PR can name a file. Mu can still change them.

### Data model

- [x] **6.1 Add a slide draft batch**

  Alembic revision `slide_draft_batches`, down-revision `carousel_instructions_drop_guidance`. New table `slide_draft_batches`: `id`, `carousel_id` (cascade on carousel delete), `status` (text, not null, check `status IN ('pending', 'accepted', 'discarded')`), `slide_count` (integer, not null, check `slide_count >= 1`), and the timestamp columns from `TimestampMixin`. A partial unique index `uq_slide_draft_batches_one_pending_carousel` on `carousel_id` where `status = 'pending'`. One carousel can hold one pending set.

  `slides.draft_batch_id` is a nullable UUID, foreign key to `slide_draft_batches.id`, `ON DELETE SET NULL`, indexed. Deleting a batch does not delete slides. `SlideDraftBatch` lives in `app/models/carousel.py` next to `Slide`, exported from `app/models/__init__.py`. `Carousel.draft_batches` and `Slide.draft_batch` are the relationships. `SlideTextStatus`, `draft_value`, and the server default `live` stay. Upgrade inserts no rows and does not update `text_status`, `draft_value`, `album_image_id`, or `generation_number`. Downgrade drops `draft_batch_id` and then the table. Albums, research, instructions, and slides stay. This table is the review state for one press of Generate. It is not the phase 8 snapshot, and it is not `campaign_carousels`.

  Acceptance: upgrade, downgrade, upgrade again. Default still has six live slides, a null `draft_batch_id` on each, and no batch row. A carousel that already has a draft slide is still draft, with its `draft_value` unchanged. A second pending row for one carousel fails the partial unique index. An accepted row and a pending row for the same carousel can both exist. Tests live in `apps/server/tests/test_slide_draft_batches_migration.py`, on the pattern of `test_carousel_instructions_migration.py` (skip when Postgres is down).

### Prompt

- [x] **6.2 Build one collection prompt**

  Add `collection_prompt_text` in `app/carousels/collection_prompt.py`. It takes instruction bodies already in position order, research items as title plus body in position order, album images as id, position, alt text, source, and license note, exclusion pairs as the two names and ids, the skeleton text elements (`TextElementPrompt`), the slide count, and whether an image is required. It calls `instruction_prompt_text` for the bodies. Blank instruction bodies are dropped there. An attached research item is included even when its body is empty.

  The user text is these sections, in this order: Instructions, Research, Album images, Slides that cannot be shown together, Text elements, then one line with the slide count and either `Image: required` or `Image: none`. An empty section says `None.` An album line is `{id} position {n} alt: {alt} source: {source} note: {note}`. An exclusion line is `{name} ({id}) cannot be shown with {name} ({id})`. The caller passes each unordered pair once. The function does not read the database and does not call a provider.

  Acceptance, in `apps/server/tests/test_collection_prompt.py`: two instruction bodies join in order with a blank line, and a blank body is dropped. Two research items stay in the given order. Two album images stay in the given order and include alt text, source, and license note. One exclusion pair appears once. The count and `Image: required` appear. No images and no research each produce `None.`

### Provider

- [x] **6.3 Validate a collection JSON object**

  Add `DraftedCollectionSlide` (name, `values_by_element_id`, `album_image_id`) and `DraftedSlideCollection` (slides, in order) in `app/carousels/collection_generation.py`. `parse_slide_collection` reads one JSON object:

  ```
  {"slides": [{"name": "...", "texts": [{"skeleton_element_id": "...", "value": "..."}], "album_image_id": "..."}]}
  ```

  `album_image_id` may be JSON null. The parse takes the requested count, the text elements, the allowed image ids, and `image_required`. It returns a draft of that count. A failure raises `TextGenerationError` (`TEXT_GENERATION_FAILED_DETAIL`). These fail the whole object: the slide list length differs from the count, a name that strips to empty, a name that is not a string, a missing or extra `skeleton_element_id`, a value that is not a string, an image id outside the allowed set, an image id when `image_required` is false, or a null image id when `image_required` is true. An empty string value is allowed. The same image id may appear on more than one slide. Names are collapsed whitespace and cut to `MAX_DRAFTED_NAME_LENGTH` (200), the same cut as `_drafted_name`.

  `openai_collection_request_body` builds the chat completion body the way `_openai_request_body` does: `response_format` `{"type": "json_object"}`, a system message that the reply is JSON only, and the user content from `collection_prompt_text` plus the JSON shape above. The key is not in the body. This function does not call the network. `draft_slide_text` stays as it is.

  Acceptance, in `apps/server/tests/test_slide_collection_text.py`: a valid object with two slides round-trips. A short list, a blank name, an unknown element id, an unknown image id, an image when none is required, and a missing image when one is required each raise `TextGenerationError`. An empty text value is kept. The request body uses `json_object` and contains the instruction text.

- [x] **6.4 Draft a collection from the fake provider and from OpenAI**

  Add `draft_slide_collection` on `TextGenerationProvider`, `FakeTextGenerationProvider`, and `OpenAITextGenerationProvider`. The argument is the same pieces `collection_prompt_text` takes, plus the model call's settings on the OpenAI class. Both methods return `DraftedSlideCollection`. Neither writes rows.

  The fake method does not use the network. It returns exactly `slide_count` slides. The name is `Drafted slide 1`, `Drafted slide 2`, and so on, cut to `MAX_DRAFTED_NAME_LENGTH`. Each element value joins, with `". "`, the element label and the instruction text from `instruction_prompt_text`. When an image is required, slide `i` uses the image id at `i % len(images)` in the list it was given. When an image is not required, `album_image_id` is null. Exclusion pairs do not change the fake names. They are accepted so the caller can pass the same object it shows the model.

  The OpenAI method posts `openai_collection_request_body` to `OPENAI_CHAT_COMPLETIONS_URL` with the bearer key, timeout 30 seconds, the same way `draft_slide_text` does. It parses the message content with `parse_slide_collection`. An HTTP error, a non-JSON body, or a parse failure raises `TextGenerationError`. `require_text_generation_provider` is unchanged: `fake` still returns the fake provider, and `openai` still requires `OPENAI_API_KEY`.

  Acceptance, in `test_slide_collection_text.py`: the fake provider returns five slides when asked for five, names them `Drafted slide 1` through `Drafted slide 5`, includes the instruction text in each element, and round-robins two image ids. With `image_required` false, every `album_image_id` is null. `draft_slide_text` on the fake provider still returns one slide. An OpenAI body that fails `parse_slide_collection` raises `TextGenerationError`. Direct tests of `draft_slide_text` still pass.

### API

- [x] **6.5 Add the generate-collection route**

  `POST /api/v1/carousels/{carousel_id}/slides/generate-collection`, registered in `register_source_text_routes` (`app/api/v1/carousel_text.py`). Admin only, same as `generate_source_slide`. The response is the carousel detail from `serialize_carousel`. The handler lives in a thin route. The write helper lives in `app/carousels/slide_collection.py`.

  The count is `slide_count_or_global_default(None)`. No instruction body is parsed for a number. The helper stores that integer on the batch. HTTP tests patch `slide_count_or_global_default` to a fixed integer. The prompt is built from `carousel.instructions` (position order, through `collection_prompt_text`), `carousel.research_links` and each `research_item.body`, `carousel.album.images` when `album_id` is set, and the exclusion pairs on this carousel. Pairs stored in both directions become one line. `image_required` is `skeleton_requires_image`.

  These return before the provider is called, and they write nothing. No instruction text after `instruction_prompt_text` is 400, detail `Add instruction text before generating slides.` A skeleton with no text elements is 400, `NO_TEXT_ELEMENTS_DETAIL`. A picture skeleton with a null `album_id` is 400, detail `Attach an album on Content first.` A picture skeleton whose album has no images is 400, detail `This album has no images yet.` A pending batch already exists is 409, detail `Accept or discard the generated set before generating another.` The provider is `_provider_or_http`: off is 409, and `TextGenerationError` is 502. A 400, 409, or 502 leaves slides and batches as they were.

  On success the helper inserts one `slide_draft_batches` row with `status` `pending` and the chosen `slide_count`, then one slide per drafted item at the end of the carousel. Positions start at `_next_slide_position` and increase by one. Each slide gets the drafted name, `text_status` `draft`, `draft_batch_id` set, `exclusions` empty, and `album_image_id` from the draft. Text goes through `_store_draft_texts`, so `value` stays `""` and `draft_value` holds the string. One commit. A failure rolls the batch and the slides back.

  `SlideReadResponse` gains `draft_batch_id` (null when the slide is in no batch). `CarouselReadResponse` gains `pending_slide_draft_batch`: null, or `{id, status, slide_count}` for the pending row. `serialize_carousel` and `serialize_slide` fill them. `live_slide_count` still counts `live_slides` only. `carousel_step_states` still counts every slide toward the done mark of two, so a set of five drafts marks Slides done. Leave that rule. The route does not write instructions, research, album files, `generation_number`, or `campaign_carousels`. It does not call `draft_slide_text`, `assemble_carousels`, or `POST /api/v1/generate/carousel`.

  Acceptance, in `apps/server/tests/test_slide_collection.py`, with `TEXT_GENERATION_PROVIDER=fake`: a carousel with two instruction documents, two research items, and two album images gets the patched count of slides, named `Drafted slide 1` onward, each text element containing the joined instructions, `draft_value` set, `value` `""`, `text_status` `draft`, and image ids round-robin. The detail includes the pending batch. A second POST is 409 and the slide count stays. A carousel with an older draft slide (null `draft_batch_id`) keeps that slide draft. Default, with no instruction text, is 400 and still has six live slides. A picture carousel with no album is 400. A reader is rejected. Provider off is 409 and writes nothing.

- [x] **6.6 Accept the whole set**

  `POST /api/v1/carousels/{carousel_id}/slide-draft-batches/{batch_id}/accept`, admin only, empty body, response `serialize_carousel`. The batch must be `pending` and belong to this carousel. Otherwise 404. The helper loads the slides whose `draft_batch_id` is this batch. Zero such slides is 400, detail `This set has no slides to accept.` The batch stays `pending`. A picture skeleton whose batch slide has a null `album_image_id` is 400, `IMAGE_REQUIRED_DETAIL`, and no slide in the set changes status.

  Otherwise, for each of those slides only, copy each `draft_value` onto `value`, set `draft_value` null, and set `text_status` `live`. Leave `name`, `album_image_id`, `exclusions`, and `draft_batch_id`. Set the batch `status` to `accepted`. One commit. Slides with a null `draft_batch_id` are untouched, including a draft from `#generate-slide` or `#generate-slide-text`: same `text_status`, same `value`, same `draft_value`. Hand-entered live slides stay live. `generation_number` stays.

  Acceptance, in `test_slide_collection.py`: accepting a set of three makes those three `live`, copies the drafted strings onto `value`, clears `draft_value`, and returns a null `pending_slide_draft_batch`. An older draft slide on the same carousel stays `draft` with its old `draft_value` and its old `value`. A live hand-entered slide keeps its text. Accepting an accepted batch is 404. A reader is rejected.

- [x] **6.7 Discard the whole set**

  `POST /api/v1/carousels/{carousel_id}/slide-draft-batches/{batch_id}/discard`, admin only, empty body, response `serialize_carousel`. The same 404 rule as accept. Delete each slide in the batch: clear its exclusion pairs with `_clear_exclusion_pairs`, then delete the row. Do not delete `album_images` rows or files, and do not call `_reject_when_paths_in_use`. Other slides keep their positions. Set the batch `status` to `discarded` and leave the row. `pending_slide_draft_batch` returns null. Slides outside the batch stay, including drafts that are not in the batch.

  Acceptance, in `test_slide_collection.py`: discard removes the generated slides, leaves a hand-entered slide and an older draft slide, leaves the album and its files, and leaves a `discarded` batch row. The next Generate can insert a new pending batch. Discarding a discarded batch is 404. A reader is rejected.

### Page

- [x] **6.8 Wire Generate to the collection route**

  `CarouselGenerateControl` posts `generateCarouselCollection` in `apps/ops/src/api/client.ts`: `POST /api/v1/carousels/{carouselId}/slides/generate-collection`, returning `CarouselReadResponse`. The click flushes open edits through `flushOpenEdits` and `leaveAfterAutosave` before the request, the same way `handleGenerateSlide` does, so the saved instruction bodies and the album are what the route reads. While the request runs, the label is `Generating…` and the button is disabled. Success replaces the open carousel. The Slides section is the same `#carousel-slides` on this page. "No slides yet." stays the empty copy. A set of drafted slides replaces that sentence. The status line uses the existing `statusMessage`: `Drafted a set of {n} slides. Accept the set to make them live.` A 400, 409, or 502 shows the API detail in `ErrorBanner`.

  Enablement moves to `collectionGenerateEnabled` in `apps/ops/src/pages/carouselCollection.ts`. The button is enabled for an admin when `instructionsGenerateEnabled` is true, `textGeneration.available` is true, and the carousel has no pending batch. A reader stays disabled. Provider off shows `textGeneration.detail` under the button. Replace `INSTRUCTIONS_GENERATE_HINT` with `Generate writes a draft set from the instructions, the album, and the research. Accept the set to make those slides live.` Delete `instructionsAfterGenerateClick`, `instructionsGenerateAccessibleName`, and `INSTRUCTIONS_GENERATE_LATER_DETAIL`. The disabled accessible name is `Generate. Add instruction text first.` when no document has text, `Generate. {detail}` when the provider is off, and `Generate. Accept or discard the generated set first.` when a pending batch exists. Add `draft_batch_id` on the slide type and `pending_slide_draft_batch` on `CarouselReadResponse` in `apps/ops/src/api/types.ts`. `#generate-slide` and `#generate-slide-text` stay on this PR.

  Acceptance, in `apps/ops/carouselCollection.test.ts` and an updated `carouselInstructions.test.ts`: an empty draft is disabled, one non-blank document is enabled, a reader is disabled, provider off is disabled, and a pending batch is disabled. The old later-phase hint is gone. The click helper that returned the carousel unchanged is gone.

- [x] **6.9 Review the set on the Slides section**

  When `pending_slide_draft_batch` is set, the Slides section shows a review block above the slide grid: `Review this generated set. It stays off Final until you accept it.` Accept set is `#accept-slide-draft-batch`. Discard set is `#discard-slide-draft-batch`. Accept calls `acceptSlideDraftBatch`. Discard calls `discardSlideDraftBatch`. Both return the carousel detail and replace the open carousel. Accept's status line is `Accepted the set. These slides are live.` Discard's is `Discarded the set.` A reader sees the sentence and both buttons disabled. The block is absent when the pending batch is null. This PR does not add a route and does not move the operator to another page. Final stays the locked heading.

  The draft badge on a batch slide stays, from the existing `text_status === "draft"` check. `live` in `carouselPageLede` still comes from `live_slide_count`, so a pending set does not increase it.

  Acceptance, in `carouselCollection.test.ts`: the review block is present only with a pending batch, and a reader cannot accept or discard. After a successful accept the helper's next state has a null pending batch. The Final notice is unchanged.

- [x] **6.10 Keep per-slide Generate next to the set**

  `#generate-slide` and `#generate-slide-text` still call `draft_slide_text` through `_draft_or_http`. They do not set `draft_batch_id`. `generate_source_slide` still appends one draft slide with no image and an empty exclusion list. `generate_slide_text` still leaves the live `value` in place until `#accept-slide-text`.

  `slideUsesCollectionReview` in `carouselCollection.ts` is true when the slide's `draft_batch_id` equals the pending batch id. On that slide, `#generate-slide-text` and `#accept-slide-text` are disabled. Their accessible names say the set is accepted or discarded from the Slides section. Name, text, image pick, and exclusions still autosave. A hand edit of a pending slide writes `draft_value` through the existing draft branch of `patch_slide`, and task 6.6's accept copies that current `draft_value`. Delete slide stays the existing delete. `#generate-slide` stays available during a pending set. The slide it creates has a null `draft_batch_id` and still uses `#accept-slide-text`.

  Acceptance: generating one slide while a set is pending leaves the pending batch and its slides, and the new slide has a null `draft_batch_id`. Generate text on a batch slide is disabled in `slideUsesCollectionReview`. Generate text on a hand-entered slide still drafts, and Accept text on that slide still marks it live without accepting the set. Server coverage stays in `test_slide_collection.py`. The helper is covered in `carouselCollection.test.ts`.

### Tests

- [x] **6.11 Run the full server and ops suites**

  From `apps/server`, `python -m unittest discover -s tests`. From `apps/ops`, `node --test *.test.ts`. This PR adds no product behavior. It fixes failures that this phase's tasks left, and it does not start a new feature. Migration tests that skip because Postgres is down stay skipped, the same way `test_carousel_steps_migration.py` skips. A skip is not a failure. The phase is done when both suites pass aside from those skips.

### Open decisions

These are the choices this sheet made so a task could name a file. The tasks above use them.

1. The slide count is `slide_count_or_global_default(None)`: one random integer from 5 to 8 inclusive, from `app/global_settings.py`. Instruction Markdown is not parsed for a count. The drawn integer is stored on `slide_draft_batches.slide_count`. Say if the count should be fixed, chosen on the page, or read from the instructions.
2. A second Generate while a pending batch exists is 409 and writes nothing. After accept or discard, Generate appends a new pending set at the next slide positions. It leaves live slides, hand-entered slides, and an older draft from Generate slide or Generate text. Say if Generate should replace every slide, or replace the pending set in place.
3. The model returns one JSON object, `slides` of `{name, texts: [{skeleton_element_id, value}], album_image_id}`, with `response_format` `json_object`, the same chat-completions call as `_openai_request_body`, timeout 30 seconds. A bad count, blank name, unknown element, unknown image id, an image when the skeleton needs none, or a missing image when it needs one fails the whole call with `TextGenerationError` and HTTP 502. Nothing is written. An empty text value is kept. The same album image may be chosen on more than one slide. Say if this should be a `json_schema` response, if a bad slide should be dropped, or if image reuse should be refused.
4. `album_images` has no label column. The album line uses `alt_text`, `source`, and `license_note`. Say if `source` alone should be the label, or if `license` should be included.
5. `FakeTextGenerationProvider.draft_slide_collection` returns exactly the requested count, names `Drafted slide 1` onward, fills each element from its label and the joined instruction text, and round-robins image ids when an image is required. `draft_slide_text` is unchanged. Say if the fake names or the image pick should differ.
6. `#generate-slide` and `#generate-slide-text` stay. They do not join the pending set. On a slide in that set, Generate text and Accept text are disabled. Generate slide stays available, and its new slide is reviewed with Accept text. Say if those buttons should be removed, or if Generate slide should be refused while a set is pending.
7. The model receives existing exclusion pairs and does not return new ones. Generated slides are stored with an empty `slide_exclusions` list. Hand entry of exclusions stays, including autosave on a pending slide. Say if the model should return pairs for the new slides.
8. Instruction bodies, research bodies, and the album list are sent in full. There is no extra character cap. Say if the prompt should be cut.
9. Accept copies each remaining batch slide's current `draft_value` onto `value`. A hand edit that autosaved into the draft is what becomes live. Deleting one slide of the set uses the existing delete. Accept of a batch that no longer has slides is 400, and the batch stays pending. Say if a pending set should be locked against edit and delete until Accept or Discard.
10. Discard keeps the batch row as `discarded` and deletes only its slides. It does not delete album files. Positions of other slides stay as stored. Say if the batch row should be deleted too.
11. The review controls sit in the Slides section of this page. The page does not scroll on its own. The Generate button does not pre-check the album: a picture carousel with no album, or an empty album, is a 400 from the route, shown in `ErrorBanner`. Say if Accept and Discard should sit next to Generate, or if the button should stay disabled until an album image can be chosen.

## 7. Final assembly

**Goal.** Turn the slides into the carousels an operator reviews, drawn with the skeleton.

**Scope.** Follow the instructions. Where a step has no guidance, use the built-in default. The slide-count example is a random count from 5 to 8. This replaces the campaign run, which only stores slide ids, and it replaces `POST /api/v1/generate/carousel`, which still draws `carousel_template_v1` from one Spotmu interest. The caption stops coming from the interest title. The text on the frame is the reviewed slide text. This phase does not call the model to write new copy. Key the assembled rows so phase 8 can hang them on generation 1 without copying them.

**Migration.** Do not convert old template artifacts into these carousels. They stay on the old queue until the campaign timeline. `campaign_carousels` remains the old assembly until this phase's rows replace it. Leave the old rows readable until phase 9.

**Open questions.** Does each assembled carousel become one draft? Does a draft freeze the slide's image file, or keep a pointer that can change? When the skeleton overlaps or a file is missing, preview marks the frame blocked and still writes a PNG. For a shipping draft, is that a blocked row, or no row? Where do the caption, hashtags, and any link come from? They are not on the slide. Do exclusion rules still split a group? Does Final read the Spotmu interest stored on the campaign?

**Task sheet.** The checklist is `docs/planning/phase_7_final_assembly.md`.

## 8. Generations

**Goal.** A generation is a snapshot. Duplicate it to try the next version.

**Scope.** The snapshot is the instruction version, the album, the research, and the slides. A new carousel is generation 1. Duplicate copies that snapshot so the next try does not edit the posted one. Performance, once it exists, attaches to the carousels assembled from that snapshot. This phase stores and duplicates. It does not drop losers or add slides from winners.

**Migration.** Backfill generation 1 for every carousel from the instruction version, album, research, and slides it has now. Empty album or research stays empty. Attach the Final rows from phase 7 to that generation.

**Open questions.** After a duplicate, do slide edits land only on the new generation? The album is shared. Does the snapshot store the album id, or the list of images it used at the time? A later upload to that album would change a shared id. It would not change a copied list.

**Task sheet.** The checklist is `docs/planning/phase_8_generations.md`.

## 9. Campaign timeline

**Goal.** Pick a campaign and see its posts.

**Scope.** Each post shows a status (upcoming, posted, or failed), the time, the content, and results when it has been posted. Queue, Schedule, and Results fold into this view. Approval becomes a post status. A cross-campaign view may remain. The campaign owns its schedule. The account keeps the posting cap across campaigns. That cap is the per-day number already stored on the account. Campaign rules are not designed in this phase.

**Migration.** Map old artifact and post-job rows onto the new statuses where the row is clearly a post. Template-loop artifacts that were never part of a generation stay off the carousel posts. They can remain on a cross-campaign view if that view stays. `draft`, `approved`, and `scheduled` need a decision before they all become upcoming.

**Open questions.** What does a campaign rule contain, where does it live, and how does it pick posts? Is approval its own status, or part of upcoming? The agreed labels are upcoming, posted, and failed. Who picks the clock time, the operator or a rule inside the account cap? Can a post still be edited after it has a time? Does create still require platforms and a Spotmu interest? If a cross-campaign view remains, is it one list or the old three pages?

## 10. Accounts and publishing

**Goal.** Connect a real social account and post from the campaign timeline. The first test is Spotmu.

**Scope.** Account rows exist. They do not store a login. Publish is a mock adapter. An Ayrshare adapter is in the tree and refuses the live call. This phase connects a real account and posts the media and the caption of a campaign post. Instagram and TikTok come first. The pipe can be rented. Paid ads stay out. The account cap already on the row is the cap across that account's campaigns.

**Migration.** None for carousels or generations. Do not add the login to the account row as it stands. That row has no token columns on purpose.

**Open questions.** Which Spotmu account is the first connection, and who owns the login? Official API, or a scheduler we already trust? What does the operator see when a post does not go out?

## 11. Measurement

**Goal.** After a post is live, pull views and engagement, and hang them on that generation's post.

**Scope.** Metric rows, a manual entry route, and a cluster median of the latest view counts exist. A stub can copy mock views onto a mock-published job. This phase reads views and engagement from the platform for each posted item and stores them on that post, so the generation can see them. The median can follow once those per-post numbers are real.

**Migration.** Snapshots already stored on a post job stay there. New pulls use that same snapshot shape and link to the campaign post.

**Open questions.** Which counts are engagement on the first pull: likes, comments, shares, saves? How soon after posting, and how often after that? Is the first place an operator looks the campaign timeline?

## 12. Next generation from results

**Goal.** From a posted generation, drop what lost and add slides modeled on what won.

**Scope.** Read the measurements on that snapshot's carousels. The next generation is a duplicate with the losers removed and new slides based on the winners. The provider drafts those slides. A person reviews them before they are live. This phase does not change the account cap or the campaign schedule.

**Migration.** None. It writes a new generation through the duplicate path from phase 8.

**Open questions.** What counts as a loss, and who decides? Does the operator confirm the drop before the next generation is saved? How many new slides, and does that count come from the instructions or from the default range?

---

## Housekeeping

- **S3 image storage.** Slide images, album images, thumbnails, skeleton previews, and carousel renders sit on disk under `ARTIFACT_STORAGE_DIR`. Move them to S3 behind the same save, open, and delete calls when more than one machine needs the bytes. Packaged `theme-defaults/…` files stay in the app until something copies them on purpose.
- **Word-count warning.** Optional, and not built. A skeleton text element may warn when the slide text runs long. The lean is a warning while editing, not a stored limit. The lorem word counts on the skeleton preview are a separate control.
