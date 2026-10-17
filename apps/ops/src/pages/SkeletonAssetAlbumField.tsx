import { useEffect, useState, type ReactElement } from "react";

import {
  albumImageFileUrl,
  albumImageThumbnailUrl,
  fetchAlbumById,
  listAlbums,
} from "../api/client";
import type { AlbumListItemResponse, AlbumReadResponse } from "../api/types";
import {
  SAVED_ASSET_OPTION,
  albumForAssetRef,
  assetRefAfterShuffle,
  assetRefForAlbumChoice,
  findDefaultAlbum,
  skeletonAlbumFromAlbum,
  type SkeletonImageAlbum,
  type SkeletonPickerImage,
  type SkeletonPickerSlide,
} from "./skeletonAssets";

export interface SkeletonAssetAlbumFieldProps {
  idPrefix: string;
  label: string;
  assetRef: string;
  onAssetRefChange: (nextAssetRef: string) => void;
  disabled: boolean;
}

let albumsPromise: Promise<SkeletonImageAlbum[]> | null = null;

/**
 * Load every album. A later visit fetches again so a new album shows up.
 * A failed request can be tried again.
 *
 * @returns Albums from the library
 */
export function loadSkeletonPickerAlbums(): Promise<SkeletonImageAlbum[]> {

  if (albumsPromise !== null) {
    return albumsPromise;
  }

  const pendingAlbums: Promise<SkeletonImageAlbum[]> = listAlbums()
    .then(async (listedAlbums: AlbumListItemResponse[]): Promise<SkeletonImageAlbum[]> => {
      const details: AlbumReadResponse[] = await Promise.all(
        listedAlbums.map((listedAlbum: AlbumListItemResponse): Promise<AlbumReadResponse> => (
          fetchAlbumById(listedAlbum.id)
        )),
      );
      const pickerAlbums: SkeletonImageAlbum[] = details.map(skeletonAlbumFromAlbum);

      albumsPromise = null;

      return pickerAlbums;
    })
    .catch((caughtError: unknown): never => {
      albumsPromise = null;

      throw caughtError;
    });
  albumsPromise = pendingAlbums;

  return pendingAlbums;
}

/**
 * Album, then thumbnails, for a picture background or an image element.
 *
 * Choosing a thumbnail stores that file's path. Shuffle stores a different
 * path from the same album once. A path outside every album stays
 * "Saved image" until the operator replaces it. There is no upload here.
 *
 * @param props - Ids, label, stored path, change handler, and disabled flag
 * @returns The album control
 */
