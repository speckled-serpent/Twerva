import type { SlideImageLicense } from "../api/types";

export type SlideImageDraftKind = "file" | "url";

export interface SlideImageDraftCheck {
  kind: SlideImageDraftKind;
  fileName: string | null;
  url: string;
  imageSource: string;
  imageLicense: SlideImageLicense;
  licenseNote: string;
}

export const SLIDE_IMAGE_SOURCE_ERROR: string = "Image source is required.";
export const SLIDE_IMAGE_NOTE_ERROR: string = "A licensed image needs a license note.";
export const SLIDE_IMAGE_TYPE_ERROR: string = "Image files must be SVG, PNG, or JPEG.";
export const SLIDE_IMAGE_URL_ERROR: string = "Enter an image URL.";
export const SLIDE_IMAGE_URL_SCHEME_ERROR: string = "The image URL must be http or https.";

const ALLOWED_IMAGE_EXTENSIONS: readonly string[] = [".svg", ".png", ".jpg", ".jpeg"];

/**
 * Client check for one image on the Add slide form. The server repeats it.
 *
 * @param draft - Kind, file name or URL, and the license fields
 * @returns An inline error, or null when this image can be saved
 */
export function slideImageDraftError(draft: SlideImageDraftCheck): string | null {

  if (draft.kind === "file") {
    if (draft.fileName === null || !isAllowedImageFileName(draft.fileName)) {
      return SLIDE_IMAGE_TYPE_ERROR;
    }
  } else if (draft.url.trim() === "") {
    return SLIDE_IMAGE_URL_ERROR;
  } else if (!isHttpImageUrl(draft.url.trim())) {
    return SLIDE_IMAGE_URL_SCHEME_ERROR;
  }

  if (draft.imageSource.trim() === "") {
    return SLIDE_IMAGE_SOURCE_ERROR;
  }

  if (draft.imageLicense === "licensed" && draft.licenseNote.trim() === "") {
    return SLIDE_IMAGE_NOTE_ERROR;
  }

  return null;
}

/**
 * First image error, in form order.
 *
 * @param drafts - Pending images on the Add slide form
 * @returns An inline error, or null when every image can be saved
 */
export function firstSlideImageDraftError(drafts: SlideImageDraftCheck[]): string | null {

  for (const draft of drafts) {
    const draftError: string | null = slideImageDraftError(draft);

    if (draftError !== null) {
      return draftError;
    }
  }

  return null;
}

/**
 * True for SVG, PNG, and JPEG names. The server still sniffs the bytes.
 *
 * @param fileName - Chosen file name
 * @returns Whether the extension is allowed
 */
export function isAllowedImageFileName(fileName: string): boolean {

  const loweredName: string = fileName.trim().toLowerCase();
  const allowed: boolean = ALLOWED_IMAGE_EXTENSIONS.some(
    (extension: string): boolean => loweredName.endsWith(extension),
  );

  return allowed;
}

/**
 * True for http and https URLs.
 *
 * @param imageUrl - URL the admin typed
 * @returns Whether the scheme is allowed
 */
export function isHttpImageUrl(imageUrl: string): boolean {

  try {
    const parsedUrl: URL = new URL(imageUrl);
    const allowed: boolean = parsedUrl.protocol === "http:" || parsedUrl.protocol === "https:";

    return allowed;
  } catch {
    return false;
  }
}
