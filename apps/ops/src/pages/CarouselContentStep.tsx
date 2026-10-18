import { useEffect, useState, type FormEvent, type ReactElement } from "react";

import {
  attachCarouselAlbum,
  clearCarouselAlbum,
  createCarouselAlbum,
  fetchSkeletonById,
  listAlbums,
} from "../api/client";
import type {
  AlbumListItemResponse,
  AlbumReadResponse,
  CarouselReadResponse,
  SkeletonReadResponse,
} from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { AlbumImagesEditor, type AlbumEditorActions } from "./AlbumImagesEditor";
import {
  ALBUM_HAS_NO_IMAGES_COPY,
  ALBUM_IMAGES_AUTOSAVE_COPY,
  ALBUM_IMAGES_READONLY_COPY,
  ALBUM_NAME_REQUIRED_COPY,
  albumActionErrorText,
  albumImageCountLabel,
  albumsToChoose,
  detachedAlbumCopy,
  visibleAlbumImageCount,
  visibleAlbumName,
} from "./carouselContent";
import { skeletonRequiresImage } from "./slideSkeletonShape";

export interface CarouselContentStepProps {
  carousel: CarouselReadResponse;
  canWrite: boolean;
  onCarouselSaved: (savedCarousel: CarouselReadResponse) => void;
  onAlbumEditorActions?: (actions: AlbumEditorActions | null) => void;
}

/**
 * Step 2: attach an existing album, or create one by name, then edit its images.
 *
 * The attached album shows its name and image count. Replace and clear
 * stay on this step. A 409 shows the API reason in the form and leaves
 * the album attached. Images are the album's own rows: add, URL import,
 * reorder, and the license fields. A reader can look and cannot attach
 * or change those images.
 *
 * @param props - The open carousel and the write callback
 * @returns The Content step
 */
