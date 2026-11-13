/** Visible label on the Duplicate button. */
export const DUPLICATE_GENERATION_LABEL: string = "Duplicate";

/** Label while the duplicate request is in flight. */
export const DUPLICATE_GENERATION_BUSY_LABEL: string = "Duplicating…";

/** Accessible name when a reader cannot duplicate. */
export const DUPLICATE_GENERATION_READER_NAME: string =
  "Duplicate. A reader cannot duplicate a generation.";

/** Which header is asking whether to show Duplicate. */
export type CarouselGenerationHeader = "carousel" | "slide";

/**
 * A saved carousel the page can show after Duplicate.
 */
export interface SavedGenerationCarousel {
  generation_number: number;
}

/**
 * The open carousel and the status line after Duplicate succeeds.
 */
export interface DuplicateGenerationState<SavedCarousel extends SavedGenerationCarousel> {
  carousel: SavedCarousel;
  statusMessage: string;
}

/**
 * Whether this header shows Duplicate.
 *
 * The open carousel shows it beside the generation pill. The slide
 * editor keeps the pill only.
 *
 * @param header - The carousel page or the slide editor
 * @returns True on the open carousel
 */
export function duplicateGenerationShown(header: CarouselGenerationHeader): boolean {

  return header === "carousel";
}

/**
 * Whether Duplicate can be pressed.
 *
 * An admin can duplicate. A reader stays disabled.
 *
 * @param canWrite - True for an admin
 * @returns True when the button can be pressed
 */
export function duplicateGenerationEnabled(canWrite: boolean): boolean {

  return canWrite;
}

/**
 * Accessible name for Duplicate.
 *
 * A reader hears why the button is disabled. While the request runs the
 * name is the busy label.
 *
 * @param canWrite - True for an admin
 * @param isDuplicating - True while the request is in flight
 * @returns The accessible name
 */
export function duplicateGenerationAccessibleName(
  canWrite: boolean,
  isDuplicating: boolean,
): string {

  if (isDuplicating) {
    return DUPLICATE_GENERATION_BUSY_LABEL;
  }

  if (!canWrite) {
    return DUPLICATE_GENERATION_READER_NAME;
  }

  return DUPLICATE_GENERATION_LABEL;
}

/**
 * Status line after Duplicate succeeds.
 *
 * @param generationNumber - The generation number on the saved carousel
 * @returns The status sentence
 */
export function duplicateGenerationStatusMessage(generationNumber: number): string {

  return `Duplicated. This is generation ${generationNumber}.`;
}

/**
 * Page state after Duplicate succeeds.
 *
 * The open carousel becomes the response. Final keeps that response's
 * assembly, which is empty until the next Assemble.
 *
 * @param savedCarousel - The carousel detail the route returned
 * @returns The carousel to show and the status sentence
 */
export function carouselAfterDuplicate<SavedCarousel extends SavedGenerationCarousel>(
  savedCarousel: SavedCarousel,
): DuplicateGenerationState<SavedCarousel> {

  const statusMessage: string = duplicateGenerationStatusMessage(savedCarousel.generation_number);
  const nextState: DuplicateGenerationState<SavedCarousel> = {
    carousel: savedCarousel,
    statusMessage,
  };

  return nextState;
}
