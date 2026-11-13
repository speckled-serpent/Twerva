import type { CarouselStepState, CarouselStepsResponse } from "../api/types";

/** Stored step numbers. The page does not use these to hide a section. */
export const CAROUSEL_STEP_BASIC: number = 0;
export const CAROUSEL_STEP_INSTRUCTIONS: number = 1;
export const CAROUSEL_STEP_CONTENT: number = 2;
export const CAROUSEL_STEP_SLIDES: number = 3;
export const CAROUSEL_STEP_FINAL: number = 4;

/**
 * One named part of a carousel, in display order.
 *
 * The index is the stored `editor_step` value. Final is never stored.
 */
export interface CarouselStepDefinition {
  index: number;
  key: keyof CarouselStepsResponse;
  label: string;
}

/**
 * Basic through Final, in the order the page stacks them.
 */
export const CAROUSEL_STEPS: readonly CarouselStepDefinition[] = [
  { index: CAROUSEL_STEP_BASIC, key: "basic", label: "Basic" },
  { index: CAROUSEL_STEP_INSTRUCTIONS, key: "instructions", label: "Instructions" },
  { index: CAROUSEL_STEP_CONTENT, key: "content", label: "Content" },
  { index: CAROUSEL_STEP_SLIDES, key: "slides", label: "Slides" },
  { index: CAROUSEL_STEP_FINAL, key: "final", label: "Final" },
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
 * Find the definition for a stored editor step.
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
 * Label that includes the stored step index.
 *
 * The page headings use `label` alone. This form stays for the stored number.
 *
 * @param step - A carousel section
 * @returns Text such as "3 Slides"
 */
export function carouselStepLabel(step: CarouselStepDefinition): string {

  return `${step.index} ${step.label}`;
}

/**
 * Why a picture carousel with no album cannot choose a slide image yet.
 *
 * The album rule fails when the skeleton needs a picture and no album
 * is attached. Research does not change this.
 */
export const SLIDES_ALBUM_REQUIRED_DETAIL: string =
  "Attach an album on Content first.";

/**
 * Derived state for one section.
 *
 * @param steps - The five states from the carousel detail
 * @param step - The section to read
 * @returns locked, available, or done
 */
export function stepStateFor(
  steps: CarouselStepsResponse,
  step: CarouselStepDefinition,
): CarouselStepState {

  return steps[step.key];
}
