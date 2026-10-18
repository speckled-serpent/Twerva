import assert from "node:assert/strict";

import type { CarouselStepState } from "./src/api/types.ts";
import {
  CAROUSEL_STEP_BASIC,
  CAROUSEL_STEP_CONTENT,
  CAROUSEL_STEP_FINAL,
  CAROUSEL_STEP_INSTRUCTIONS,
  CAROUSEL_STEP_SLIDES,
} from "./src/pages/carouselSteps.ts";
import {
  SLIDE_COUNT_DEFAULT_HIGH,
  SLIDE_COUNT_DEFAULT_LOW,
  SLIDE_COUNT_FALLBACK_HINT,
  slideCountFallbackHint,
} from "./src/pages/slideCountFallback.ts";

const slideStates: CarouselStepState[] = ["locked", "available", "done"];
const otherSteps: number[] = [
  CAROUSEL_STEP_BASIC,
  CAROUSEL_STEP_INSTRUCTIONS,
  CAROUSEL_STEP_CONTENT,
  CAROUSEL_STEP_FINAL,
];

assert.equal(SLIDE_COUNT_DEFAULT_LOW, 5);
assert.equal(SLIDE_COUNT_DEFAULT_HIGH, 8);
assert.match(SLIDE_COUNT_FALLBACK_HINT, /random value from 5 to 8/);
assert.match(SLIDE_COUNT_FALLBACK_HINT, /global settings/);
assert.match(SLIDE_COUNT_FALLBACK_HINT, /later phase/);
assert.match(SLIDE_COUNT_FALLBACK_HINT, /no guidance/);
assert.equal(
  slideCountFallbackHint(CAROUSEL_STEP_SLIDES, "available"),
  SLIDE_COUNT_FALLBACK_HINT,
);
assert.equal(
  slideCountFallbackHint(CAROUSEL_STEP_SLIDES, "done"),
  SLIDE_COUNT_FALLBACK_HINT,
);
assert.equal(slideCountFallbackHint(CAROUSEL_STEP_SLIDES, "locked"), null);

for (const editorStep of otherSteps) {

  for (const slidesState of slideStates) {
    assert.equal(slideCountFallbackHint(editorStep, slidesState), null);
  }
}
