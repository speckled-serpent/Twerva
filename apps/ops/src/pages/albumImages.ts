import type {
  AlbumImageReadResponse,
  AlbumPatchRequest,
  AlbumReadResponse,
  SlideImageLicense,
} from "../api/types";
import type { AutosaveReadiness } from "./skeletonAutosave";
import {
  SLIDE_IMAGE_NOTE_ERROR,
  SLIDE_IMAGE_SOURCE_ERROR,
  SLIDE_IMAGE_TYPE_ERROR,
  SLIDE_IMAGE_URL_ERROR,
  SLIDE_IMAGE_URL_SCHEME_ERROR,
  isAllowedImageFileName,
  isHttpImageUrl,
} from "./slideImageDraft.ts";

export const ALBUM_IMAGE_LICENSES: readonly SlideImageLicense[] = [
  "cc0",
  "public_domain",
  "owned",
  "licensed",
];

export const ALBUM_NAME_ERROR: string = "Name is required.";

export interface AlbumImageDraft {
  id: string;
  altText: string;
  license: SlideImageLicense;
  source: string;
  licenseNote: string;
  relativePath: string;
  thumbnailPath: string | null;
}

export interface AlbumDraft {
  name: string;
  images: AlbumImageDraft[];
}

export interface AlbumImageFieldPatch {
  altText?: string;
  license?: SlideImageLicense;
  source?: string;
  licenseNote?: string;
}

/**
 * Draft the album detail and the Content step both edit.
 *
 * Images are in position order. A licensed row keeps its note. Any other
 * license stores an empty note, matching the album PATCH.
 *
 * @param album - Album detail from `GET /api/v1/albums/{id}`
 * @returns Name plus ordered image fields
 */
export function draftFromAlbum(album: AlbumReadResponse): AlbumDraft {

  const orderedImages: AlbumImageReadResponse[] = [...album.images].sort(
    (left: AlbumImageReadResponse, right: AlbumImageReadResponse): number => (
      left.position - right.position
    ),
  );
  const imageDrafts: AlbumImageDraft[] = orderedImages.map(
    (image: AlbumImageReadResponse): AlbumImageDraft => {
      const imageDraft: AlbumImageDraft = {
        id: image.id,
        altText: image.alt_text ?? "",
        license: image.license,
        source: image.source,
        licenseNote: image.license === "licensed" ? image.license_note : "",
        relativePath: image.relative_path,
        thumbnailPath: image.thumbnail_path,
      };

      return imageDraft;
    },
  );
  const draft: AlbumDraft = {
    name: album.name,
    images: imageDrafts,
  };

  return draft;
}

/**
 * Album PATCH body. The array order is the saved order.
 *
 * @param draft - Name and image fields
 * @returns Body for `PATCH /api/v1/albums/{id}`
 */
export function patchFromDraft(draft: AlbumDraft): AlbumPatchRequest {

  const patchRequest: AlbumPatchRequest = {
    name: draft.name.trim(),
    images: draft.images.map((image: AlbumImageDraft) => ({
      id: image.id,
      alt_text: image.altText.trim() === "" ? null : image.altText.trim(),
      license: image.license,
      source: image.source.trim(),
      license_note: image.license === "licensed" ? image.licenseNote.trim() : "",
    })),
  };

  return patchRequest;
}

/**
 * Blank name, blank source, or a licensed image with no note cannot save.
 *
 * @param draft - Name and image fields
 * @returns Ready, or the first reason to wait
 */
export function albumDraftReadiness(draft: AlbumDraft): AutosaveReadiness {

  if (draft.name.trim() === "") {
    const invalidName: AutosaveReadiness = {
      kind: "invalid",
      message: ALBUM_NAME_ERROR,
    };

    return invalidName;
  }

  for (const image of draft.images) {
    if (image.source.trim() === "") {
      const invalidSource: AutosaveReadiness = {
        kind: "invalid",
        message: SLIDE_IMAGE_SOURCE_ERROR,
      };

      return invalidSource;
    }

    if (image.license === "licensed" && image.licenseNote.trim() === "") {
      const invalidNote: AutosaveReadiness = {
        kind: "invalid",
        message: SLIDE_IMAGE_NOTE_ERROR,
      };

      return invalidNote;
    }
  }

  const ready: AutosaveReadiness = { kind: "ready" };

  return ready;
}

/**
 * Stable text for the autosave. Trimmed fields only, in list order.
 *
 * @param draft - Name and image fields
 * @returns Fingerprint compared with the last successful save
 */
export function albumDraftFingerprint(draft: AlbumDraft): string {

  const fingerprint: string = JSON.stringify({
    name: draft.name.trim(),
    images: draft.images.map((image: AlbumImageDraft) => ({
      id: image.id,
      altText: image.altText.trim(),
      license: image.license,
      source: image.source.trim(),
      licenseNote: image.license === "licensed" ? image.licenseNote.trim() : "",
    })),
  });

  return fingerprint;
}

/**
 * Swap one image with its neighbor. Out of range returns null.
 *
 * @param images - Current order
 * @param imageIndex - Index of the image to move
 * @param direction - -1 up, 1 down
 * @returns The new order, or null when the move does not fit
 */
