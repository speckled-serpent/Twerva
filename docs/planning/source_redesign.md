# Carousel Redesign: Skeleton-Bound Carousels

## Why

Matching and content decisions move to carousel-creation time, so the output becomes predictable. On-the-fly generation at campaign time was rejected because it publishes unreviewed output.

- Keep the term "carousels". The album / content / resource naming debate is dropped.
- Drop the album-versus-resource distinction. Every carousel is one thing.
- Create carousel asks only for a name and a required skeleton. There is no algorithmic skeleton-carousel matching at the campaign layer.
- Old carousels that do not fit the new structure can be deleted.
- Opening a carousel shows slides that follow the selected skeleton: an image field only if the skeleton requires an image, plus one text input per skeleton text element.
- One image per slide. To test text variants on the same image, add more slides that reuse it.
- Each slide gets an ID/name.
- Per-slide exclusion rules: a slide declares other slide IDs it cannot be shown with, so random carousel picks never repeat the same story/image pairing.
- Optional skeleton enhancement, not required now: word-count limits or warnings on text elements, leaning toward a warning rather than a hard block.
- In-carousel preview while developing.
- Generation: images are uploaded manually. Text comes from an LLM using inspiration and rules inside the carousel, and is reviewed before it goes live.
- Campaign flow: pick a skeleton first, then a dropdown of matching carousels, pick one, and run. The campaign assembles already-reviewed content.

## Phase plan

Each phase can ship and be reviewed on its own. Later phases assume the earlier ones are in place. Starting point in the code: a carousel is an album (slides with free text, labeled fields, tags, and many images) or a resource (one `.md` or `.txt` file); a slide already has a UUID and has no name; skeletons store a concrete image path, and text elements use a Spotmu text source; skeleton pickers list albums and store one path; a campaign stores a definition and has no skeleton or carousel.

### 1. Model change

**Status.** Done.

**Scope.** A carousel requires a skeleton. Create asks for a name and that skeleton. Album and resource become one kind of carousel. A slide keeps its existing id and gains a name. A slide holds one image; further slides can reuse that image when the operator wants text variants. Skeleton pickers list these carousels and still store one concrete image path. Carousels that cannot take this shape are removed: resource carousels, and album carousels left without a skeleton. When a skeleton or artifact still stores an image path from that carousel, deletion keeps the current in-use refusal until that path is cleared.

**Out of scope.** The skeleton-shaped text inputs, in-carousel preview, exclusion rules, LLM text, the campaign skeleton-and-carousel run, and word-count warnings.

**Done when.** Create carousel is a name plus a required skeleton. Album and resource are gone from the API and the ops lists. Each slide has an id and a name and at most one image. A carousel cannot be saved without a skeleton. Resource carousels are gone, and album carousels without a skeleton are gone once nothing still stores their image paths.

**Migration.** Yes. `carousels` gains a required skeleton foreign key. `kind` and `resource_files` are removed. `slides` gains a name. A slide is limited to one image row. The migration deletes resource rows, and deletes album rows that have no skeleton once their image paths are no longer stored on a skeleton or artifact.

### 2. Skeleton-shaped slide editor and in-carousel preview

**Status.** Done.

**Scope.** Opening a carousel shows slides that follow its skeleton. The image field is shown when the skeleton requires an image (an image element, or a picture background). There is one text input per skeleton text element. Preview, while the operator is editing, renders that skeleton with this slide's image and text. Skeleton samples already preview a skeleton without creating an artifact; this preview is that same kind of frame, filled from the slide.

**Out of scope.** Exclusion rules, LLM generation, the campaign run, and word-count warnings. Images stay a manual upload.

**Done when.** The slide form matches the carousel's skeleton: an image field only when the skeleton requires one, and one text field per text element. Saving stores those values on the slide. Preview shows the skeleton with this slide and does not write a campaign artifact.

**Migration.** Yes. A slide today stores one `free_text` plus labeled fields and tags. This phase stores one text value per skeleton text element on the slide, in place of that free text, those labels, and those tags.

### 3. Exclusion rules

**Status.** Done.

**Scope.** A slide declares other slide ids in the same carousel that it cannot be shown with, so a random carousel pick does not repeat the same story/image pairing. Slides that reuse one image for text variants can exclude each other.

**Out of scope.** LLM text, the campaign skeleton, carousel, and run screens, and word-count warnings.

**Done when.** An operator can save the excluded slide ids on a slide. A pick that includes an excluded pair is refused. A pick of slides that do not exclude each other is allowed.

**Migration.** Yes. Exclusion pairs are new. This phase stores, on the slide, the other slide ids it cannot be shown with.

### 4. LLM text inside the carousel

**Status.** Done.

**Scope.** Images stay manual uploads. The carousel holds inspiration and rules. An LLM writes the slide's skeleton text from those. A person reviews that text before it is the live text on the slide.

**Out of scope.** Campaign assembly, and word-count warnings. The redesign does not name which model runs the call.

**Done when.** Inspiration and rules can be saved on the carousel. Generating fills the slide's text inputs. Accepting makes that text live. Leaving it unreviewed keeps it off the live slide. Images are still uploaded by hand.

**Migration.** Yes. Inspiration and rules are new columns or rows on the carousel. Review state is new on the generated text.

### 5. Campaign flow

**Status.** Done.

**Scope.** The operator picks a skeleton, then one carousel from the dropdown of carousels bound to that skeleton, then runs. The run assembles slides whose text is already reviewed, and it respects exclusion rules. Matching is the skeleton stored on the carousel. The run does not call the LLM.

**Out of scope.** Word-count warnings, queue and schedule, account connection, and measurement. Those stay on `docs/planning/phase_map.md` after this plan.

**Done when.** The campaign stores the chosen skeleton and the chosen carousel. The carousel dropdown lists carousels with that skeleton. Run builds the post from reviewed slides in that carousel and leaves unreviewed slides out. Run does not generate text.

**Migration.** Yes. `campaigns` gains the chosen skeleton and the chosen carousel. It has neither foreign key today.

### Later

**Word-count warnings on skeleton text elements.** Optional, and outside the five phases. A skeleton text element warns when the slide text runs long. The lean is a warning. **Migration.** No. The warning is computed while editing. A stored limit is not part of this note.