export function CarouselContentStep({
  carousel,
  canWrite,
  onCarouselSaved,
  onAlbumEditorActions,
}: CarouselContentStepProps): ReactElement {

  const [trackedCarouselId, setTrackedCarouselId] = useState<string>(carousel.id);
  const [albums, setAlbums] = useState<AlbumListItemResponse[] | null>(null);
  const [albumError, setAlbumError] = useState<unknown>(null);
  const [skeleton, setSkeleton] = useState<SkeletonReadResponse | null>(null);
  const [skeletonError, setSkeletonError] = useState<unknown>(null);
  const [selectedAlbumId, setSelectedAlbumId] = useState<string>("");
  const [newAlbumName, setNewAlbumName] = useState<string>("");
  const [isReplacing, setIsReplacing] = useState<boolean>(false);
  const [isWorking, setIsWorking] = useState<boolean>(false);
  const [imagesBusy, setImagesBusy] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [loadedAlbum, setLoadedAlbum] = useState<AlbumReadResponse | null>(null);

  if (carousel.id !== trackedCarouselId) {
    setTrackedCarouselId(carousel.id);
    setAlbums(null);
    setSkeleton(null);
    setSelectedAlbumId("");
    setNewAlbumName("");
    setIsReplacing(false);
    setFormError(null);
    setLoadedAlbum(null);
    setImagesBusy(false);
  }

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadAlbums = async (): Promise<void> => {

      try {
        const loadedAlbums: AlbumListItemResponse[] = await listAlbums();

        if (isCancelled) {
          return;
        }

        setAlbums(loadedAlbums);
        setAlbumError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setAlbums([]);
        setAlbumError(caughtError);
      }
    };

    void loadAlbums();

    return (): void => {
      isCancelled = true;
    };
  }, [carousel.id, carousel.album_id]);

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;
    const skeletonId: string = carousel.skeleton_id;

    const loadSkeleton = async (): Promise<void> => {

      try {
        const loadedSkeleton: SkeletonReadResponse = await fetchSkeletonById(skeletonId);

        if (isCancelled) {
          return;
        }

        setSkeleton(loadedSkeleton);
        setSkeletonError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setSkeleton(null);
        setSkeletonError(caughtError);
      }
    };

    void loadSkeleton();

    return (): void => {
      isCancelled = true;
    };
  }, [carousel.skeleton_id]);

  const attachedAlbum: AlbumListItemResponse | null = findAttachedAlbum(
    albums,
    carousel.album_id,
  );
  const albumDetail: AlbumReadResponse | null = loadedAlbum !== null
    && loadedAlbum.id === carousel.album_id
    ? loadedAlbum
    : null;
  const albumName: string | null = visibleAlbumName(
    albumDetail?.name ?? null,
    attachedAlbum?.name ?? null,
  );
  const imageCount: number | null = visibleAlbumImageCount(
    albumDetail === null ? null : albumDetail.images.length,
    attachedAlbum === null ? null : attachedAlbum.image_count,
  );
  const albumChangeLocked: boolean = isWorking || imagesBusy;
  const showChooser: boolean = canWrite && (carousel.album_id === null || isReplacing);
  const choiceAlbums: AlbumListItemResponse[] = albumsToChoose(
    albums ?? [],
    carousel.album_id,
    isReplacing,
  );

  const handleAttach = async (): Promise<void> => {

    if (!canWrite || albumChangeLocked || selectedAlbumId === "") {
      return;
    }

    setIsWorking(true);
    setFormError(null);

    try {
      const updatedCarousel: CarouselReadResponse = await attachCarouselAlbum(carousel.id, {
        album_id: selectedAlbumId,
      });
      const loadedAlbums: AlbumListItemResponse[] = await listAlbums();
      setAlbums(loadedAlbums);
      setSelectedAlbumId("");
      setIsReplacing(false);
      onCarouselSaved(updatedCarousel);
    } catch (caughtError: unknown) {
      setFormError(albumActionErrorText(caughtError));
    } finally {
      setIsWorking(false);
    }
  };

  const handleCreate = async (): Promise<void> => {

    if (!canWrite || albumChangeLocked) {
      return;
    }

    const albumName: string = newAlbumName.trim();

    if (albumName === "") {
      setFormError(ALBUM_NAME_REQUIRED_COPY);

      return;
    }

    setIsWorking(true);
    setFormError(null);

    try {
      const updatedCarousel: CarouselReadResponse = await createCarouselAlbum(carousel.id, {
        name: albumName,
      });
      const loadedAlbums: AlbumListItemResponse[] = await listAlbums();
      setAlbums(loadedAlbums);
      setNewAlbumName("");
      setIsReplacing(false);
      onCarouselSaved(updatedCarousel);
    } catch (caughtError: unknown) {
      setFormError(albumActionErrorText(caughtError));
    } finally {
      setIsWorking(false);
    }
  };

  const handleClear = async (): Promise<void> => {

    if (!canWrite || albumChangeLocked || carousel.album_id === null) {
      return;
    }

    setIsWorking(true);
    setFormError(null);

    try {
      const updatedCarousel: CarouselReadResponse = await clearCarouselAlbum(carousel.id);
      setIsReplacing(false);
      onCarouselSaved(updatedCarousel);
    } catch (caughtError: unknown) {
      setFormError(albumActionErrorText(caughtError));
    } finally {
      setIsWorking(false);
    }
  };

  return (
    <section id="carousel-content" className="carousel-content stack-form" aria-label="Content">
      <ErrorBanner error={skeletonError} />
      <ErrorBanner error={albumError} />
      <AlbumStatus
        carousel={carousel}
        albumName={albumName}
        imageCount={imageCount}
        albumsLoaded={albums !== null}
        albumError={albumError}
        skeleton={skeleton}
      />
      {carousel.album_id === null ? null : (
        <div className="carousel-album-images" id="carousel-album-images">
          <p className="field-hint" id="carousel-album-images-hint">
            {canWrite ? ALBUM_IMAGES_AUTOSAVE_COPY : ALBUM_IMAGES_READONLY_COPY}
          </p>
          <AlbumImagesEditor
            key={carousel.album_id}
            albumId={carousel.album_id}
            canWrite={canWrite}
            showName={false}
            onAlbumChange={setLoadedAlbum}
            onActions={onAlbumEditorActions}
            onBusyChange={setImagesBusy}
          />
        </div>
      )}
      {canWrite ? (
        <form
          id="carousel-album-form"
          className="carousel-album-form"
          onSubmit={(submitEvent: FormEvent<HTMLFormElement>): void => {
            submitEvent.preventDefault();

            if (newAlbumName.trim() !== "") {
              void handleCreate();

              return;
            }

            void handleAttach();
          }}
        >
          {carousel.album_id === null ? null : (
            <div className="button-row">
              {isReplacing ? null : (
                <button
                  id="carousel-album-replace"
                  type="button"
                  disabled={albumChangeLocked}
                  onClick={(): void => {
                    setIsReplacing(true);
                    setFormError(null);
                  }}
                >
                  Replace album
                </button>
              )}
              <button
                id="carousel-album-clear"
                type="button"
                disabled={albumChangeLocked}
                onClick={(): void => {
                  void handleClear();
                }}
              >
                Clear album
              </button>
            </div>
          )}
          {showChooser ? (
            <AlbumChooser
              albums={choiceAlbums}
              albumsLoaded={albums !== null}
              selectedAlbumId={selectedAlbumId}
              newAlbumName={newAlbumName}
              isReplacing={isReplacing}
              isWorking={isWorking}
              isLocked={albumChangeLocked}
              onSelectedAlbumId={setSelectedAlbumId}
              onNewAlbumName={setNewAlbumName}
              onAttach={(): void => {
                void handleAttach();
              }}
              onCreate={(): void => {
                void handleCreate();
              }}
              onCancel={(): void => {
                setIsReplacing(false);
                setSelectedAlbumId("");
                setFormError(null);
              }}
            />
          ) : null}
          {formError === null ? null : (
            <p className="field-error" id="carousel-album-error" role="alert">
              {formError}
            </p>
          )}
        </form>
      ) : (
        <p className="field-hint" id="carousel-album-readonly">
          Attaching an album is an admin action.
        </p>
      )}
    </section>
  );
}