export function moveAlbumImage(
  images: readonly AlbumImageDraft[],
  imageIndex: number,
  direction: -1 | 1,
): AlbumImageDraft[] | null {

  const nextIndex: number = imageIndex + direction;

  if (nextIndex < 0 || nextIndex >= images.length) {
    return null;
  }

  const nextImages: AlbumImageDraft[] = [...images];
  const movingImage: AlbumImageDraft | undefined = nextImages[imageIndex];
  const swappedImage: AlbumImageDraft | undefined = nextImages[nextIndex];

  if (movingImage === undefined || swappedImage === undefined) {
    return null;
  }

  nextImages[imageIndex] = swappedImage;
  nextImages[nextIndex] = movingImage;

  return nextImages;
}

/**
 * Replace fields on one image and leave the others in place.
 *
 * @param images - Current image drafts
 * @param imageId - Image to change
 * @param patch - Fields to replace. Omitted fields stay.
 * @returns A new list
 */
export function withAlbumImagePatch(
  images: readonly AlbumImageDraft[],
  imageId: string,
  patch: AlbumImageFieldPatch,
): AlbumImageDraft[] {

  const nextImages: AlbumImageDraft[] = images.map(
    (image: AlbumImageDraft): AlbumImageDraft => {

      if (image.id !== imageId) {
        return image;
      }

      const nextImage: AlbumImageDraft = {
        id: image.id,
        altText: patch.altText === undefined ? image.altText : patch.altText,
        license: patch.license === undefined ? image.license : patch.license,
        source: patch.source === undefined ? image.source : patch.source,
        licenseNote: patch.licenseNote === undefined ? image.licenseNote : patch.licenseNote,
        relativePath: image.relativePath,
        thumbnailPath: image.thumbnailPath,
      };

      return nextImage;
    },
  );

  return nextImages;
}

/**
 * License change. A license other than licensed clears the note.
 *
 * @param image - Image being edited
 * @param nextLicense - License chosen in the select
 * @returns Fields to merge into that image
 */
export function albumImageLicensePatch(
  image: AlbumImageDraft,
  nextLicense: SlideImageLicense,
): AlbumImageFieldPatch {

  const patch: AlbumImageFieldPatch = {
    license: nextLicense,
    licenseNote: nextLicense === "licensed" ? image.licenseNote : "",
  };

  return patch;
}

/**
 * Select values are the four licenses. Anything else is ignored.
 *
 * @param value - Option value from the license select
 * @returns The license, or null when the value is not one
 */
export function slideImageLicenseFromSelect(value: string): SlideImageLicense | null {

  for (const licenseOption of ALBUM_IMAGE_LICENSES) {
    if (licenseOption === value) {
      return licenseOption;
    }
  }

  return null;
}

/**
 * Row shape `albumImageDisplayUrl` needs. The URL only reads the thumbnail.
 *
 * @param image - Draft row
 * @param position - Index in the current order
 * @returns A display row for the thumbnail helper
 */
export function displayImageFromDraft(
  image: AlbumImageDraft,
  position: number,
): AlbumImageReadResponse {

  const displayImage: AlbumImageReadResponse = {
    id: image.id,
    position,
    relative_path: image.relativePath,
    media_type: "jpeg",
    byte_size: 0,
    width: null,
    height: null,
    alt_text: image.altText === "" ? null : image.altText,
    license: image.license,
    source: image.source,
    license_note: image.licenseNote,
    intake: "upload",
    thumbnail_path: image.thumbnailPath,
  };

  return displayImage;
}

/**
 * Client check before a file is posted to the album.
 *
 * @param fileName - Chosen file name
 * @param source - Source field
 * @param imageLicense - License field
 * @param licenseNote - Note field
 * @returns An inline error, or null when the file can be added
 */
export function albumImageFileIntakeError(
  fileName: string,
  source: string,
  imageLicense: SlideImageLicense,
  licenseNote: string,
): string | null {

  if (!isAllowedImageFileName(fileName)) {
    return SLIDE_IMAGE_TYPE_ERROR;
  }

  return sharedIntakeError(source, imageLicense, licenseNote);
}

/**
 * Client check before a URL is imported onto the album.
 *
 * @param imageUrl - URL field
 * @param source - Source field
 * @param imageLicense - License field
 * @param licenseNote - Note field
 * @returns An inline error, or null when the URL can be imported
 */
export function albumImageUrlIntakeError(
  imageUrl: string,
  source: string,
  imageLicense: SlideImageLicense,
  licenseNote: string,
): string | null {

  if (imageUrl === "") {
    return SLIDE_IMAGE_URL_ERROR;
  }

  if (!isHttpImageUrl(imageUrl)) {
    return SLIDE_IMAGE_URL_SCHEME_ERROR;
  }

  return sharedIntakeError(source, imageLicense, licenseNote);
}

function sharedIntakeError(
  source: string,
  imageLicense: SlideImageLicense,
  licenseNote: string,
): string | null {

  if (source.trim() === "") {
    return SLIDE_IMAGE_SOURCE_ERROR;
  }

  if (imageLicense === "licensed" && licenseNote.trim() === "") {
    return SLIDE_IMAGE_NOTE_ERROR;
  }

  return null;
}
