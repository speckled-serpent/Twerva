import type { CarouselStepState, CarouselStepsResponse } from "../api/types";

/** Stored and displayed step numbers. Instructions and Final are never stored. */
export const CAROUSEL_STEP_BASIC: number = 0;
export const CAROUSEL_STEP_INSTRUCTIONS: number = 1;
export const CAROUSEL_STEP_CONTENT: number = 2;
export const CAROUSEL_STEP_SLIDES: number = 3;
export const CAROUSEL_STEP_FINAL: number = 4;

/**
 * One step on the carousel stepper, in display order.
 */
export interface CarouselStepDefinition {
  index: number;
  key: keyof CarouselStepsResponse;
  label: string;
}

/**
 * The five steps, labeled with their index: 0 Basic through 4 Final.
 */
export const CAROUSEL_STEPS: readonly CarouselStepDefinition[] = [
  { index: CAROUSEL_STEP_BASIC, key: "basic", label: "Basic" },
  { index: CAROUSEL_STEP_INSTRUCTIONS, key: "instructions", label: "Instructions" },
  { index: CAROUSEL_STEP_CONTENT, key: "content", label: "Content" },
  { index: CAROUSEL_STEP_SLIDES, key: "slides", label: "Slides" },
  { index: CAROUSEL_STEP_FINAL, key: "final", label: "Final" },
];

/**
 * Steps the operator can open in this phase.
 *
 * Basic is the label and the locked skeleton. Content chooses an album.
 * Slides is the editor. Instructions and Final stay closed.
 */
export const OPENABLE_EDITOR_STEPS: readonly number[] = [
  CAROUSEL_STEP_BASIC,
  CAROUSEL_STEP_CONTENT,
  CAROUSEL_STEP_SLIDES,
];

/**
 * Shell and list label for the stored generation number.
 *
 * @param generationNumber - `carousels.generation_number`, at least 1
 * @returns Text such as "Generation 1"
 */
export function generationLabel(generationNumber: number): string {

  return `Generation ${generationNumber}`;
}

/**
 * Find the step definition for a stored editor step.
 *
 * @param stepIndex - 0 Basic through 4 Final
 * @returns That step, or null when the number is not a step
 */
export function carouselStepByIndex(stepIndex: number): CarouselStepDefinition | null {

  const foundStep: CarouselStepDefinition | undefined = CAROUSEL_STEPS.find(
    (step: CarouselStepDefinition): boolean => step.index === stepIndex,
  );

  if (foundStep === undefined) {
    return null;
  }

  return foundStep;
}

/**
 * Visible label, including the step index.
 *
 * @param step - A stepper step
 * @returns Text such as "3 Slides"
 */
export function carouselStepLabel(step: CarouselStepDefinition): string {

  return `${step.index} ${step.label}`;
}

/**
 * Why Instructions stays closed.
 *
 * Phase 5 stores versioned Markdown and runs it through the provider.
 * This phase keeps the control locked and leaves inspiration and rules
 * in their columns.
 */
export const INSTRUCTIONS_CLOSED_DETAIL: string =
  "Versioned Markdown instructions are a later phase. Phase 5 replaces the hidden inspiration and rules form.";

/**
 * Why Slides stays closed.
 *
 * The album rule fails when the skeleton needs a picture and no album
 * is attached. Research does not open Slides.
 */
export const SLIDES_ALBUM_REQUIRED_DETAIL: string =
  "Attach an album on Content first.";

/**
 * Accessible name, including locked or done when that is the derived state.
 *
 * Instructions stays closed for an admin and a reader. Its name says
 * versioned Markdown instructions are a later phase, and that phase 5
 * replaces the hidden inspiration and rules form. Locked Slides says
 * to attach an album on Content first. Available Slides stays unmarked.
 * Done Slides says done.
 *
 * @param step - A stepper step
 * @param stepState - Derived state from `steps`
 * @returns The button's accessible name
 */
export function carouselStepAccessibleName(
  step: CarouselStepDefinition,
  stepState: CarouselStepState,
): string {

  const label: string = carouselStepLabel(step);

  if (step.index === CAROUSEL_STEP_INSTRUCTIONS) {
    return `${label}, locked. ${INSTRUCTIONS_CLOSED_DETAIL}`;
  }

  if (step.index === CAROUSEL_STEP_SLIDES && stepState === "locked") {
    return `${label}, locked. ${SLIDES_ALBUM_REQUIRED_DETAIL}`;
  }

  if (stepState === "locked") {
    return `${label}, locked`;
  }

  if (stepState === "done") {
    return `${label}, done`;
  }

  return label;
}

