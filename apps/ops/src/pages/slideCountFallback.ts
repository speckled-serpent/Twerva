import type { CarouselStepState } from "../api/types";
import { CAROUSEL_STEP_SLIDES } from "./carouselSteps";

/**
 * Inclusive bounds of the global slide-count default.
 *
 * The same bounds live in `app/global_settings.py`. A later phase draws
 * a random count in this range when a carousel has no guidance. This
 * phase does not add a settings screen, and it does not store the
 * count on the skeleton. The done mark on Slides stays two slides.
 */
export const SLIDE_COUNT_DEFAULT_LOW: number = 5;
export const SLIDE_COUNT_DEFAULT_HIGH: number = 8;

/**
 * The one hint on the open Slides step.
 *
 * It names the global default. It does not add or remove slides.
 */
export const SLIDE_COUNT_FALLBACK_HINT: string =
  `The global slide-count default is a random value from ${SLIDE_COUNT_DEFAULT_LOW} to ${SLIDE_COUNT_DEFAULT_HIGH}, used when a later phase needs a count and this carousel has no guidance. That default lives in global settings.`;

/**
 * Hint shown while Slides is the open step.
 *
 * Basic, Instructions, Content, and Final return null. Locked Slides
 * keeps the album hint and does not add this one.
 *
 * @param editorStep - The step on screen
 * @param slidesState - Derived state of Slides
 * @returns The fallback hint, or null when this step should not show it
 */
export function slideCountFallbackHint(
  editorStep: number,
  slidesState: CarouselStepState,
): string | null {

  if (editorStep !== CAROUSEL_STEP_SLIDES) {

    return null;
  }

  if (slidesState === "locked") {

    return null;
  }

  return SLIDE_COUNT_FALLBACK_HINT;
}
