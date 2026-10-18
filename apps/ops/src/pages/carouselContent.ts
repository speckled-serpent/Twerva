import type { AlbumListItemResponse } from "../api/types";

/** Picture skeleton, no album. The operator chooses or creates one. */
export const ALBUM_REQUIRED_COPY: string =
  "This skeleton needs an album. Choose or create one.";

/** Skeleton that needs no picture, and no album is attached. */
export const ALBUM_OPTIONAL_COPY: string =
  "No album is attached. Slides for this skeleton do not use a picture.";

/** Attached album whose image list is empty. */
export const ALBUM_HAS_NO_IMAGES_COPY: string = "This album has no images yet.";

/** Blank name on create. Matches `POST /api/v1/carousels/{id}/album`. */
export const ALBUM_NAME_REQUIRED_COPY: string = "Name is required.";

/** License, order, alt, and source on an attached album save themselves. */
export const ALBUM_IMAGES_AUTOSAVE_COPY: string =
  "Order, alt, source, and license fields save on their own.";

/** A reader can see the attached album's images and cannot change them. */
export const ALBUM_IMAGES_READONLY_COPY: string =
  "Editing album images is an admin action.";

/**
 * Copy for a carousel with no album.
 *
 * A picture skeleton says to choose or create one. A skeleton that needs
 * no picture says slides do not use a picture.
 *
 * @param skeletonNeedsImage - True when the skeleton needs a picture
 * @returns The empty-state sentence
 */
export function detachedAlbumCopy(skeletonNeedsImage: boolean): string {

  if (skeletonNeedsImage) {
    return ALBUM_REQUIRED_COPY;
  }

  return ALBUM_OPTIONAL_COPY;
}

/**
 * Name shown for the attached album.
 *
 * The album detail wins once it has loaded. Until then the list name is used.
 *
 * @param detailName - Name from `GET /api/v1/albums/{id}`, or null
 * @param listedName - Name from the album list, or null
 * @returns The name to show, or null when neither has arrived
 */
export function visibleAlbumName(
  detailName: string | null,
  listedName: string | null,
): string | null {

  if (detailName !== null && detailName !== "") {
    return detailName;
  }

  if (listedName !== null && listedName !== "") {
    return listedName;
  }

  return null;
}

/**
 * Image count shown beside the attached album.
 *
 * The detail count wins, so an upload on Content updates the count before
 * the album list is fetched again. The list count covers the first paint.
 *
 * @param detailCount - Images on the loaded album, or null while it loads
 * @param listedCount - `image_count` from the list, or null
 * @returns The count to show, or null when neither is known
 */
export function visibleAlbumImageCount(
  detailCount: number | null,
  listedCount: number | null,
): number | null {

  if (detailCount !== null) {
    return detailCount;
  }

  return listedCount;
}

/**
 * Image count beside the attached album's name.
 *
 * @param imageCount - Images on the album
 * @returns "1 image" or "6 images"
 */
export function albumImageCountLabel(imageCount: number): string {

  if (imageCount === 1) {
    return "1 image";
  }

  return `${imageCount} images`;
}

/**
 * Albums the chooser can attach.
 *
 * Replacing hides the album already attached, so the action points at
 * a different one. Creating a name is separate and still replaces.
 *
 * @param albums - Albums from `GET /api/v1/albums`
 * @param attachedAlbumId - The carousel's album, or null
 * @param isReplacing - True when an attached album is being replaced
 * @returns Albums in name order
 */
export function albumsToChoose(
  albums: readonly AlbumListItemResponse[],
  attachedAlbumId: string | null,
  isReplacing: boolean,
): AlbumListItemResponse[] {

  const orderedAlbums: AlbumListItemResponse[] = [...albums].sort(
    (left: AlbumListItemResponse, right: AlbumListItemResponse): number => {

      return left.name.localeCompare(right.name);
    },
  );

  if (!isReplacing || attachedAlbumId === null) {
    return orderedAlbums;
  }

  const otherAlbums: AlbumListItemResponse[] = orderedAlbums.filter(
    (album: AlbumListItemResponse): boolean => album.id !== attachedAlbumId,
  );

  return otherAlbums;
}

/**
 * Sentence for a failed attach, create, or clear.
 *
 * A 409 uses the API detail: slides still point at that album's images,
 * so clear those slide images first. The stored album is left unchanged.
 *
 * @param error - Caught request failure
 * @returns The reason shown in the form
 */
export function albumActionErrorText(error: unknown): string {

  const detailText: string | null = detailTextFromError(error);

  if (detailText !== null) {
    return detailText;
  }

  if (error instanceof Error && error.message !== "") {
    return error.message;
  }

  return "The album could not be changed.";
}

function detailTextFromError(error: unknown): string | null {

  if (typeof error !== "object" || error === null || !("detailText" in error)) {
    return null;
  }

  const detailText: unknown = error.detailText;

  if (typeof detailText !== "string" || detailText === "") {
    return null;
  }

  return detailText;
}
