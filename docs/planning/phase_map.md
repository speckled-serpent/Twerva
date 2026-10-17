# Twerva — Phase map

*Last updated: 2026-10-17*  
*Status: What's left to implement, after the redesign agreed with Mu. Strategy: `docs/prompts/project.md`. Product design: `docs/prompts/product.md`.*

This list replaces the previous one. A Skeleton is the structure of a carousel: the background and the named elements. A Carousel is what an operator builds, in steps. A Slide is one frame of content inside it. Albums and Research are shared libraries. A generation is a snapshot of one carousel. The campaign is the timeline of posts.

The strategic phases in `docs/prompts/project.md` (Spotmu, then internal brands, then an optional external spin-off) stay as they are.

Build in the order below. The rename is a real change to the tables and the routes, so later phases can use the new names. Albums come before the Content step, because today's images sit on the slide and that step needs an album to attach. Research has nothing to import, so it stays a small phase after Albums. The step screen comes once both libraries exist. Instructions come before the model fills slides, because the call should read those documents. Hand entry of slides already works, so Final is not waiting on the model for a carousel someone typed. It still follows Instructions, so the first assembly uses the written rules. Generations come after Final so the snapshot includes the slides that will be posted, including ones the model wrote. The campaign timeline is where those assembled carousels become posts. Accounts, measurement, and the next generation follow the first posts.

---

## Done

A theme is the shape of a carousel frame: one background (picture, solid color, or gradient), spacing, and named elements. An element is text or an image, and the name is required. The theme editor covers that frame, autosaves frame and element edits, and previews the frame with lorem ipsum at a word count per text element. It does not ask the operator to mark the theme Draft or Live. The status column is still on the row. A campaign can pick any theme. Adding a text element adds an empty text on every unit of every source bound to that theme. Removing an element removes that text. A text element may omit a Spotmu text source. Unit text is the value stored for that element, under its name. A picture background or an image element stores a concrete image path.

A source is bound to one theme. Create asks for a name and that theme. There is one kind of source. Album and resource are gone, and the `resource_files` table is gone. A unit has a name, at most one image, and one text per named text element. The image field is there only when the theme has a picture background or an image element. A unit can name other units in the same source that it cannot be shown with. Images are a manual upload or a URL import, with a license and a source note, stored on disk. The path prefix is `albums/…`, or `theme-defaults/…` for the packaged photos. Opening a unit previews that theme with this unit and does not write an artifact.

The Default source (slug `default`) is six packaged photos, bound to Spotmu Paper v1, so the required theme has a row to point at. Its paths stay `theme-defaults/…`.

The source stores inspiration and rules as two text fields. Generate drafts the unit's name and text from those. Accept makes that text the live text. Leaving it unreviewed keeps the unit off a run. The call uses OpenAI when `OPENAI_API_KEY` is set (`TEXT_GENERATION_PROVIDER` is `openai` or `fake`; the model defaults to `gpt-4o-mini`) and stays off otherwise. Images are not generated.

A campaign stores the chosen theme and one source bound to that theme. Older rows can have both empty. Run groups the live units into `campaign_carousels` that respect the exclusion rules. It does not call the model and does not draw slides. Those rows are a run's assembly, not the source. Create still asks for platforms and at least one Spotmu interest. A production Spotmu campaign also asks for an account. A Spotmu test campaign does not. Run does not read the interests.

The ops console is signed in. An admin can change rows. A reader can look. The left rail is Content (Campaigns, Themes, Sources), Run (Queue, Schedule, Results), and Setup (Accounts, Users).

An earlier loop still renders a shipping carousel from `carousel_template_v1` off one Spotmu interest. The caption is that interest's title, a fixed hashtag set, and the interest URL. The ops console can approve that draft, set a time, mock-publish, and record a metric by hand. An account can carry a per-day cadence cap. It does not store a login. Publish is a mock adapter. An Ayrshare adapter is in the tree and refuses the live call. Metric rows, a manual entry route, and a cluster median of the latest view counts exist. A stub can copy mock views onto a mock-published job. Clusters, brands, ingest, and steer from that loop are still in the API. The phases below replace that loop for the new model.

---

## 1. Rename to Skeletons, Carousels, and Slides

**Goal.** Use the new names in the database, the API, and the rail, without changing what the rows do.

**Scope.** Themes become Skeletons. Sources become Carousels. Units become Slides. A slide keeps today's shape: a name, an optional image, one text per named text element, the exclusion list, and the draft or live text. Create is still a label plus a skeleton. Preview, exclusions, and generate-from-inspiration keep working under the new names. `campaign_carousels` stays the run assembly. It is not renamed into the new Carousel.

**Migration.** Rename the tables, the routes, and the labels in one revision. A screen-only rename would leave `/api/v1/sources` and `units` under new labels, and the next phases would keep writing the old names.

`themes` and `theme_elements` become `skeletons` and `skeleton_elements`. `sources` becomes `carousels`. `units` becomes `slides`, and the text and exclusion tables move with them. Campaign `theme_id` and `source_id` become `skeleton_id` and `carousel_id`, and they stay optional on older rows. Each existing source becomes one carousel on the skeleton it already uses. The Default source stays a carousel until Albums. Inspiration, rules, and slide images stay put. There is no generation table yet.

**Open questions.** The theme row still has Draft and Live, and the editor does not ask. Does a Skeleton keep that status?

## 2. Albums

**Goal.** A reusable collection of images, on the rail, that more than one carousel can use.

**Scope.** An album is a named set of images. Keep today's upload, URL import, license fields, and thumbnails. Skeleton picture paths stay concrete files. This phase does not build the Content step. It does store which album a carousel's images came from, so the files are not left on the slide with nowhere to live.

