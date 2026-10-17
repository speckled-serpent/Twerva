import assert from "node:assert/strict";

import { CREATE_CAROUSEL_NAME_ERROR } from "./src/pages/createCarousel.ts";
import {
  CAROUSEL_LABEL_ERROR,
  carouselLabelFingerprint,
  carouselLabelReadiness,
} from "./src/pages/carouselLabel.ts";

assert.equal(CAROUSEL_LABEL_ERROR, CREATE_CAROUSEL_NAME_ERROR);

const blankLabel = carouselLabelReadiness({ name: "   " });
assert.equal(blankLabel.kind, "invalid");

if (blankLabel.kind === "invalid") {
  assert.equal(blankLabel.message, CAROUSEL_LABEL_ERROR);
}

assert.equal(carouselLabelReadiness({ name: " Harbor " }).kind, "ready");
assert.equal(carouselLabelFingerprint({ name: " Harbor " }), "Harbor");
assert.equal(
  carouselLabelFingerprint({ name: "Harbor" }),
  carouselLabelFingerprint({ name: " Harbor " }),
);
