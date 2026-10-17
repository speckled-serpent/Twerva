import assert from "node:assert/strict";

import {
  CREATE_CAROUSEL_NAME_ERROR,
  CREATE_CAROUSEL_SKELETON_ERROR,
  createCarouselFieldError,
} from "./src/pages/createCarousel.ts";

assert.equal(createCarouselFieldError("  ", "skeleton-1"), CREATE_CAROUSEL_NAME_ERROR);
assert.equal(createCarouselFieldError("Shelf", ""), CREATE_CAROUSEL_SKELETON_ERROR);
assert.equal(createCarouselFieldError("Shelf", "skeleton-1"), null);