**Migration.** Add albums and album images. For each carousel that has slide images, create one album named after the carousel and move the image rows onto it. The carousel points at that album. A slide that had an image keeps a pointer to that album image. Do not copy the bytes. The Default carousel's six packaged photos become an album named Default. Their paths stay `theme-defaults/…`. Other files stay at the paths they already have. A carousel with no images gets no album. Skeleton backgrounds that store a path are left alone.

**Open questions.** Mu will detail albums further. Does the album screen show the license, source, and alt already stored on each image? Today two slides can each hold their own copy of one picture. Should those become one album image?

## 3. Research

**Goal.** A reusable text document a carousel can draw on later.

**Scope.** Minimal. A name and a body of text. Its own rail section. An operator can write and edit it. No upload rules beyond plain text, no synthesis, and no link to a carousel until the Content step.

**Migration.** None. `resource_files` was dropped when sources became theme-bound. Do not recreate it. The API does not use the leftover helpers under `app/sources/resource_files.py`, `resource_store.py`, and `resource_markdown.py`. Remove them here so Research is not that old upload.

**Open questions.** Mu will detail Research. Is one row one document, or can one research item hold several? Is there a size limit?

## 4. Carousel steps and the Content step

**Goal.** Building a carousel is a sequence of steps. Step 2 attaches an album, research, or both.

**Scope.** Step 0 is create: a label and a skeleton. Step 3 is the slide editor that already exists, shown as its own step. Step 2 picks or creates an album, and optionally research. An album is required when the skeleton has a picture background or an image element. Research stays optional even when the skeleton has text. Once an album is selected, further uploads happen on that step. Steps 1 and 4 are on the screen and get their behavior in the next phases. A step can omit guidance. The fallback is a built-in default, such as a slide count drawn at random from 5 to 8. This phase does not add a settings screen for those defaults.

**Migration.** Carousels that received an album in phase 2 already point at it. This phase is the screen, plus an optional research link. Slides that point at an album image still do.

**Open questions.** Where do defaults live, on the Skeleton or in global settings? What is the built-in default for each step besides the slide-count example? Create is supposed to start generation 1. The snapshot table arrives in phase 8. Until then, does the screen say generation 1, or stay quiet?

## 5. Instructions

**Goal.** Step 1 is versioned markdown the model will follow.

**Scope.** One or more markdown documents per carousel, stored in the database, edited with a preview. Thin v1 is the editor, Generate, and review, on the server. Generate uses the provider that already exists: OpenAI when `OPENAI_API_KEY` is set, off otherwise, with `TEXT_GENERATION_PROVIDER` left swappable. This phase does not write slide rows. Per-slide generate from inspiration and rules keeps working until the next phase.

**Migration.** Copy inspiration and rules into one markdown document, version 1, on that carousel. An empty carousel gets an empty first version so the editor has a document. Drop the two columns after the copy.

**Open questions.** What does Generate return before it can write slides: a revised document, or a proposed slide list the next phase saves? Does review accept a version, or only edit the text? When a carousel has several documents, do they run as one prompt or one at a time?

## 6. AI slide generation

**Goal.** Fill slides from the instructions, the album, and research. Hand entry stays.

**Scope.** A slide stays a name, an optional image, and one text per named text element. Generate writes those fields from the current instruction version, the attached album, and research, through the same provider. A person reviews the text before it is live. Images are chosen from the album. They are not drawn. A slide left unreviewed stays off Final, as a draft unit stays off a run today.

**Migration.** Keep the draft and live text gate. Do not mark old draft text live.

**Open questions.** Does review stay on the slide, or move to the instruction run? Do exclusion rules get passed into the model?

## 7. Final assembly

**Goal.** Turn the slides into the carousels an operator reviews, drawn with the skeleton.

**Scope.** Follow the instructions. Where a step has no guidance, use the built-in default. The slide-count example is a random count from 5 to 8. This replaces the campaign run, which only stores slide ids, and it replaces `POST /api/v1/generate/carousel`, which still draws `carousel_template_v1` from one Spotmu interest. The caption stops coming from the interest title. The text on the frame is the reviewed slide text. This phase does not call the model to write new copy. Key the assembled rows so phase 8 can hang them on generation 1 without copying them.

**Migration.** Do not convert old template artifacts into these carousels. They stay on the old queue until the campaign timeline. `campaign_carousels` remains the old assembly until this phase's rows replace it. Leave the old rows readable until phase 9.

**Open questions.** Does each assembled carousel become one draft? Does a draft freeze the slide's image file, or keep a pointer that can change? When the skeleton overlaps or a file is missing, preview marks the frame blocked and still writes a PNG. For a shipping draft, is that a blocked row, or no row? Where do the caption, hashtags, and any link come from? They are not on the slide. Do exclusion rules still split a group? Does Final read the Spotmu interest stored on the campaign?

## 8. Generations

**Goal.** A generation is a snapshot. Duplicate it to try the next version.

**Scope.** The snapshot is the instruction version, the album, the research, and the slides. A new carousel is generation 1. Duplicate copies that snapshot so the next try does not edit the posted one. Performance, once it exists, attaches to the carousels assembled from that snapshot. This phase stores and duplicates. It does not drop losers or add slides from winners.

**Migration.** Backfill generation 1 for every carousel from the instruction version, album, research, and slides it has now. Empty album or research stays empty. Attach the Final rows from phase 7 to that generation.

**Open questions.** After a duplicate, do slide edits land only on the new generation? The album is shared. Does the snapshot store the album id, or the list of images it used at the time? A later upload to that album would change a shared id. It would not change a copied list.

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
