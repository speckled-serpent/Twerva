import assert from "node:assert/strict";

import { generationLabel } from "./src/pages/carouselSteps.ts";
import {
  DUPLICATE_GENERATION_READER_NAME,
  carouselAfterDuplicate,
  duplicateGenerationAccessibleName,
  duplicateGenerationEnabled,
  duplicateGenerationShown,
  type DuplicateGenerationState,
  type SavedGenerationCarousel,
} from "./src/pages/carouselGeneration.ts";

const savedGeneration: SavedGenerationCarousel = {
  generation_number: 2,
};
const nextState: DuplicateGenerationState<SavedGenerationCarousel> =
  carouselAfterDuplicate(savedGeneration);

assert.equal(duplicateGenerationEnabled(true), true);
assert.equal(duplicateGenerationEnabled(false), false);
assert.equal(
  duplicateGenerationAccessibleName(false, false),
  DUPLICATE_GENERATION_READER_NAME,
);
assert.equal(
  duplicateGenerationAccessibleName(false, false),
  "Duplicate. A reader cannot duplicate a generation.",
);
assert.equal(nextState.carousel.generation_number, 2);
assert.equal(nextState.statusMessage, "Duplicated. This is generation 2.");
assert.equal(duplicateGenerationShown("slide"), false);
assert.equal(duplicateGenerationShown("carousel"), true);
assert.equal(generationLabel(2), "Generation 2");
