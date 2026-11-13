import assert from "node:assert/strict";

import type { CarouselStepState } from "./src/api/types.ts";
import {
  SLIDE_COUNT_DEFAULT_HIGH,
  SLIDE_COUNT_DEFAULT_LOW,
  SLIDE_COUNT_FALLBACK_HINT,
  slideCountFallbackHint,
} from "./src/pages/slideCountFallback.ts";

const openStates: CarouselStepState[] = ["available", "done"];

assert.equal(SLIDE_COUNT_DEFAULT_LOW, 5);
assert.equal(SLIDE_COUNT_DEFAULT_HIGH, 8);
assert.match(SLIDE_COUNT_FALLBACK_HINT, /random value from 5 to 8/);
assert.match(SLIDE_COUNT_FALLBACK_HINT, /global settings/);
assert.match(SLIDE_COUNT_FALLBACK_HINT, /later phase/);
assert.match(SLIDE_COUNT_FALLBACK_HINT, /no guidance/);
assert.equal(slideCountFallbackHint("locked"), null);

for (const slidesState of openStates) {
  assert.equal(slideCountFallbackHint(slidesState), SLIDE_COUNT_FALLBACK_HINT);
}
