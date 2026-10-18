import assert from "node:assert/strict";

import type { CarouselStepState, CarouselStepsResponse } from "./src/api/types.ts";
import {
  CAROUSEL_STEPS,
  CAROUSEL_STEP_BASIC,
  CAROUSEL_STEP_CONTENT,
  CAROUSEL_STEP_SLIDES,
  canOpenCarouselStep,
  carouselStepAccessibleName,
  carouselStepByIndex,
  carouselStepClassName,
  carouselStepLabel,
  carouselStepMark,
  displayedEditorStep,
  generationLabel,
  INSTRUCTIONS_CLOSED_DETAIL,
  openStepSentence,
  shellEditorStep,
  SLIDES_ALBUM_REQUIRED_DETAIL,
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
assert.equal(openStepSentence(CAROUSEL_STEP_CONTENT), "This carousel opens on Content.");
const instructionsName: string = carouselStepAccessibleName(stepAt(1), "locked");
assert.equal(
  instructionsName,
  `1 Instructions, locked. ${INSTRUCTIONS_CLOSED_DETAIL}`,
);
assert.match(instructionsName, /Versioned Markdown instructions are a later phase/);
assert.match(
  instructionsName,
  /Phase 5 replaces the hidden inspiration and rules form/,
);
assert.equal(carouselStepAccessibleName(stepAt(1), "available"), instructionsName);
assert.equal(carouselStepAccessibleName(stepAt(1), "done"), instructionsName);
assert.equal(SLIDES_ALBUM_REQUIRED_DETAIL, "Attach an album on Content first.");
assert.equal(
  carouselStepAccessibleName(stepAt(3), "locked"),
  `3 Slides, locked. ${SLIDES_ALBUM_REQUIRED_DETAIL}`,
);
assert.equal(carouselStepAccessibleName(stepAt(3), "done"), "3 Slides, done");
assert.equal(carouselStepAccessibleName(stepAt(3), "available"), "3 Slides");
assert.equal(carouselStepMark("locked"), "Locked");
assert.equal(carouselStepMark("available"), null);
assert.equal(carouselStepMark("done"), "Done");
assert.equal(carouselStepClassName("done", false).includes("is-done"), true);
assert.equal(carouselStepClassName("done", true).includes("is-done"), true);
assert.equal(carouselStepClassName("available", true).includes("is-done"), false);
assert.equal(carouselStepClassName("available", false).includes("is-locked"), false);
assert.equal(carouselStepClassName("locked", false).includes("is-locked"), true);
assert.equal(shellEditorStep(CAROUSEL_STEP_SLIDES, lockedSlides), CAROUSEL_STEP_CONTENT);
assert.equal(shellEditorStep(CAROUSEL_STEP_SLIDES, availableSlides), CAROUSEL_STEP_SLIDES);
assert.equal(shellEditorStep(CAROUSEL_STEP_SLIDES, doneSlides), CAROUSEL_STEP_SLIDES);
assert.equal(shellEditorStep(CAROUSEL_STEP_BASIC, lockedSlides), CAROUSEL_STEP_BASIC);
assert.equal(shellEditorStep(CAROUSEL_STEP_CONTENT, lockedSlides), CAROUSEL_STEP_CONTENT);

assert.equal(stepStateFor(doneSlides, stepAt(3)), "done");
assert.equal(canOpenCarouselStep(stepAt(3), doneSlides.slides), true);
assert.equal(canOpenCarouselStep(stepAt(3), availableSlides.slides), true);
assert.equal(canOpenCarouselStep(stepAt(3), lockedSlides.slides), false);
assert.equal(canOpenCarouselStep(stepAt(CAROUSEL_STEP_BASIC), "done"), true);
assert.equal(canOpenCarouselStep(stepAt(CAROUSEL_STEP_BASIC), "available"), true);
assert.equal(canOpenCarouselStep(stepAt(CAROUSEL_STEP_BASIC), "locked"), false);
assert.equal(canOpenCarouselStep(stepAt(CAROUSEL_STEP_CONTENT), "available"), true);
assert.equal(canOpenCarouselStep(stepAt(CAROUSEL_STEP_CONTENT), "done"), true);
assert.equal(canOpenCarouselStep(stepAt(CAROUSEL_STEP_CONTENT), "locked"), false);
assert.equal(carouselStepAccessibleName(stepAt(CAROUSEL_STEP_CONTENT), "available"), "2 Content");
assert.equal(carouselStepAccessibleName(stepAt(CAROUSEL_STEP_CONTENT), "done"), "2 Content, done");

const closedStates: CarouselStepState[] = ["locked", "available", "done"];
const openableSteps: number[] = [
  CAROUSEL_STEP_BASIC,
  CAROUSEL_STEP_CONTENT,
  CAROUSEL_STEP_SLIDES,
];

for (const step of CAROUSEL_STEPS) {

  if (openableSteps.includes(step.index)) {
    continue;
  }

  for (const stepState of closedStates) {
    assert.equal(canOpenCarouselStep(step, stepState), false);
    assert.equal(stepClickStoresEditorStep(step, stepState, 3, true), false);
  }
}

assert.equal(stepClickStoresEditorStep(stepAt(CAROUSEL_STEP_BASIC), "done", 0, true), false);
assert.equal(stepClickStoresEditorStep(stepAt(CAROUSEL_STEP_BASIC), "done", 3, true), true);
assert.equal(stepClickStoresEditorStep(stepAt(CAROUSEL_STEP_BASIC), "done", 3, false), false);
assert.equal(stepClickStoresEditorStep(stepAt(CAROUSEL_STEP_BASIC), "locked", 3, true), false);
assert.equal(stepClickStoresEditorStep(stepAt(3), "available", 3, true), true);
assert.equal(stepClickStoresEditorStep(stepAt(3), "available", 0, true), true);
assert.equal(stepClickStoresEditorStep(stepAt(3), "done", 3, true), false);
assert.equal(stepClickStoresEditorStep(stepAt(3), "done", 0, true), true);
assert.equal(stepClickStoresEditorStep(stepAt(3), "locked", 3, true), false);
assert.equal(stepClickStoresEditorStep(stepAt(3), "available", 3, false), false);
assert.equal(stepClickStoresEditorStep(stepAt(CAROUSEL_STEP_CONTENT), "available", 3, true), true);
assert.equal(stepClickStoresEditorStep(stepAt(CAROUSEL_STEP_CONTENT), "available", 2, true), true);
assert.equal(stepClickStoresEditorStep(stepAt(CAROUSEL_STEP_CONTENT), "done", 2, true), false);
assert.equal(stepClickStoresEditorStep(stepAt(CAROUSEL_STEP_CONTENT), "done", 3, true), true);
assert.equal(stepClickStoresEditorStep(stepAt(CAROUSEL_STEP_CONTENT), "available", 3, false), false);
assert.equal(stepClickStoresEditorStep(stepAt(CAROUSEL_STEP_CONTENT), "locked", 3, true), false);
assert.equal(
  canOpenCarouselStep(stepAt(CAROUSEL_STEP_CONTENT), lockedSlides.content),
  true,
);
assert.equal(canOpenCarouselStep(stepAt(CAROUSEL_STEP_SLIDES), lockedSlides.slides), false);
assert.equal(displayedEditorStep(3, null, true), 3);
assert.equal(displayedEditorStep(3, 2, true), 3);
assert.equal(displayedEditorStep(3, null, false), 3);
assert.equal(displayedEditorStep(3, CAROUSEL_STEP_CONTENT, false), CAROUSEL_STEP_CONTENT);
assert.equal(stepClickStoresEditorStep(stepAt(1), "locked", 0, true), false);
assert.equal(stepClickStoresEditorStep(stepAt(1), "locked", 3, true), false);
assert.equal(stepClickStoresEditorStep(stepAt(1), "locked", 0, false), false);
assert.equal(canOpenCarouselStep(stepAt(1), "locked"), false);
