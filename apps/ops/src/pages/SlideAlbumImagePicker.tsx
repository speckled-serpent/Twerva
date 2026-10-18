import { useEffect, useState, type ReactElement } from "react";

import { albumImageDisplayUrl, fetchAlbumById } from "../api/client";
import type { AlbumImageReadResponse, AlbumReadResponse } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import {
  SLIDE_ALBUM_EMPTY_COPY,
  SLIDE_ALBUM_MISSING_COPY,
  SLIDE_ALBUM_PICK_HINT,
  SLIDE_ALBUM_READONLY_COPY,
  albumImagesInPositionOrder,
} from "./slideAlbumImage";

export interface SlideAlbumImagePickerProps {
  albumId: string | null;
  selectedImageId: string | null;
  canWrite: boolean;
  isChoosing: boolean;
  isLocked: boolean;
  onChoose: (albumImageId: string) => void;
  onOpenContent: () => void;
}

/**
 * Album images the operator can store on this slide.
 *
 * Shown only when the skeleton uses a slide image. Choosing one calls
 * `onChoose`. A reader sees the same images and cannot change the choice.
 * An empty album points at Content, where images are added.
 *
 * @param props - The carousel's album and the current choice
 * @returns The image section on the slide editor
 */
export function SlideAlbumImagePicker({
  albumId,
  selectedImageId,
  canWrite,
  isChoosing,
  isLocked,
  onChoose,
  onOpenContent,
}: SlideAlbumImagePickerProps): ReactElement {

  const [trackedAlbumId, setTrackedAlbumId] = useState<string | null>(albumId);
  const [album, setAlbum] = useState<AlbumReadResponse | null>(null);
  const [albumError, setAlbumError] = useState<unknown>(null);
  const [albumReady, setAlbumReady] = useState<boolean>(albumId === null);

  if (albumId !== trackedAlbumId) {
    setTrackedAlbumId(albumId);
    setAlbum(null);
    setAlbumError(null);
    setAlbumReady(albumId === null);
  }

  useEffect((): (() => void) => {
    if (albumId === null) {
      return (): void => {
        return;
      };
    }

    let isCancelled: boolean = false;

    const loadAlbum = async (): Promise<void> => {

      try {
        const loadedAlbum: AlbumReadResponse = await fetchAlbumById(albumId);

        if (isCancelled) {
          return;
        }

        setAlbum(loadedAlbum);
        setAlbumError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setAlbum(null);
        setAlbumError(caughtError);
      } finally {
        if (!isCancelled) {
          setAlbumReady(true);
        }
      }
    };

    void loadAlbum();

    return (): void => {
      isCancelled = true;
    };
  }, [albumId]);

  const albumImages: AlbumImageReadResponse[] = album === null || album.id !== albumId
    ? []
    : albumImagesInPositionOrder(album.images);
  const hint: string = canWrite ? SLIDE_ALBUM_PICK_HINT : SLIDE_ALBUM_READONLY_COPY;

  return (
    <section id="slide-images" className="slide-images" aria-label="Image">
      <h2>Image</h2>
      <p className="field-hint" id="slide-album-hint">{hint}</p>
      <ErrorBanner error={albumError} />
      {isChoosing ? <p className="field-hint" id="slide-album-saving">Saving the image…</p> : null}
      {albumId === null ? (
        <AlbumImagePointer
          copy={SLIDE_ALBUM_MISSING_COPY}
          onOpenContent={onOpenContent}
        />
      ) : !albumReady ? (
        <p>Loading album…</p>
      ) : albumError !== null ? null : albumImages.length === 0 ? (
        <AlbumImagePointer
          copy={SLIDE_ALBUM_EMPTY_COPY}
          onOpenContent={onOpenContent}
        />
      ) : (
        <div
          className="asset-picker"
          id="slide-album-picker"
          role="group"
          aria-label="Album images"
        >
          <div className="asset-picker-thumbs">
            {albumImages.map((image: AlbumImageReadResponse): ReactElement => {
              const isSelected: boolean = image.id === selectedImageId;
              const thumbClassName: string = isSelected
                ? "asset-thumb is-selected"
                : "asset-thumb";
              const choiceLocked: boolean = !canWrite || isChoosing || isLocked;

              return (
                <button
                  key={image.id}
                  id={`slide-album-image-${image.id}`}
                  type="button"
                  className={thumbClassName}
                  aria-pressed={isSelected}
                  disabled={choiceLocked}
                  onClick={(): void => {
                    if (choiceLocked || isSelected) {
                      return;
                    }

                    onChoose(image.id);
                  }}
                >
                  <img
                    src={albumImageDisplayUrl(albumId, image)}
                    alt={image.alt_text ?? "Album image"}
                  />
                </button>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}

interface AlbumImagePointerProps {
  copy: string;
  onOpenContent: () => void;
}

function AlbumImagePointer({
  copy,
  onOpenContent,
}: AlbumImagePointerProps): ReactElement {

  return (
    <>
      <p id="slide-album-empty">{copy}</p>
      <div className="button-row">
        <button id="slide-album-open-content" type="button" onClick={onOpenContent}>
          Open Content
        </button>
      </div>
    </>
  );
}
