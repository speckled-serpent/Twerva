# Source Redesign: Theme-Bound Sources

## Why

Matching and content decisions move to source-creation time, so the output becomes predictable. On-the-fly generation at campaign time was rejected because it publishes unreviewed output.

- Keep the term "sources". The album / content / resource naming debate is dropped.
- Drop the album-versus-resource distinction. Every source is one thing.
- Create source asks only for a name and a required theme. There is no algorithmic theme-source matching at the campaign layer.
- Old sources that do not fit the new structure can be deleted.
- Opening a source shows units that follow the selected theme: an image field only if the theme requires an image, plus one text input per theme text element.
- One image per unit. To test text variants on the same image, add more units that reuse it.
- Each unit gets an ID/name.
- Per-unit exclusion rules: a unit declares other unit IDs it cannot be shown with, so random carousel picks never repeat the same story/image pairing.
- Optional theme enhancement, not required now: word-count limits or warnings on text elements, leaning toward a warning rather than a hard block.
- In-source preview while developing.
- Generation: images are uploaded manually. Text comes from an LLM using inspiration and rules inside the source, and is reviewed before it goes live.
- Campaign flow: pick a theme first, then a dropdown of matching sources, pick one, and run. The campaign assembles already-reviewed content.

## Phase plan

Each phase can ship and be reviewed on its own. Later phases assume the earlier ones are in place. Starting point in the code: a source is an album (units with free text, labeled fields, tags, and many images) or a resource (one `.md` or `.txt` file); a unit already has a UUID and has no name; themes store a concrete image path, and text elements use a Spotmu text source; theme pickers list albums and store one path; a campaign stores a definition and has no theme or source.

### 1. Model change

**Status.** Done.

**Scope.** A source requires a theme. Create asks for a name and that theme. Album and resource become one kind of source. A unit keeps its existing id and gains a name. A unit holds one image; further units can reuse that image when the operator wants text variants. Theme pickers list these sources and still store one concrete image path. Sources that cannot take this shape are removed: resource sources, and album sources left without a theme. When a theme or artifact still stores an image path from that source, deletion keeps the current in-use refusal until that path is cleared.

**Out of scope.** The theme-shaped text inputs, in-source preview, exclusion rules, LLM text, the campaign theme-and-source run, and word-count warnings.

**Done when.** Create source is a name plus a required theme. Album and resource are gone from the API and the ops lists. Each unit has an id and a name and at most one image. A source cannot be saved without a theme. Resource sources are gone, and album sources without a theme are gone once nothing still stores their image paths.

**Migration.** Yes. `sources` gains a required theme foreign key. `kind` and `resource_files` are removed. `units` gains a name. A unit is limited to one image row. The migration deletes resource rows, and deletes album rows that have no theme once their image paths are no longer stored on a theme or artifact.

### 2. Theme-shaped unit editor and in-source preview

**Status.** Done.

**Scope.** Opening a source shows units that follow its theme. The image field is shown when the theme requires an image (an image element, or a picture background). There is one text input per theme text element. Preview, while the operator is editing, renders that theme with this unit's image and text. Theme samples already preview a theme without creating an artifact; this preview is that same kind of frame, filled from the unit.

**Out of scope.** Exclusion rules, LLM generation, the campaign run, and word-count warnings. Images stay a manual upload.

**Done when.** The unit form matches the source's theme: an image field only when the theme requires one, and one text field per text element. Saving stores those values on the unit. Preview shows the theme with this unit and does not write a campaign artifact.

**Migration.** Yes. A unit today stores one `free_text` plus labeled fields and tags. This phase stores one text value per theme text element on the unit, in place of that free text, those labels, and those tags.

### 3. Exclusion rules

**Status.** Done.

**Scope.** A unit declares other unit ids in the same source that it cannot be shown with, so a random carousel pick does not repeat the same story/image pairing. Units that reuse one image for text variants can exclude each other.

**Out of scope.** LLM text, the campaign theme, source, and run screens, and word-count warnings.

**Done when.** An operator can save the excluded unit ids on a unit. A pick that includes an excluded pair is refused. A pick of units that do not exclude each other is allowed.

**Migration.** Yes. Exclusion pairs are new. This phase stores, on the unit, the other unit ids it cannot be shown with.

### 4. LLM text inside the source

**Scope.** Images stay manual uploads. The source holds inspiration and rules. An LLM writes the unit's theme text from those. A person reviews that text before it is the live text on the unit.

**Out of scope.** Campaign assembly, and word-count warnings. The redesign does not name which model runs the call.

**Done when.** Inspiration and rules can be saved on the source. Generating fills the unit's text inputs. Accepting makes that text live. Leaving it unreviewed keeps it off the live unit. Images are still uploaded by hand.

**Migration.** Yes. Inspiration and rules are new columns or rows on the source. Review state is new on the generated text.

### 5. Campaign flow

**Scope.** The operator picks a theme, then one source from the dropdown of sources bound to that theme, then runs. The run assembles units whose text is already reviewed, and it respects exclusion rules. Matching is the theme stored on the source. The run does not call the LLM.

**Out of scope.** Word-count warnings, queue and schedule, account connection, and measurement. Those stay on `docs/planning/phase_map.md` after this plan.

**Done when.** The campaign stores the chosen theme and the chosen source. The source dropdown lists sources with that theme. Run builds the post from reviewed units in that source and leaves unreviewed units out. Run does not generate text.

**Migration.** Yes. `campaigns` gains the chosen theme and the chosen source. It has neither foreign key today.

### Later

**Word-count warnings on theme text elements.** Optional, and outside the five phases. A theme text element warns when the unit text runs long. The lean is a warning. **Migration.** No. The warning is computed while editing. A stored limit is not part of this note.
