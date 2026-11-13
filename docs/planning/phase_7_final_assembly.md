## 7. Final assembly

**Status.** Checklist. Head revision on main is `slide_draft_batches`. Implement in the order below. Each box is one commit, and the console still works after that commit. Each box names the tests that land with it. Task 7.8 runs the full suites and `npm run build`.

**Goal.** Turn the slides into the carousels an operator reviews, drawn with the skeleton.

**What the code does today.** Final is the last heading on the one-page editor, `#carousel-final` in `CarouselsPage`. `finalSectionNotice` in `apps/ops/src/pages/carouselPage.ts` returns `FINAL_CLOSED_DETAIL` ("Final assembly is a later phase."). `CarouselSectionNav` only scrolls to that heading. The page does not switch steps and does not hide a section. `editor_step` is not what chooses the panel, and step 4 is not stored. `carousel_step_states` in `app/carousels/slide_skeleton.py` sets `final` to `locked`. `accepted_editor_step` rejects 4 with `FINAL_LOCKED_DETAIL` ("Final is locked.") before it checks `STORED_EDITOR_STEPS`. `PATCH /api/v1/carousels/{carousel_id}/step` with 4 is 400.

A slide is live when `live_slides` in `app/carousels/slide_text_review.py` says so: `text_status` `live`. Live copy is `slide_element_texts.value`. `draft_value` is the unaccepted draft. `CarouselReadResponse.live_slide_count` counts live slides only. A pending `slide_draft_batches` row stays off Final. The Slides review copy already says the set stays off Final until it is accepted. Hand-entered slides are stored `live`. The done mark on Slides is two slides, `CAROUSEL_SLIDES_DONE_COUNT`. That count is not the group size.

`POST /api/v1/campaigns/{campaign_id}/run` (`run_campaign`) replaces `campaign_carousels` through `_replace_campaign_carousels`. It sorts `live_slides` by `(position, id)`, passes both directions of `slide_exclusions`, and calls `assemble_carousels` in `app/campaigns/assemble.py`. That function packs each slide into the first group that `assert_slide_pick_allowed` accepts. It has no size cap. The stored rows are slide ids and positions. They are not drawn.

`POST /api/v1/generate/carousel` (`generate_carousel_artifact`) still calls `generate_carousel_artifact_draft`. That draws `carousel_template_v1` from one Spotmu `SourceItem` through `render_carousel_from_source_fields` and `plan_carousel_slides`. The caption is `build_carousel_caption`: the interest title, the heading, the interest URL, and `DEFAULT_HASHTAGS`. The PNG path is `{artifact_id}/{slide_index}_{role}.png` from `write_artifact_slide_png_bytes`. Those rows are `artifacts` with `status` `draft`. Queue, Schedule, Results, approve, and schedule still read them.

The skeleton frame is a different drawer. `render_skeleton_sample` in `app/skeletons/samples.py` draws 1080×1920 (`SKELETON_FRAME_WIDTH_PIXELS`, `SKELETON_FRAME_HEIGHT_PIXELS`). `POST /api/v1/carousels/{carousel_id}/slides/preview` calls it with a `SlideSkeletonFill` and writes no row. `source_item` is ignored when `slide_fill` is set. Overlap, a missing file, and a measure error set `blocked` and still return PNG bytes. `SkeletonSampleBlockReason` is `overlap`, `missing_asset`, or `measure_error`. The preview route's saved image path is `slide.album_image.relative_path` (`Slide.images` returns that one album image).

Publish reads artifact files, not carousel slides. `publish_post_job` resolves `artifacts.slides[].asset_ref` with `resolve_artifact_slide_media_paths` and passes those paths to the adapter. `MockPublishAdapter` returns `mock-{platform}-{post_job.id}` and does not open the network. `AyrsharePublishAdapter` still refuses the live call. `PUBLISH_ADAPTER` defaults to `mock`.

`slide_count_or_global_default(None)` in `app/global_settings.py` draws one integer from 5 to 8 (`SLIDE_COUNT_DEFAULT_LOW`, `SLIDE_COUNT_DEFAULT_HIGH`). Nothing on the carousel stores a count. Instruction Markdown is not parsed for one. `generation_number` on the carousel is 1. There is no generations table. There is no assembly table.

**Settled for this phase.** The tasks use these. The open decisions at the end are the choices Mu can still change.

