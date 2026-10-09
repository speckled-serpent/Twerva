export const DEFAULT_ALBUM_ID: string = "default";
export const SAVED_ASSET_OPTION: string = "__saved__";

export interface ThemeImageAlbum {
  album_id: string;
  name: string;
  asset_refs: string[];
}

/**
 * Return the album that already contains this stored path.
 *
 * @param albums - Albums from the default-images API
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
 * @param albums - Albums from the API
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
  const defaultAlbum: ThemeImageAlbum | undefined = albums.find(
    (album: ThemeImageAlbum): boolean => album.album_id === DEFAULT_ALBUM_ID,
  );
  const album: ThemeImageAlbum | undefined = selectedAlbum ?? defaultAlbum;

  if (album === undefined || album.asset_refs.length === 0) {
    return null;
  }

  const chosenRef: string = chooseAlbumAssetRef(album.asset_refs, currentAssetRef, randomUnit);

  return chosenRef;
}
