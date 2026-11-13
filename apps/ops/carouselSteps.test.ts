import assert from "node:assert/strict";

import type { CarouselStepsResponse } from "./src/api/types.ts";
import {
  CAROUSEL_STEPS,
  CAROUSEL_STEP_FINAL,
  SLIDES_ALBUM_REQUIRED_DETAIL,
  carouselStepByIndex,
  carouselStepLabel,
  generationLabel,
  stepStateFor,
  type CarouselStepDefinition,
} from "./src/pages/carouselSteps.ts";

const doneSlides: CarouselStepsResponse = {
  basic: "done",
  instructions: "done",
  content: "done",
  slides: "done",
  final: "locked",
};

function stepAt(stepIndex: number): CarouselStepDefinition {

  const foundStep: CarouselStepDefinition | null = carouselStepByIndex(stepIndex);

  assert.notEqual(foundStep, null);
  assert.ok(foundStep);

  return foundStep;
}

assert.equal(generationLabel(1), "Generation 1");
assert.equal(CAROUSEL_STEPS.length, 5);
assert.deepEqual(
  CAROUSEL_STEPS.map((step: CarouselStepDefinition): string => carouselStepLabel(step)),
  ["0 Basic", "1 Instructions", "2 Content", "3 Slides", "4 Final"],
);
assert.deepEqual(
  CAROUSEL_STEPS.map((step: CarouselStepDefinition): string => step.label),
  ["Basic", "Instructions", "Content", "Slides", "Final"],
);
assert.equal(carouselStepByIndex(9), null);
assert.equal(SLIDES_ALBUM_REQUIRED_DETAIL, "Attach an album on Content first.");
assert.equal(stepStateFor(doneSlides, stepAt(3)), "done");
assert.equal(stepStateFor(doneSlides, stepAt(CAROUSEL_STEP_FINAL)), "locked");
