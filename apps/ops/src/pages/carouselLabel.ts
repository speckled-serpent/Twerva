import type { AutosaveReadiness } from "./skeletonAutosave";

/** Shown when the label is blank. Matches the create form and the rename API. */
export const CAROUSEL_LABEL_ERROR: string = "Name is required.";

/**
 * The carousel label edited on Basic. The stored field is `name`.
 */
export interface CarouselLabelDraft {
  name: string;
}

/**
 * A blank label waits. The message is the required-name error.
 *
 * @param draft - The label field
 * @returns Ready to save, or the required-name error
 */
export function carouselLabelReadiness(draft: CarouselLabelDraft): AutosaveReadiness {

  if (draft.name.trim() === "") {
    const invalidName: AutosaveReadiness = {
      kind: "invalid",
      message: CAROUSEL_LABEL_ERROR,
    };

    return invalidName;
  }

  const ready: AutosaveReadiness = { kind: "ready" };

  return ready;
}

/**
 * Identity of a label that should be written. Surrounding spaces do not count.
 *
 * @param draft - The label field
 * @returns The trimmed name
 */
export function carouselLabelFingerprint(draft: CarouselLabelDraft): string {

  return draft.name.trim();
}
