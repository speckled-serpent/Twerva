import type {
  CarouselReadResponse,
  SlideElementTextReadResponse,
  SlideImageReadResponse,
  SlideReadResponse,
} from "../api/types";

export const DEFAULT_ALBUM_ID: string = "default";
export const SAVED_ASSET_OPTION: string = "__saved__";

export interface SkeletonPickerImage {
  imageId: string;
  slideId: string;
  relativePath: string;
  hasThumbnail: boolean;
}

export interface SkeletonPickerSlide {
  slideId: string;
  caption: string;
  images: SkeletonPickerImage[];
}

export interface SkeletonImageAlbum {
  album_id: string;
  name: string;
  slug: string;
  asset_refs: string[];
  slides: SkeletonPickerSlide[];
}

/**
 * Caption beside a slide's images. The first non-empty text value wins.
 * The caption is not stored on the skeleton.
 *
 * @param textValues - Skeleton text stored on the slide, in display order
 * @returns Display text, possibly empty
 */
export function captionForSlide(textValues: readonly string[]): string {

  for (const textValue of textValues) {
    const trimmedValue: string = textValue.trim();

    if (trimmedValue !== "") {
      return trimmedValue;
    }
  }

  return "";
}

/**
 * Albums for the skeleton picker. Text-only slides are omitted.
 *
 * @param carousel - Album detail from `GET /api/v1/carousels/{id}`
 * @returns One album and the image slides inside it
 */
export function skeletonAlbumFromCarousel(carousel: CarouselReadResponse): SkeletonImageAlbum {

  const orderedSlides: SlideReadResponse[] = [...carousel.slides].sort(
    (left: SlideReadResponse, right: SlideReadResponse): number => left.position - right.position,
  );
  const pickerSlides: SkeletonPickerSlide[] = [];
  const assetRefs: string[] = [];

  for (const slide of orderedSlides) {
    const orderedImages: SlideImageReadResponse[] = [...slide.images].sort(
      (left: SlideImageReadResponse, right: SlideImageReadResponse): number => (
        left.position - right.position
      ),
    );

    if (orderedImages.length === 0) {
      continue;
    }

    const textValues: string[] = slide.texts.map(
      (elementText: SlideElementTextReadResponse): string => elementText.value,
    );
    const pickerImages: SkeletonPickerImage[] = orderedImages.map((image) => {
      assetRefs.push(image.relative_path);

      const pickerImage: SkeletonPickerImage = {
        imageId: image.id,
        slideId: slide.id,
        relativePath: image.relative_path,
        hasThumbnail: image.thumbnail_path !== null && image.thumbnail_path !== "",
      };

      return pickerImage;
    });
    const pickerSlide: SkeletonPickerSlide = {
      slideId: slide.id,
      caption: captionForSlide(textValues),
      images: pickerImages,
    };
    pickerSlides.push(pickerSlide);
  }

  const album: SkeletonImageAlbum = {
    album_id: carousel.id,
    name: carousel.name,
    slug: carousel.slug,
    asset_refs: assetRefs,
    slides: pickerSlides,
  };

  return album;
}

/**
 * Return the album that already contains this stored path.
 *
 * @param albums - Albums loaded from Carousels
 * @param assetRef - Concrete path stored on the skeleton
 * @returns The matching album, or null when the path is outside every album
 */
export function albumForAssetRef(
  albums: readonly SkeletonImageAlbum[],
  assetRef: string,
): SkeletonImageAlbum | null {

  const match: SkeletonImageAlbum | undefined = albums.find(
    (album: SkeletonImageAlbum): boolean => album.asset_refs.includes(assetRef),
  );

  return match ?? null;
}

/**
 * The seeded Default album, by slug or by the old catalog id.
 *
 * @param albums - Albums loaded from Carousels
 * @returns Default, or undefined when it is absent
 */
