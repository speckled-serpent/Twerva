import type {
  SourceReadResponse,
  UnitFieldReadResponse,
  UnitImageReadResponse,
  UnitReadResponse,
} from "../api/types";

export const DEFAULT_ALBUM_ID: string = "default";
export const SAVED_ASSET_OPTION: string = "__saved__";

export interface ThemePickerImage {
  imageId: string;
  unitId: string;
  relativePath: string;
  hasThumbnail: boolean;
}

export interface ThemePickerUnit {
  unitId: string;
  caption: string;
  images: ThemePickerImage[];
}

export interface ThemeImageAlbum {
  album_id: string;
  name: string;
  slug: string;
  asset_refs: string[];
  units: ThemePickerUnit[];
}

/**
 * Caption beside a unit's images. Free text wins. Otherwise the first field.
 * The caption is not stored on the theme.
 *
 * @param freeText - Unit free text
 * @param firstFieldValue - Value of the first field, or null
 * @returns Display text, possibly empty
 */
export function captionForUnit(freeText: string | null, firstFieldValue: string | null): string {

  const trimmedFreeText: string = (freeText ?? "").trim();

  if (trimmedFreeText !== "") {
    return trimmedFreeText;
  }

  const trimmedField: string = (firstFieldValue ?? "").trim();

  return trimmedField;
}

/**
 * Albums for the theme picker. Text-only units are omitted.
 *
 * @param source - Album detail from `GET /api/v1/sources/{id}`
 * @returns One album and the image units inside it
 */
export function themeAlbumFromSource(source: SourceReadResponse): ThemeImageAlbum {

  const orderedUnits: UnitReadResponse[] = [...source.units].sort(
    (left: UnitReadResponse, right: UnitReadResponse): number => left.position - right.position,
  );
  const pickerUnits: ThemePickerUnit[] = [];
  const assetRefs: string[] = [];

  for (const unit of orderedUnits) {
    const orderedImages: UnitImageReadResponse[] = [...unit.images].sort(
      (left: UnitImageReadResponse, right: UnitImageReadResponse): number => (
        left.position - right.position
      ),
    );

    if (orderedImages.length === 0) {
      continue;
    }

    const orderedFields: UnitFieldReadResponse[] = [...unit.fields].sort(
      (left: UnitFieldReadResponse, right: UnitFieldReadResponse): number => (
        left.position - right.position
      ),
    );
    const firstFieldValue: string | null = orderedFields[0]?.value ?? null;
    const pickerImages: ThemePickerImage[] = orderedImages.map((image) => {
      assetRefs.push(image.relative_path);

      const pickerImage: ThemePickerImage = {
        imageId: image.id,
        unitId: unit.id,
        relativePath: image.relative_path,
        hasThumbnail: image.thumbnail_path !== null && image.thumbnail_path !== "",
      };

      return pickerImage;
    });
    const pickerUnit: ThemePickerUnit = {
      unitId: unit.id,
      caption: captionForUnit(unit.free_text, firstFieldValue),
      images: pickerImages,
    };
    pickerUnits.push(pickerUnit);
  }

  const album: ThemeImageAlbum = {
    album_id: source.id,
    name: source.name,
    slug: source.slug,
    asset_refs: assetRefs,
    units: pickerUnits,
  };

  return album;
}

/**
 * Return the album that already contains this stored path.
 *
 * @param albums - Albums loaded from Sources
 * @param assetRef - Concrete path stored on the theme
 * @returns The matching album, or null when the path is outside every album
 */
export function albumForAssetRef(
  albums: readonly ThemeImageAlbum[],
  assetRef: string,
): ThemeImageAlbum | null {

  const match: ThemeImageAlbum | undefined = albums.find(
    (album: ThemeImageAlbum): boolean => album.asset_refs.includes(assetRef),
  );

  return match ?? null;
}

/**
 * The seeded Default album, by slug or by the old catalog id.
 *
 * @param albums - Albums loaded from Sources
 * @returns Default, or undefined when it is absent
 */
export function findDefaultAlbum(
  albums: readonly ThemeImageAlbum[],
): ThemeImageAlbum | undefined {

  const defaultAlbum: ThemeImageAlbum | undefined = albums.find(
    (album: ThemeImageAlbum): boolean => (
      album.slug === DEFAULT_ALBUM_ID || album.album_id === DEFAULT_ALBUM_ID
    ),
  );

  return defaultAlbum;
}

/**
 * Pick one concrete path from an album.
 *
 * ``exclude`` is skipped when another file exists, so Shuffle changes the
 * stored path. The same ``randomUnit`` and album always return the same path.
 *
 * @param assetRefs - Concrete paths in one album
 * @param exclude - Stored path to avoid, or null
 * @param randomUnit - Number in ``[0, 1)``
 * @returns A path from ``assetRefs``
 */
export function chooseAlbumAssetRef(
  assetRefs: readonly string[],
  exclude: string | null,
  randomUnit: number,
): string {

  const differentRefs: string[] = assetRefs.filter(
    (assetRef: string): boolean => assetRef !== exclude,
  );
  const choices: readonly string[] = differentRefs.length > 0 ? differentRefs : assetRefs;

  if (choices.length === 0) {
    throw new Error("Album has no images.");
  }

  const scaledIndex: number = Math.floor(randomUnit * choices.length);
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
 * @param randomUnit - Number in ``[0, 1)``
 * @returns The path to store
 */
export function assetRefForAlbumChoice(
  album: ThemeImageAlbum,
  currentAssetRef: string,
  randomUnit: number,
): string {

  if (album.asset_refs.includes(currentAssetRef)) {
    return currentAssetRef;
  }

  const chosenRef: string = chooseAlbumAssetRef(album.asset_refs, null, randomUnit);

  return chosenRef;
}

/**
 * Pick a different file from the album the Shuffle button should use.
 *
 * A saved path outside the albums shuffles the Default album.
 *
 * @param albums - Albums from Sources
 * @param selectValue - Current dropdown value
 * @param currentAssetRef - Path currently stored
 * @param randomUnit - Number in ``[0, 1)``
 * @returns The next stored path, or null when that album has no files
 */
export function assetRefAfterShuffle(
  albums: readonly ThemeImageAlbum[],
  selectValue: string,
  currentAssetRef: string,
  randomUnit: number,
): string | null {

  const selectedAlbum: ThemeImageAlbum | undefined = selectValue === SAVED_ASSET_OPTION
    ? undefined
    : albums.find((album: ThemeImageAlbum): boolean => album.album_id === selectValue);
  const album: ThemeImageAlbum | undefined = selectedAlbum ?? findDefaultAlbum(albums);

  if (album === undefined || album.asset_refs.length === 0) {
    return null;
  }

  const chosenRef: string = chooseAlbumAssetRef(album.asset_refs, currentAssetRef, randomUnit);

  return chosenRef;
}

/**
 * Pick one concrete path from the Default album for a new image element.
 *
 * @param albums - Albums from Sources
 * @param randomUnit - Number in ``[0, 1)``
 * @returns A stored path from Default
 */
export function pickDefaultAlbumImage(
  albums: readonly ThemeImageAlbum[],
  randomUnit: number,
): string {

  const defaultAlbum: ThemeImageAlbum | undefined = findDefaultAlbum(albums);

  if (defaultAlbum === undefined || defaultAlbum.asset_refs.length === 0) {
    throw new Error("Default album has no images.");
  }

  const chosenRef: string = chooseAlbumAssetRef(defaultAlbum.asset_refs, null, randomUnit);

  return chosenRef;
}