- Assembly reads the carousel's live slides and draws each frame with `render_skeleton_sample`. The text on the frame is `value`. This phase does not call `draft_slide_text`, `draft_slide_collection`, or `render_carousel_from_source_fields`.
- Hand entry is enough. A carousel with no instruction documents still assembles when it has two live slides. Draft slides, including a pending set, are left out.
- The new rows are not `artifacts` and not `campaign_carousels`. The old generate route, the campaign run, and `MockPublishAdapter` stay. Old template artifacts stay on Queue. Phase 9 is what folds that queue in.
- One `carousel_assemblies` row per carousel and `generation_number`. Re-assemble keeps that row id and replaces its children, so phase 8 can hang the row on generation 1 without copying frames. This phase does not add a generations table.
- `editor_step` 4 stays unstored. The page stays one scroll.

### Data model

- [x] **7.1 Add the assembly tables**

  Alembic revision `carousel_final_assembly`, down-revision `slide_draft_batches`. Three tables. Upgrade inserts no rows and does not update `artifacts`, `campaign_carousels`, slides, or `generation_number`. Downgrade drops them in child-to-parent order and leaves any PNG files on disk.

  `carousel_assemblies`: `id`, `carousel_id` (cascade on carousel delete), `generation_number` (integer, not null, check `generation_number >= 1`), `slide_count` (integer, not null, check `slide_count >= 1`), and the timestamp columns from `TimestampMixin`. Unique `(carousel_id, generation_number)`. This is the row phase 8 attaches. It is not a generation snapshot.

  `assembled_carousels`: `id`, `assembly_id` (cascade on assembly delete), `position` (check `position >= 0`), `status` (text, not null, check `status = 'draft'`), `caption` (text, null), `cta_url` (text, null), and `TimestampMixin`. Unique `(assembly_id, position)`. No hashtag column. One row is one carousel the operator reviews.

  `assembled_carousel_frames`: `id`, `assembled_carousel_id` (cascade), `position` (check `position >= 0`), `slide_id` (nullable UUID, foreign key to `slides.id`, `ON DELETE SET NULL`), `album_image_id` (nullable UUID, foreign key to `album_images.id`, `ON DELETE SET NULL`), `asset_ref` (text, not null), `blocked` (boolean, not null), `block_reason` (text, null, check null or in `overlap`, `missing_asset`, `measure_error`), `block_detail` (text, null), and `TimestampMixin`. Unique `(assembled_carousel_id, position)`. The PNG path is the frozen frame. Deleting the slide or the album image clears the pointer and leaves the row.

  `CarouselAssembly`, `AssembledCarousel`, and `AssembledCarouselFrame` live in `app/models/carousel.py` next to `SlideDraftBatch`, exported from `app/models/__init__.py`. `Carousel.assemblies` is the relationship. This revision does not widen `ck_carousels_editor_step`.

  Acceptance: upgrade, downgrade, upgrade again. Default still has six live slides, generation 1, and no assembly row. A second assembly for the same carousel and generation fails the unique constraint. A frame can be stored with `blocked` true and `block_reason` `missing_asset`. `campaign_carousels` and `artifacts` still read back. Tests live in `apps/server/tests/test_carousel_final_assembly_migration.py`, on the pattern of `test_slide_draft_batches_migration.py` (skip when Postgres is down).

### Grouping

- [x] **7.2 Group live slides under a size cap**

  Add `plan_final_groups` in `app/carousels/final_assembly.py`. It takes live slide ids in the order the caller gives, exclusion pairs as `(slide_id, excluded_slide_id)`, and `slide_count` (the cap, already chosen, at least 1). It does not read the database, does not draw, and does not parse instruction text.

  Walk the ids in order. A slide joins the first group that has fewer than `slide_count` slides and that `assert_slide_pick_allowed` accepts with this slide added. Otherwise it starts the next group. A slide alone is always one group. Both directions of a pair may be present. Do not change `assemble_carousels`. The campaign run keeps packing with no cap.

  Acceptance, in `apps/server/tests/test_final_assembly.py`: six ids and a cap of 5, with no exclusions, return a group of five and a group of one, in the given order. Three ids and a cap of 8 return one group of three. A cap of 1 returns one group per id. With A excluding B and a cap of 8, the order A, B, C returns `[A, C]` and `[B]`. An empty list returns no groups. A direct call to `assemble_carousels` with six ids and no exclusions still returns one group.