interface AlbumStatusProps {
  carousel: CarouselReadResponse;
  albumName: string | null;
  imageCount: number | null;
  albumsLoaded: boolean;
  albumError: unknown;
  skeleton: SkeletonReadResponse | null;
}

function AlbumStatus({
  carousel,
  albumName,
  imageCount,
  albumsLoaded,
  albumError,
  skeleton,
}: AlbumStatusProps): ReactElement {

  return (
    <div className="carousel-attached-album" id="carousel-album-status">
      <p className="carousel-basic-kicker">Album</p>
      {albumStatusBody(carousel, albumName, imageCount, albumsLoaded, albumError, skeleton)}
    </div>
  );
}

function albumStatusBody(
  carousel: CarouselReadResponse,
  albumName: string | null,
  imageCount: number | null,
  albumsLoaded: boolean,
  albumError: unknown,
  skeleton: SkeletonReadResponse | null,
): ReactElement {

  if (albumName !== null && imageCount !== null) {
    return (
      <>
        <p id="carousel-album-name" className="carousel-album-name">
          {albumName}
        </p>
        <p id="carousel-album-image-count" className="carousel-album-count">
          {albumImageCountLabel(imageCount)}
        </p>
        {imageCount === 0 ? (
          <p id="carousel-album-no-images" className="carousel-album-note">
            {ALBUM_HAS_NO_IMAGES_COPY}
          </p>
        ) : null}
      </>
    );
  }

  if (carousel.album_id !== null && !albumsLoaded) {
    return (
      <p id="carousel-album-loading" className="carousel-album-note">
        Loading album…
      </p>
    );
  }

  if (carousel.album_id !== null && albumError !== null) {
    return (
      <p id="carousel-album-missing" className="carousel-album-note">
        The album list could not be loaded.
      </p>
    );
  }

  if (carousel.album_id !== null) {
    return (
      <p id="carousel-album-missing" className="carousel-album-note">
        This album is not available.
      </p>
    );
  }

  if (skeleton === null) {
    return (
      <p id="carousel-album-loading" className="carousel-album-note">
        Loading skeleton…
      </p>
    );
  }

  const emptyCopy: string = detachedAlbumCopy(skeletonRequiresImage(skeleton));
  const emptyCopyId: string = skeletonRequiresImage(skeleton)
    ? "carousel-album-required"
    : "carousel-album-optional";

  return (
    <p id={emptyCopyId} className="carousel-album-note">
      {emptyCopy}
    </p>
  );
}