export function findDefaultAlbum(
  albums: readonly SkeletonImageAlbum[],
): SkeletonImageAlbum | undefined {

  const defaultAlbum: SkeletonImageAlbum | undefined = albums.find(
    (album: SkeletonImageAlbum): boolean => (
      album.slug === DEFAULT_ALBUM_ID || album.album_id === DEFAULT_ALBUM_ID
    ),
  );

  return defaultAlbum;
}

/**
 * Pick one concrete path from an album.
 *
 * ``exclude`` is skipped when another file exists, so Shuffle changes the
 * stored path. The same ``randomSlide`` and album always return the same path.
 *
 * @param assetRefs - Concrete paths in one album
 * @param exclude - Stored path to avoid, or null
 * @param randomSlide - Number in ``[0, 1)``
 * @returns A path from ``assetRefs``
 */
export function chooseAlbumAssetRef(
  assetRefs: readonly string[],
  exclude: string | null,
  randomSlide: number,
): string {

  const differentRefs: string[] = assetRefs.filter(
    (assetRef: string): boolean => assetRef !== exclude,
  );
  const choices: readonly string[] = differentRefs.length > 0 ? differentRefs : assetRefs;

  if (choices.length === 0) {
    throw new Error("Album has no images.");
  }

  const scaledIndex: number = Math.floor(randomSlide * choices.length);
  const boundedIndex: number = Math.min(choices.length - 1, Math.max(0, scaledIndex));
  const chosenRef: string | undefined = choices[boundedIndex];

  if (chosenRef === undefined) {
    throw new Error("Album has no images.");
  }

  return chosenRef;
}

/**
 * Keep the stored path when it is already in the album. Otherwise pick once.
 *
 * @param album - Album the operator selected
 * @param currentAssetRef - Path currently stored on the draft
 * @param randomSlide - Number in ``[0, 1)``
 * @returns The path to store
 */
export function assetRefForAlbumChoice(
  album: SkeletonImageAlbum,
  currentAssetRef: string,
  randomSlide: number,
): string {

  if (album.asset_refs.includes(currentAssetRef)) {
    return currentAssetRef;
  }

  const chosenRef: string = chooseAlbumAssetRef(album.asset_refs, null, randomSlide);

  return chosenRef;
}

/**
 * Pick a different file from the album the Shuffle button should use.
 *
 * A saved path outside the albums shuffles the Default album.
 *
 * @param albums - Albums from Carousels
 * @param selectValue - Current dropdown value
 * @param currentAssetRef - Path currently stored
 * @param randomSlide - Number in ``[0, 1)``
 * @returns The next stored path, or null when that album has no files
 */
export function assetRefAfterShuffle(
  albums: readonly SkeletonImageAlbum[],
  selectValue: string,
  currentAssetRef: string,
  randomSlide: number,
): string | null {

  const selectedAlbum: SkeletonImageAlbum | undefined = selectValue === SAVED_ASSET_OPTION
    ? undefined
    : albums.find((album: SkeletonImageAlbum): boolean => album.album_id === selectValue);
  const album: SkeletonImageAlbum | undefined = selectedAlbum ?? findDefaultAlbum(albums);

  if (album === undefined || album.asset_refs.length === 0) {
    return null;
  }

  const chosenRef: string = chooseAlbumAssetRef(album.asset_refs, currentAssetRef, randomSlide);

  return chosenRef;
}

/**
 * Pick one concrete path from the Default album for a new image element.
 *
 * @param albums - Albums from Carousels
 * @param randomSlide - Number in ``[0, 1)``
 * @returns A stored path from Default
 */
export function pickDefaultAlbumImage(
  albums: readonly SkeletonImageAlbum[],
  randomSlide: number,
): string {

  const defaultAlbum: SkeletonImageAlbum | undefined = findDefaultAlbum(albums);

  if (defaultAlbum === undefined || defaultAlbum.asset_refs.length === 0) {
    throw new Error("Default album has no images.");
  }

  const chosenRef: string = chooseAlbumAssetRef(defaultAlbum.asset_refs, null, randomSlide);

  return chosenRef;
}