### Render

- [x] **7.3 Draw one live slide with the skeleton**

  Add `slide_fill_from_live_slide` and `render_assembled_frame` in `app/carousels/final_render.py`. The fill uses each `slide_element_texts.value` keyed by `skeleton_element_id`. It does not read `draft_value`. The image path is `slide.album_image.relative_path` when the album image is set, and null when it is not. `render_assembled_frame` calls `render_skeleton_sample` with that fill and `source_item` None, so a Spotmu interest is not drawn. The canvas stays 1080×1920 from the skeleton drawer.

  The relative path is `assembled/{assembly_id}/{frame_id}.png` under `ARTIFACT_STORAGE_DIR`, from `assembled_frame_relative_path`. Write the PNG bytes `render_skeleton_sample` returns, including when `blocked` is true. Use `resolve_asset_reference_path` so the path cannot leave the store. Do not call `write_artifact_slide_png_bytes`, `render_carousel_from_source_fields`, `plan_carousel_slides`, or `build_carousel_caption`. This function does not insert a row.

  Acceptance, in `apps/server/tests/test_final_render.py`: the fill helper keeps a live value of `Reviewed line` and ignores a different `draft_value`. A color skeleton with that fill writes a PNG file whose bytes start with the PNG signature, and `blocked` is false. A picture skeleton whose image path is not on disk writes the PNG, sets `blocked` true, and sets `block_reason` to `missing_asset`. An overlap that `render_skeleton_sample` already reports as `overlap` is returned the same way, and the file is still written. The test does not create an `artifacts` row.

### API

- [ ] **7.4 Assemble the live slides and store the rows**

  `POST /api/v1/carousels/{carousel_id}/assemble`, empty body, admin only, same as `generate_source_slide`. Register it from `register_carousel_assembly_routes` in `app/api/v1/carousel_assembly.py`, called next to `register_source_preview_routes` in `app/api/v1/carousels.py`. The response is `serialize_carousel`. The write helper is `assemble_carousel_final` in `app/carousels/final_assembly.py`.

  Load live slides with `live_slides`, sorted by `(position, id)`, the same order `_replace_campaign_carousels` uses. Fewer than two live slides returns 400, detail `Add at least two live slides before assembly.`, and writes nothing. Draft slides do not count. A pending batch is not an error and is not assembled. The cap is one call to `slide_count_or_global_default(None)`. HTTP tests patch that helper to a fixed integer. Groups come from `plan_final_groups`. Each frame is `render_assembled_frame`. `caption` on every assembled carousel is the carousel name. `cta_url` is null. `status` is `draft`. `generation_number` and the stored `slide_count` are copied onto the assembly row.

  The first assemble inserts one `carousel_assemblies` row. A later assemble for the same carousel and generation keeps that row id, deletes the previous frame files by their `asset_ref`, deletes the child rows, and writes the new groups. One commit. A failure rolls the rows back and does not leave the new PNGs behind. Deleting a slide or an album image does not delete the assembly. The pointers set themselves null. The next assemble rebuilds from the slides that remain.

  The helper does not read instruction bodies, research, or `campaign_interests`. It does not call a text provider. It does not call `generate_carousel_artifact_draft`, `_replace_campaign_carousels`, or `publish_post_job`. It does not write `artifacts`, `post_jobs`, or `campaign_carousels`.

  `CarouselReadResponse` gains `assembly`: null, or `{id, generation_number, slide_count, carousels}`. Each carousel is `{id, position, status, caption, cta_url, blocked, frames}`. `blocked` on the carousel is true when any frame is blocked. A frame is `{id, position, slide_id, album_image_id, blocked, block_reason, block_detail}`. `serialize_carousel` fills it. The list item stays without it. Load the assembly chain with `selectinload` next to the slide loads in `app/api/v1/carousels.py`. Add the assemble path to `EXPECTED_API_V1_PATHS` in `apps/server/tests/test_api_routes.py`.

  Acceptance, in `apps/server/tests/test_carousel_assembly.py`: six live slides and a patched cap of 5 store two `draft` carousels, positions 0 and 1, with five frames and one frame, captions equal to the carousel name, and null `cta_url`. Each frame's `asset_ref` is an `assembled/…` PNG. A draft slide on the same carousel is not a frame, and its pending batch stays pending. A second POST keeps the same assembly id, replaces the frames, and leaves one assembly row. One live slide is 400 and stores nothing. An `artifacts` count, a `campaign_carousels` count, and a `post_jobs` count are unchanged. A reader is rejected. Default, with six live slides, assembles when an admin calls it. The detail's `live_slide_count` stays six.