interface AlbumChooserProps {
  albums: readonly AlbumListItemResponse[];
  albumsLoaded: boolean;
  selectedAlbumId: string;
  newAlbumName: string;
  isReplacing: boolean;
  isWorking: boolean;
  isLocked: boolean;
  onSelectedAlbumId: (albumId: string) => void;
  onNewAlbumName: (albumName: string) => void;
  onAttach: () => void;
  onCreate: () => void;
  onCancel: () => void;
}

function AlbumChooser({
  albums,
  albumsLoaded,
  selectedAlbumId,
  newAlbumName,
  isReplacing,
  isWorking,
  isLocked,
  onSelectedAlbumId,
  onNewAlbumName,
  onAttach,
  onCreate,
  onCancel,
}: AlbumChooserProps): ReactElement {

  const attachLabel: string = isReplacing ? "Replace album" : "Attach album";

  return (
    <>
      {isReplacing ? (
        <p className="field-hint" id="carousel-album-replace-hint">
          Choose another album, or create one by name. The current album stays until that succeeds.
        </p>
      ) : null}
      <label>
        Existing album
        <select
          id="carousel-album-select"
          value={selectedAlbumId}
          disabled={!albumsLoaded || isLocked || albums.length === 0}
          onChange={(changeEvent): void => {
            onSelectedAlbumId(changeEvent.target.value);
          }}
        >
          <option value="">Choose an album</option>
          {albums.map((album: AlbumListItemResponse): ReactElement => (
            <option key={album.id} value={album.id}>
              {album.name}
            </option>
          ))}
        </select>
      </label>
      {albumsLoaded && albums.length === 0 ? (
        <p className="field-hint" id="carousel-album-none">
          {isReplacing ? "No other albums yet." : "No albums yet."}
        </p>
      ) : null}
      <div className="button-row">
        <button
          id="carousel-album-attach"
          type="button"
          className="primary"
          disabled={isLocked || selectedAlbumId === ""}
          onClick={onAttach}
        >
          {isWorking ? "Saving…" : attachLabel}
        </button>
      </div>
      <label>
        New album name
        <input
          id="carousel-album-create-name"
          value={newAlbumName}
          disabled={isLocked}
          autoComplete="off"
          onChange={(changeEvent): void => {
            onNewAlbumName(changeEvent.target.value);
          }}
        />
      </label>
      <div className="button-row">
        <button
          id="carousel-album-create"
          type="button"
          className="primary"
          disabled={isLocked}
          onClick={onCreate}
        >
          {isWorking ? "Saving…" : "Create album"}
        </button>
        {isReplacing ? (
          <button
            id="carousel-album-cancel"
            type="button"
            disabled={isLocked}
            onClick={onCancel}
          >
            Cancel
          </button>
        ) : null}
      </div>
    </>
  );
}

function findAttachedAlbum(
  albums: readonly AlbumListItemResponse[] | null,
  albumId: string | null,
): AlbumListItemResponse | null {

  if (albums === null || albumId === null) {
    return null;
  }

  const foundAlbum: AlbumListItemResponse | undefined = albums.find(
    (album: AlbumListItemResponse): boolean => album.id === albumId,
  );

  if (foundAlbum === undefined) {
    return null;
  }

  return foundAlbum;
}
