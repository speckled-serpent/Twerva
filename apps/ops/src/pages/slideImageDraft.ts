export const SLIDE_IMAGE_SOURCE_ERROR: string = "Image source is required.";
export const SLIDE_IMAGE_NOTE_ERROR: string = "A licensed image needs a license note.";
export const SLIDE_IMAGE_TYPE_ERROR: string = "Image files must be SVG, PNG, or JPEG.";
export const SLIDE_IMAGE_URL_ERROR: string = "Enter an image URL.";
export const SLIDE_IMAGE_URL_SCHEME_ERROR: string = "The image URL must be http or https.";

const ALLOWED_IMAGE_EXTENSIONS: readonly string[] = [".svg", ".png", ".jpg", ".jpeg"];

/**
 * True for SVG, PNG, and JPEG names. The server still sniffs the bytes.
 *
 * Album image intake uses this before a file is posted. A slide does
 * not upload its own file.
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