- [ ] **7.5 Serve the frozen frame**

  `GET /api/v1/carousels/{carousel_id}/assembly/frames/{frame_id}/file` returns the PNG. Authenticated operators, including a reader, the same way `preview_slide_on_skeleton` allows a reader. A frame that is not on this carousel is 404. Resolve `asset_ref` with `resolve_asset_reference_path`. A missing file is 404. A path that escapes the store is 404 and the file is not opened. The route does not draw again and does not read the album file. Register it on the same assembly router. Add the path to `EXPECTED_API_V1_PATHS`.

  Acceptance, in `test_carousel_assembly.py`: after assemble, a reader can GET the first frame and the body starts with the PNG signature. An unknown frame id is 404. The album file route still returns the album image. `POST /api/v1/generate/carousel` is still registered.

### Step state

- [ ] **7.6 Mark Final from the assembly**

  `carousel_step_states` gains `live_slide_count` and `has_final_assembly`, appended after `has_instruction_text`. The existing `slide_count` argument stays the count of every slide, which is what marks Slides done. The caller sets `has_final_assembly` when an assembly row exists for this carousel's `generation_number`. `final` is `locked` when `live_slide_count` is under two, `available` when there are at least two live slides and no assembly, and `done` when the assembly exists. A pending draft set does not make Final done. `basic`, `instructions`, `content`, and `slides` stay on their current rules. `serialize_carousel` and `_accepted_editor_step` in `app/api/v1/carousel_writes.py` pass the new arguments. `STORED_EDITOR_STEPS` stays 0, 1, 2, and 3.

  `accepted_editor_step` rejects 4 before it looks at the derived state, including when `final` is `available` or `done`, because Final is not a stored step. The detail stays `FINAL_LOCKED_DETAIL`. `PATCH .../step` with 4 stays 400 and the stored step stays. Create still stores step 0.

  Update the tests that require `final` to be locked on every carousel: `test_carousel_step_state.py`, `test_carousel_editor_step.py`, `test_carousel_album_link.py`, `test_carousel_research_link.py`, and `test_carousels.py`. A carousel with fewer than two live slides still reads `final: locked`.

  Acceptance: two live slides and no assembly read `final: available`. After assemble, the same carousel reads `final: done`. One live slide reads `final: locked`, and a 400 from assemble leaves it locked. Step 4 is 400. A picture carousel with no album still refuses step 3.

### Page

- [ ] **7.7 Show the assembly on Final**

  Replace the later-phase sentence in the Final section. `CarouselFinalSection` renders under `#carousel-final`. Empty copy, when `assembly` is null: `No assembly yet. Assemble draws the live slides with this skeleton.` The button is `#assemble-final`, label `Assemble`. It calls `assembleCarousel` in `apps/ops/src/api/client.ts`, `POST /api/v1/carousels/{carouselId}/assemble`, returning the carousel detail. Success replaces the open carousel. The status line is `Assembled {n} carousels.` A 400 shows the API detail in `ErrorBanner`. While the request runs, the label is `Assembling…` and the button is disabled.

  Enablement is `finalAssembleEnabled` in `apps/ops/src/pages/finalAssembly.ts`. The button is enabled for an admin when `live_slide_count` is at least two. A reader stays disabled. The disabled accessible name is `Assemble. Add at least two live slides first.` when fewer than two slides are live. Add `assembly` on `CarouselReadResponse` in `apps/ops/src/api/types.ts`. The frame image URL is `assembledFrameFileUrl`, the file route from task 7.5.

  When `assembly` is set, list the groups in position order as Carousel 1, Carousel 2, from `position + 1`. Each group shows its caption and, in frame order, the PNG. A blocked frame shows `block_detail` under that image. The section does not show hashtags or a link. It does not link to Queue, Schedule, or Results. It does not call `generateCarouselArtifact` or a publish route. `CarouselSectionNav` still only scrolls. `live_slide_count` in `carouselPageLede` is unchanged. The Slides review sentence stays.

  Delete the Final use of `FINAL_CLOSED_DETAIL`. Update `carouselPage.test.ts` and `carouselCollection.test.ts`, which assert that sentence from `finalSectionNotice`. `carouselSteps.test.ts` drops the constant if nothing else reads it.

  Acceptance, in `apps/ops/finalAssembly.test.ts`: an admin with two live slides is enabled, a reader is disabled, and one live slide is disabled. After a successful assemble the helper's next state has two groups when the response does. The empty sentence is the one above. The later-phase sentence is gone from the section.

