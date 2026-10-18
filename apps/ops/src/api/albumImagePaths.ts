/**
 * Album image routes shared by the Albums page and the Content step.
 *
 * New bytes go through `/api/v1/albums/{albumId}/...`. License, order,
 * alt, source, and the license note use the album PATCH, not these paths.
 */

/**
 * Collection of images on one album. Upload posts here.
 *
 * @param albumId - Album UUID
 * @returns `/api/v1/albums/{albumId}/images`
 */
export function albumImagesPath(albumId: string): string {

  return `/api/v1/albums/${albumId}/images`;
}

/**
 * URL import for one album image.
 *
 * @param albumId - Album UUID
 * @returns `/api/v1/albums/{albumId}/images/import`
 */
export function albumImageImportPath(albumId: string): string {

  return `/api/v1/albums/${albumId}/images/import`;
}

/**
 * One image on an album. Delete uses this path.
 *
 * @param albumId - Album UUID
 * @param imageId - Image UUID
 * @returns `/api/v1/albums/{albumId}/images/{imageId}`
 */
export function albumImageItemPath(albumId: string, imageId: string): string {

  return `/api/v1/albums/${albumId}/images/${imageId}`;
}

/**
 * Original file for one album image.
 *
 * @param albumId - Album UUID
 * @param imageId - Image UUID
 * @returns File path under the album image item
 */
export function albumImageFilePath(albumId: string, imageId: string): string {

  return `${albumImageItemPath(albumId, imageId)}/file`;
}

/**
 * Thumbnail for one album image.
 *
 * @param albumId - Album UUID
 * @param imageId - Image UUID
 * @returns Thumbnail path under the album image item
 */
export function albumImageThumbnailPath(albumId: string, imageId: string): string {

  return `${albumImageItemPath(albumId, imageId)}/thumbnail`;
}