/**
 * Lede sentence naming the stored open step.
 *
 * @param editorStep - `carousels.editor_step`
 * @returns A sentence such as "This carousel opens on Slides."
 */
export function openStepSentence(editorStep: number): string {

  const openStep: CarouselStepDefinition | null = carouselStepByIndex(editorStep);

  if (openStep === null) {
    return "This carousel opens on its stored step.";
  }

  return `This carousel opens on ${openStep.label}.`;
}

/**
 * Derived state for one step.
 *
 * @param steps - The five states from the carousel detail
 * @param step - The step to read
 * @returns locked, available, or done
 */
export function stepStateFor(
  steps: CarouselStepsResponse,
  step: CarouselStepDefinition,
): CarouselStepState {

  return steps[step.key];
}

/**
 * Whether this phase lets the operator open the step.
 *
 * Basic, Content, and Slides open when they are available or done. A
 * locked step stays closed. Instructions and Final stay closed.
 *
 * @param step - The step control
 * @param stepState - Derived state for that step
 * @returns True when the control can be selected
 */
export function canOpenCarouselStep(
  step: CarouselStepDefinition,
  stepState: CarouselStepState,
): boolean {

  if (!OPENABLE_EDITOR_STEPS.includes(step.index)) {
    return false;
  }

  if (stepState === "locked") {
    return false;
  }

  return true;
}

/**
 * Whether clicking the step writes `editor_step`.
 *
 * An available step that can be opened always calls the step PATCH.
 * A done step calls it only when it is not already the open step.
 * A reader does not write. A locked step does not write.
 *
 * @param step - The clicked step
 * @param stepState - Derived state for that step
 * @param editorStep - The stored open step
 * @param canWrite - True for an admin
 * @returns True when the click should PATCH
 */
export function stepClickStoresEditorStep(
  step: CarouselStepDefinition,
  stepState: CarouselStepState,
  editorStep: number,
  canWrite: boolean,
): boolean {

  if (!canWrite) {
    return false;
  }

  if (!canOpenCarouselStep(step, stepState)) {
    return false;
  }

  if (stepState === "available") {
    return true;
  }

  return editorStep !== step.index;
}

/**
 * Mark drawn on the control. Available stays unmarked.
 *
 * @param stepState - Derived state from `steps`
 * @returns Locked, Done, or null while the step is still open
 */
export function carouselStepMark(stepState: CarouselStepState): string | null {

  if (stepState === "locked") {
    return "Locked";
  }

  if (stepState === "done") {
    return "Done";
  }

  return null;
}

/**
 * Classes for one step control.
 *
 * The open step uses the teal primary. A done step uses the success
 * color. A locked step uses the stone disabled treatment. Available
 * adds neither done nor locked.
 *
 * @param stepState - Derived state from `steps`
 * @param isCurrent - True when this step is the one on screen
 * @returns Space-separated class names
 */
export function carouselStepClassName(
  stepState: CarouselStepState,
  isCurrent: boolean,
): string {

  const classNames: string[] = ["carousel-step"];

  if (isCurrent) {
    classNames.push("is-current");
  }

  if (stepState === "done") {
    classNames.push("is-done");
  }

  if (stepState === "locked") {
    classNames.push("is-locked");
  }

  return classNames.join(" ");
}

/**
 * Step the shell may show.
 *
 * Slides stays closed while `steps.slides` is locked. The shell shows
 * Content, where the album is attached, and does not write
 * `editor_step`. Any other stored step is shown as it is.
 *
 * @param editorStep - The stored step, or a step a reader is looking at
 * @param steps - The five states from the carousel detail
 * @returns The step whose panel is visible
 */
export function shellEditorStep(
  editorStep: number,
  steps: CarouselStepsResponse,
): number {

  if (editorStep !== CAROUSEL_STEP_SLIDES) {
    return editorStep;
  }

  const slidesStep: CarouselStepDefinition | null = carouselStepByIndex(
    CAROUSEL_STEP_SLIDES,
  );

  if (slidesStep === null) {
    return editorStep;
  }

  if (stepStateFor(steps, slidesStep) === "locked") {
    return CAROUSEL_STEP_CONTENT;
  }

  return editorStep;
}

/**
 * Step the shell shows.
 *
 * An admin follows the stored step. A reader can look at another open
 * step without writing `editor_step`.
 *
 * @param storedStep - `carousels.editor_step`
 * @param viewedStep - Step a reader opened locally, or null
 * @param canWrite - True for an admin
 * @returns The step whose panel is visible
 */
export function displayedEditorStep(
  storedStep: number,
  viewedStep: number | null,
  canWrite: boolean,
): number {

  if (canWrite || viewedStep === null) {
    return storedStep;
  }

  return viewedStep;
}