### Tests

- [ ] **7.8 Run the full server suite, the full ops suite, and the ops build**

  From `apps/server`, `python -m unittest discover -s tests`. From `apps/ops`, `node --test *.test.ts`, then `npm run build`. This commit adds no product behavior. It fixes failures that this phase's tasks left, and it does not start a new feature. Migration tests that skip because Postgres is down stay skipped, the same way `test_carousel_steps_migration.py` skips. A skip is not a failure. The phase is done when both suites pass aside from those skips, and `npm run build` succeeds.

### Open decisions

These are the questions section 7 leaves open. The tasks above use the recommended default so a commit can name a file.

1. **How assembly follows the instructions.** The scope says to follow the instructions, and to use the built-in default where a step has no guidance. The slide-count example is a random count from 5 to 8. Instruction Markdown has no count field, and phase 6 does not parse one. Recommended default: do not parse the documents and do not call the model. Draw one cap with `slide_count_or_global_default(None)`, store it on `carousel_assemblies.slide_count`, and draw the live `value` strings. A carousel someone typed, with no instruction rows, still assembles. Say if a number in the Markdown should win, or if the model should group the slides.
2. **What "replaces" means for the old routes.** The scope says this replaces the campaign run and `POST /api/v1/generate/carousel`. The migration says not to convert old template artifacts, to leave `campaign_carousels` readable until phase 9, and to leave those artifacts on the old queue until the campaign timeline. Recommended default: add the new tables and leave both routes, their rows, and `MockPublishAdapter` as they are. Final does not publish. Say if this phase should stop the run, or stop the template generate route, or start sending assembled PNGs through the mock adapter.
3. **Whether each assembled carousel is one draft.** Recommended default: yes. One `assembled_carousels` row with `status` `draft`. It is not an `artifacts` row, so it does not show up on Queue. This phase does not add approve, schedule, or a status besides `draft`. Say if it should be an `artifacts` draft instead, or if the row should have no status until phase 9.
4. **Whether a draft freezes the image.** Recommended default: freeze the rendered frame. Write the PNG under `assembled/{assembly_id}/{frame_id}.png` at assemble time. Store `slide_id` and `album_image_id` as pointers that set null when the source row is deleted. Do not copy the album file. A later edit to the album bytes does not change the PNG. The next Assemble writes new files. Say if Final should keep only the pointers and draw again on each view.
5. **A blocked frame.** Preview sets `blocked` and still returns a PNG when the skeleton overlaps, a file is missing, or measure fails. Recommended default: write the frame row and the PNG, with `blocked` true and `block_reason` set. The assembled carousel stays `draft`. The group is `blocked` when any frame is. This phase does not ship it. Say if a blocked frame should drop the group, or should fail the whole assemble with nothing written.
6. **Caption, hashtags, and the link.** They are not on the slide. The old caption is the interest title plus `DEFAULT_HASHTAGS` and the interest URL. Recommended default: copy the carousel name into `caption` on each assembled carousel. Leave `cta_url` null. Add no hashtag column and do not append hashtags to the caption. Final shows the caption and does not edit it. Say if the caption should stay empty, or if it should be the campaign hashtag and a link the operator types.
7. **Exclusion rules.** Recommended default: they still split a group. `plan_final_groups` uses `assert_slide_pick_allowed`, and a slide also starts a new group when the current one is at the cap. `assemble_carousels` is unchanged, so the campaign run does not gain a cap. Say if Final should pack every live slide into one carousel and ignore exclusions, or if the cap should not apply.
8. **The Spotmu interest on the campaign.** Recommended default: Final does not read it. Assemble takes the carousel id. `render_skeleton_sample` gets `source_item` None and the live slide fill. A carousel that is on no campaign still assembles. Say if the frame text or the caption should come from `campaign_interests`.
