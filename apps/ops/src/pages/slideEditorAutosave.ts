import type { SlideElementTextWrite, SlideWriteRequest } from "../api/types";
import {
  SLIDE_IMAGE_REQUIRED_COPY,
  newPictureSlideWriteRequest,
  slideTextSaveRequest,
} from "./slideAlbumImage.ts";
import type { AutosaveReadiness } from "./skeletonAutosave.ts";

/** Shown when the name is blank. Matches the carousel label and the slide API. */
export const SLIDE_NAME_REQUIRED_ERROR: string = "Name is required.";

/** Existing slide. Name, text, and exclusions save without a Save button. */
export const SLIDE_AUTOSAVE_HINT: string =
  "The name, text, and exclusions save on their own.";

/**
 * New slide that does not need a picture.
 *
 * There is no row until the name is filled in and the pause elapses.
 */
export const NEW_SLIDE_AUTOSAVE_HINT: string =
  "This slide is stored when you pause, once the name is filled in. Nothing is saved before that.";

/**
 * New picture slide.
 *
 * The row is created only when the name and a chosen album image are both set.
 */
export const NEW_PICTURE_SLIDE_AUTOSAVE_HINT: string =
  "This slide is stored when you pause, once the name is filled in and an image is chosen. Nothing is saved before that.";

/**
 * Name, text, and exclusions being edited on one slide.
 *
 * `slideId` is null until the row exists. `albumImageId` is the image a
 * new picture slide will be created with, or the image an existing slide
 * already points at. The debounced save omits that id on an existing slide.
 */
export interface SlideFieldDraft {
  slideId: string | null;
  needsImage: boolean;
  skeletonReady: boolean;
  name: string;
  texts: SlideElementTextWrite[];
  excludedSlideIds: string[];
  albumImageId: string | null;
}

/**
 * Whether this draft should be written.
 *
 * An existing slide with a blank name waits and shows the required-name
 * error. The previous name stays on the row. A new slide with nothing
 * filled in waits quietly, because there is no row yet. Once the operator
 * has typed text, picked an image, or marked an exclusion, a blank name
 * shows the same error and still does not create a row. A picture slide
 * with no chosen or stored image waits until one is chosen.
 *
 * @param draft - The slide fields in the editor
 * @returns Skip, the required-name or image error, or ready
 */
export function slideEditorReadiness(draft: SlideFieldDraft): AutosaveReadiness {

  if (!draft.skeletonReady) {
    const waitingForSkeleton: AutosaveReadiness = { kind: "skip" };

    return waitingForSkeleton;
  }

  if (draft.slideId === null && isUntouchedNewSlide(draft)) {
    const waitingToStart: AutosaveReadiness = { kind: "skip" };

    return waitingToStart;
  }

  if (draft.name.trim() === "") {
    const invalidName: AutosaveReadiness = {
      kind: "invalid",
      message: SLIDE_NAME_REQUIRED_ERROR,
    };

    return invalidName;
  }

  if (draft.needsImage && draft.albumImageId === null) {
    const missingImage: AutosaveReadiness = {
      kind: "invalid",
      message: SLIDE_IMAGE_REQUIRED_COPY,
    };

    return missingImage;
  }

  const ready: AutosaveReadiness = { kind: "ready" };

  return ready;
}

/**
 * Identity of the name, text, and exclusions.
 *
 * Surrounding spaces on the name do not count. The album image is not
 * part of the identity: choosing one on an existing slide saves
 * immediately, and a new slide keeps the chosen id on the draft object
 * the saver already holds. Two drafts that differ only by that id still
 * share a fingerprint, and the latest draft is the one that is written.
 *
 * @param draft - The slide fields in the editor
 * @returns A string that changes when the autosaved fields change
 */
export function slideEditorFingerprint(draft: SlideFieldDraft): string {

  const textParts: string[] = draft.texts.map(
    (text: SlideElementTextWrite): string => `${text.skeleton_element_id}=${text.value}`,
  );
  const excludedPart: string = [...draft.excludedSlideIds].sort().join(",");
  const fingerprint: string = `${draft.name.trim()}\n${textParts.join("\n")}\n${excludedPart}`;

  return fingerprint;
}

/**
 * Body for the debounced save.
 *
 * An existing slide omits `album_image_id`, so the current image stays.
 * A new picture slide includes the chosen id, because that is the create.
 * A new slide that needs no picture omits it.
 *
 * @param draft - A draft `slideEditorReadiness` has already called ready
 * @returns The create or PATCH body
 */
export function slideAutosaveWriteRequest(draft: SlideFieldDraft): SlideWriteRequest {

  const trimmedName: string = draft.name.trim();
  const texts: SlideElementTextWrite[] = draft.texts.map(
    (text: SlideElementTextWrite): SlideElementTextWrite => ({
      skeleton_element_id: text.skeleton_element_id,
      value: text.value,
    }),
  );
  const excludedSlideIds: string[] = [...draft.excludedSlideIds];

  if (draft.slideId === null && draft.needsImage) {

    if (draft.albumImageId === null) {
      throw new Error(SLIDE_IMAGE_REQUIRED_COPY);
    }

    return newPictureSlideWriteRequest(
      trimmedName,
      texts,
      excludedSlideIds,
      draft.albumImageId,
    );
  }

  return slideTextSaveRequest(trimmedName, texts, excludedSlideIds);
}

/**
 * Immediate image save for an existing slide.
 *
 * The album image is set. Name, text, and exclusions are the draft the
 * autosave just flushed, so this PATCH does not put the previous text back.
 *
 * @param draft - The flushed slide fields
 * @param albumImageId - The album image the operator just chose
 * @returns The slide PATCH body
 */
export function slideImageChoiceWriteRequest(
  draft: SlideFieldDraft,
  albumImageId: string,
): SlideWriteRequest {

  const slideWriteRequest: SlideWriteRequest = slideTextSaveRequest(
    draft.name.trim(),
    draft.texts,
    draft.excludedSlideIds,
  );
  slideWriteRequest.album_image_id = albumImageId;

  return slideWriteRequest;
}

/**
 * A new slide the operator has not started.
 *
 * No name, no text, no exclusion, and no chosen image. Autosave stays quiet.
 *
 * @param draft - The slide fields in the editor
 * @returns True when creating a row would store an empty slide
 */
function isUntouchedNewSlide(draft: SlideFieldDraft): boolean {

  if (draft.name.trim() !== "") {
    return false;
  }

  if (draft.albumImageId !== null) {
    return false;
  }

  if (draft.excludedSlideIds.length > 0) {
    return false;
  }

  const hasText: boolean = draft.texts.some(
    (text: SlideElementTextWrite): boolean => text.value !== "",
  );

  return !hasText;
}
