import { useEffect, useState, type ReactElement } from "react";

import { fetchThemeDefaultImages } from "../api/client";
import type { ThemeDefaultImagesResponse } from "../api/types";
import {
  DEFAULT_ALBUM_ID,
  SAVED_ASSET_OPTION,
  albumForAssetRef,
  assetRefAfterShuffle,
  assetRefForAlbumChoice,
  type ThemeImageAlbum,
} from "./themeAssets";

export interface ThemeAssetAlbumFieldProps {
  label: string;
  assetRef: string;
  onAssetRefChange: (nextAssetRef: string) => void;
  disabled: boolean;
}

let albumsPromise: Promise<ThemeImageAlbum[]> | null = null;

/**
 * Load bundled albums once. A failed request can be tried again.
 *
 * @returns Albums from `GET /api/v1/themes/default-images`
 */
function loadThemeImageAlbums(): Promise<ThemeImageAlbum[]> {

  if (albumsPromise !== null) {
    return albumsPromise;
  }

  const pendingAlbums: Promise<ThemeImageAlbum[]> = fetchThemeDefaultImages()
    .then((response: ThemeDefaultImagesResponse): ThemeImageAlbum[] => response.albums)
    .catch((caughtError: unknown): never => {
      albumsPromise = null;

      throw caughtError;
    });
  albumsPromise = pendingAlbums;

  return pendingAlbums;
}

/**
 * Album dropdown for a picture background or an image element.
 *
 * Default is the only album today. Choosing it stores one concrete path
 * and does not draw again until Shuffle. A path outside the albums stays
 * selected as "Saved image" until the operator replaces it.
 *
 * @param props - Label, stored path, change handler, and disabled flag
 * @returns The album control
 */
export function ThemeAssetAlbumField({
  label,
  assetRef,
  onAssetRefChange,
  disabled,
}: ThemeAssetAlbumFieldProps): ReactElement {

  const [albums, setAlbums] = useState<ThemeImageAlbum[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const matchedAlbum: ThemeImageAlbum | null = albumForAssetRef(albums, assetRef);
  const selectValue: string = matchedAlbum !== null
    ? matchedAlbum.album_id
    : assetRef.trim() === ""
      ? DEFAULT_ALBUM_ID
      : SAVED_ASSET_OPTION;
  const albumOptions: ThemeImageAlbum[] = albums.length > 0
    ? albums
    : [{ album_id: DEFAULT_ALBUM_ID, name: "Default", asset_refs: [] }];

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    loadThemeImageAlbums()
      .then((loadedAlbums: ThemeImageAlbum[]): void => {
        if (!isCancelled) {
          setAlbums(loadedAlbums);
          setLoadError(null);
        }
      })
      .catch((caughtError: unknown): void => {
        if (!isCancelled) {
          const message: string = caughtError instanceof Error
            ? caughtError.message
            : "Couldn't load default images.";
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

    const defaultAlbum: ThemeImageAlbum | undefined = albums.find(
      (album: ThemeImageAlbum): boolean => album.album_id === DEFAULT_ALBUM_ID,
    );

    if (defaultAlbum === undefined || defaultAlbum.asset_refs.length === 0) {
      return;
    }

    const chosenRef: string = assetRefForAlbumChoice(defaultAlbum, "", Math.random());
    onAssetRefChange(chosenRef);
  }, [albums, assetRef, onAssetRefChange]);

  const hint: string = assetHint(assetRef, matchedAlbum !== null);

  return (
    <>
      <div className="asset-album-row">
        <label>
          {label}
          <select
            value={selectValue}
            disabled={disabled}
            onChange={(changeEvent): void => {
              const nextAlbumId: string = changeEvent.target.value;

              if (nextAlbumId === SAVED_ASSET_OPTION) {
                return;
              }

              const nextAlbum: ThemeImageAlbum | undefined = albums.find(
                (album: ThemeImageAlbum): boolean => album.album_id === nextAlbumId,
              );

              if (nextAlbum === undefined) {
                return;
              }

              onAssetRefChange(assetRefForAlbumChoice(nextAlbum, assetRef, Math.random()));
            }}
          >
            {selectValue === SAVED_ASSET_OPTION ? (
              <option value={SAVED_ASSET_OPTION}>Saved image</option>
            ) : null}
            {albumOptions.map((album: ThemeImageAlbum): ReactElement => (
              <option key={album.album_id} value={album.album_id}>
                {album.name}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="asset-shuffle-button"
          disabled={disabled || albums.length === 0}
          onClick={(): void => {
            const nextRef: string | null = assetRefAfterShuffle(
              albums,
              selectValue,
              assetRef,
              Math.random(),
            );

            if (nextRef !== null) {
              onAssetRefChange(nextRef);
            }
          }}
        >
          Shuffle
        </button>
      </div>
      {loadError !== null ? <p className="field-hint">{loadError}</p> : null}
      {loadError === null && albums.length === 0 ? (
        <p className="field-hint">Loading default images.</p>
      ) : null}
      {albums.length > 0 ? <p className="field-hint">{hint}</p> : null}
    </>
  );
}

function assetHint(assetRef: string, inAlbum: boolean): string {

  const trimmedRef: string = assetRef.trim();

  if (trimmedRef === "") {
    return "Default picks one bundled image and keeps that file.";
  }

  if (inAlbum) {
    return `Stored as ${trimmedRef}. Shuffle picks a different default image.`;
  }

  return `Stored as ${trimmedRef}. This file is outside the albums. Choosing Default replaces it.`;
}
