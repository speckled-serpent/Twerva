import assert from "node:assert/strict";

import {
  clampStopOffset,
  gradientProblem,
  normalizeHexColor,
  offsetFromPercentInput,
} from "./src/pages/skeletonColors.ts";

assert.equal(normalizeHexColor(""), "");
assert.equal(normalizeHexColor("   "), "");
assert.equal(normalizeHexColor("4a4a4a"), "#4A4A4A");
assert.equal(normalizeHexColor("#4a4a4a"), "#4A4A4A");
assert.equal(normalizeHexColor("abc"), "#AABBCC");
assert.equal(normalizeHexColor("#AbC"), "#AABBCC");
assert.equal(normalizeHexColor("zzzzzz"), "zzzzzz");

assert.equal(
  gradientProblem("180", [{ offset: "0", color: "#112233" }]),
  "Can't draw gradient: add a second color",
);
assert.equal(
  gradientProblem("400", [
    { offset: "0", color: "#112233" },
    { offset: "1", color: "#AABBCC" },
  ]),
  "Angle must be 0-360",
);
assert.equal(
  gradientProblem("180", [
    { offset: "0", color: "#112233" },
    { offset: "1.5", color: "#AABBCC" },
  ]),
  "Stop offsets must be between 0% and 100%",
);
assert.equal(
  gradientProblem("180", [
    { offset: "0", color: "#112233" },
    { offset: "1", color: "not-a-color" },
  ]),
  "Stop 2 color isn't a valid hex color",
);
assert.equal(
  gradientProblem("180", [
    { offset: "0", color: "4a4a4a" },
    { offset: "1", color: "bdbdbd" },
  ]),
  null,
);

assert.equal(clampStopOffset([0, 0.4], 0, 0.9), 0.4);
assert.equal(clampStopOffset([0.2, 1], 1, 0), 0.2);
assert.equal(clampStopOffset([0, 0.5, 1], 1, 0.1), 0.1);
assert.equal(
  offsetFromPercentInput([0, 1], 0, "40"),
  "0.4",
);
assert.equal(
  offsetFromPercentInput([0.25, 1], 1, "10"),
  "0.25",
);
assert.equal(
  offsetFromPercentInput([0, 1], 1, "150"),
  "1.5",
);