export function SkeletonAssetAlbumField({
  idPrefix,
  label,
  assetRef,
  onAssetRefChange,
  disabled,
}: SkeletonAssetAlbumFieldProps): ReactElement {

  const [albums, setAlbums] = useState<SkeletonImageAlbum[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [emptyBrowseId, setEmptyBrowseId] = useState<string | null>(null);
  const matchedAlbum: SkeletonImageAlbum | null = albumForAssetRef(albums, assetRef);
  const defaultAlbum: SkeletonImageAlbum | undefined = findDefaultAlbum(albums);
  const selectValue: string = emptyBrowseId
    ?? matchedAlbum?.album_id
    ?? (assetRef.trim() === ""
      ? (defaultAlbum?.album_id ?? albums[0]?.album_id ?? "")
      : SAVED_ASSET_OPTION);
  const browsedAlbum: SkeletonImageAlbum | undefined = albums.find(
    (album: SkeletonImageAlbum): boolean => album.album_id === selectValue,
  );
  const shuffleAlbum: SkeletonImageAlbum | undefined = selectValue === SAVED_ASSET_OPTION
    ? defaultAlbum
    : browsedAlbum;

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    loadSkeletonPickerAlbums()
      .then((loadedAlbums: SkeletonImageAlbum[]): void => {
        if (!isCancelled) {
          setAlbums(loadedAlbums);
          setLoadError(null);
        }
      })
      .catch((caughtError: unknown): void => {
        if (!isCancelled) {
          const message: string = caughtError instanceof Error
            ? caughtError.message
            : "Couldn't load albums.";
          setLoadError(message);
        }
      });

    return (): void => {
      isCancelled = true;
    };
  }, []);

  useEffect((): void => {
    if (assetRef.trim() !== "") {
      return;
    }

    if (defaultAlbum === undefined || defaultAlbum.asset_refs.length === 0) {
      return;
    }

    const chosenRef: string = assetRefForAlbumChoice(defaultAlbum, "", Math.random());
    onAssetRefChange(chosenRef);
  }, [albums, assetRef, defaultAlbum, onAssetRefChange]);

  const hint: string = assetHint(assetRef, matchedAlbum !== null, browsedAlbum);

  return (
    <>
      <div className="asset-album-row">
        <label>
          {label}
          <select
            id={`${idPrefix}-album`}
            value={selectValue}
            disabled={disabled || albums.length === 0}
            onChange={(changeEvent): void => {
              const nextAlbumId: string = changeEvent.target.value;

              if (nextAlbumId === SAVED_ASSET_OPTION) {
                return;
              }

              const nextAlbum: SkeletonImageAlbum | undefined = albums.find(
                (album: SkeletonImageAlbum): boolean => album.album_id === nextAlbumId,
              );

              if (nextAlbum === undefined) {
                return;
              }

              if (nextAlbum.asset_refs.length === 0) {
                setEmptyBrowseId(nextAlbum.album_id);

                return;
              }

              setEmptyBrowseId(null);
              onAssetRefChange(assetRefForAlbumChoice(nextAlbum, assetRef, Math.random()));
            }}
          >
            {selectValue === SAVED_ASSET_OPTION ? (
              <option value={SAVED_ASSET_OPTION}>Saved image</option>
            ) : null}
            {albums.map((album: SkeletonImageAlbum): ReactElement => (
              <option key={album.album_id} value={album.album_id}>
                {album.name}
              </option>
            ))}
          </select>
        </label>
        <button
          id={`${idPrefix}-shuffle`}
          type="button"
          className="asset-shuffle-button"
          disabled={disabled || shuffleAlbum === undefined || shuffleAlbum.asset_refs.length < 1}
          onClick={(): void => {
            const nextRef: string | null = assetRefAfterShuffle(
              albums,
              selectValue,
              assetRef,
              Math.random(),
            );

            if (nextRef !== null) {
              setEmptyBrowseId(null);
              onAssetRefChange(nextRef);
            }
          }}
        >
          Shuffle
        </button>
      </div>
      {loadError !== null ? <p className="field-hint">{loadError}</p> : null}
      {loadError === null && albums.length === 0 ? (
        <p className="field-hint">Loading albums.</p>
      ) : null}
      {browsedAlbum !== undefined && browsedAlbum.slides.length === 0 ? (
        <p className="field-hint">This album has no images.</p>
      ) : null}
      {browsedAlbum !== undefined && browsedAlbum.slides.length > 0 ? (
        <div className="asset-picker" id={`${idPrefix}-images`}>
          {browsedAlbum.slides.map((slide: SkeletonPickerSlide): ReactElement => (
            <div key={slide.slideId} className="asset-picker-slide">
              {slide.caption !== "" ? (
                <p className="asset-picker-caption">{slide.caption}</p>
              ) : null}
              <div className="asset-picker-thumbs">
                {slide.images.map((image: SkeletonPickerImage): ReactElement => (
                  <button
                    key={image.imageId}
                    type="button"
                    className={image.relativePath === assetRef ? "asset-thumb is-selected" : "asset-thumb"}
                    data-asset-ref={image.relativePath}
                    disabled={disabled}
                    onClick={(): void => {
                      setEmptyBrowseId(null);
                      onAssetRefChange(image.relativePath);
                    }}
                  >
                    <img
                      src={displayUrl(browsedAlbum.album_id, image)}
                      alt={slide.caption === "" ? image.relativePath : slide.caption}
                    />
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : null}
      {albums.length > 0 ? <p className="field-hint" id={`${idPrefix}-hint`}>{hint}</p> : null}
    </>
  );
}

function displayUrl(albumId: string, image: SkeletonPickerImage): string {

  if (image.hasThumbnail) {
    return albumImageThumbnailUrl(albumId, image.imageId);
  }

  return albumImageFileUrl(albumId, image.imageId);
}

function assetHint(
  assetRef: string,
  inAlbum: boolean,
  browsedAlbum: SkeletonImageAlbum | undefined,
): string {

  const trimmedRef: string = assetRef.trim();

  if (trimmedRef === "") {
    return "Choosing an album stores one image from it.";
  }

  if (inAlbum) {
    const albumName: string = browsedAlbum?.name ?? "this album";

    return `Stored as ${trimmedRef}. Shuffle picks a different image in ${albumName}.`;
  }

  return `Stored as ${trimmedRef}. This file is outside the albums. Choosing an album replaces it.`;
}
