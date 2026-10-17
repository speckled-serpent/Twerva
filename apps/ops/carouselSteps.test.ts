import assert from "node:assert/strict";

import type { CarouselStepState, CarouselStepsResponse } from "./src/api/types.ts";
import {
  CAROUSEL_STEPS,
  CAROUSEL_STEP_SLIDES,
  canOpenCarouselStep,
  carouselStepAccessibleName,
  carouselStepByIndex,
  carouselStepLabel,
  generationLabel,
  openStepSentence,
  stepClickStoresEditorStep,
  stepStateFor,
  type CarouselStepDefinition,
} from "./src/pages/carouselSteps.ts";

const doneSlides: CarouselStepsResponse = {
  basic: "done",
  instructions: "locked",
  content: "done",
  slides: "done",
  final: "locked",
};

const availableSlides: CarouselStepsResponse = {
  basic: "done",
  instructions: "locked",
  content: "done",
  slides: "available",
  final: "locked",
};

const lockedSlides: CarouselStepsResponse = {
  basic: "done",
  instructions: "locked",
  content: "available",
  slides: "locked",
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
assert.equal(openStepSentence(CAROUSEL_STEP_SLIDES), "This carousel opens on Slides.");
assert.equal(openStepSentence(0), "This carousel opens on Basic.");
assert.equal(carouselStepAccessibleName(stepAt(1), "locked"), "1 Instructions, locked");
assert.equal(carouselStepAccessibleName(stepAt(3), "done"), "3 Slides, done");
assert.equal(carouselStepAccessibleName(stepAt(3), "available"), "3 Slides");

assert.equal(stepStateFor(doneSlides, stepAt(3)), "done");
assert.equal(canOpenCarouselStep(stepAt(3), doneSlides.slides), true);
assert.equal(canOpenCarouselStep(stepAt(3), availableSlides.slides), true);
assert.equal(canOpenCarouselStep(stepAt(3), lockedSlides.slides), false);

const closedStates: CarouselStepState[] = ["locked", "available", "done"];

for (const step of CAROUSEL_STEPS) {

  if (step.index === CAROUSEL_STEP_SLIDES) {
    continue;
  }

  for (const stepState of closedStates) {
    assert.equal(canOpenCarouselStep(step, stepState), false);
    assert.equal(stepClickStoresEditorStep(step, stepState, 3, true), false);
  }
}

assert.equal(stepClickStoresEditorStep(stepAt(3), "available", 3, true), true);
assert.equal(stepClickStoresEditorStep(stepAt(3), "available", 0, true), true);
assert.equal(stepClickStoresEditorStep(stepAt(3), "done", 3, true), false);
assert.equal(stepClickStoresEditorStep(stepAt(3), "done", 0, true), true);
assert.equal(stepClickStoresEditorStep(stepAt(3), "locked", 3, true), false);
assert.equal(stepClickStoresEditorStep(stepAt(3), "available", 3, false), false);
assert.equal(stepClickStoresEditorStep(stepAt(2), "available", 3, true), false);
