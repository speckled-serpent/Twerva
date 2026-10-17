export const CREATE_CAROUSEL_NAME_ERROR: string = "Name is required.";
export const CREATE_CAROUSEL_SKELETON_ERROR: string = "A carousel needs a skeleton.";

/**
 * Validate the create-carousel form. Name and skeleton are both required.
 *
 * @param sourceName - Name field
 * @param skeletonId - Selected skeleton id
 * @returns An error message, or null when the fields are ready to submit
 */
export function createCarouselFieldError(sourceName: string, skeletonId: string): string | null {

  if (sourceName.trim() === "") {
    return CREATE_CAROUSEL_NAME_ERROR;
  }

  if (skeletonId.trim() === "") {
    return CREATE_CAROUSEL_SKELETON_ERROR;
  }

  return null;
}
