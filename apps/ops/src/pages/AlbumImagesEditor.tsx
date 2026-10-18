import { useEffect, useRef, useState, type ReactElement } from "react";

import {
  albumImageDisplayUrl,
  deleteAlbumImage,
  fetchAlbumById,
  importAlbumImage,
  patchAlbum,
  uploadAlbumImage,
} from "../api/client";
import type { AlbumImageReadResponse, AlbumReadResponse, SlideImageLicense } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import {
  ALBUM_IMAGE_LICENSES,
  albumDraftFingerprint,
  albumDraftReadiness,
  albumImageFileIntakeError,
  albumImageLicensePatch,
  albumImageUrlIntakeError,
  displayImageFromDraft,
  draftFromAlbum,
  moveAlbumImage,
  patchFromDraft,
  slideImageLicenseFromSelect,
  withAlbumImagePatch,
  type AlbumDraft,
  type AlbumImageDraft,
  type AlbumImageFieldPatch,
} from "./albumImages";
import { SkeletonAutosaveStatus } from "./SkeletonAutosaveStatus";
import {
  SKELETON_AUTOSAVE_DELAY_MS,
  formatSkeletonAutosaveError,
} from "./skeletonAutosave";
import { useSkeletonAutosave } from "./useSkeletonAutosave";

export interface AlbumEditorActions {
  flush: () => Promise<void>;
  isDirty: () => boolean;
  abandon: () => Promise<void>;
}

export interface AlbumImagesEditorProps {
  albumId: string;
  canWrite: boolean;
  showName: boolean;
  onAlbumChange?: (album: AlbumReadResponse) => void;
  onNameDraft?: (name: string) => void;
  onActions?: (actions: AlbumEditorActions | null) => void;
  onBusyChange?: (isBusy: boolean) => void;
}

/**
 * Add, import, reorder, and autosave one album's images.
 *
 * The Albums page shows the name field. Content does not: the carousel
 * already shows the album name. Both write bytes through the album image
 * routes and save license, source, alt, and the license note at 700ms.
 * A reader can look. The fields stay disabled and the add form stays hidden.
 *
 * @param props - Album id, write flag, and the name field
 * @returns The image editor
 */
export function AlbumImagesEditor({
  albumId,
  canWrite,
  showName,
  onAlbumChange,
  onNameDraft,
  onActions,
  onBusyChange,
}: AlbumImagesEditorProps): ReactElement {

  const [draft, setDraft] = useState<AlbumDraft | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [isWorking, setIsWorking] = useState<boolean>(false);
  const [file, setFile] = useState<File | null>(null);
  const [imageUrl, setImageUrl] = useState<string>("");
  const [intakeLicense, setIntakeLicense] = useState<SlideImageLicense>("cc0");
  const [intakeSource, setIntakeSource] = useState<string>("");
  const [intakeAlt, setIntakeAlt] = useState<string>("");
  const [intakeNote, setIntakeNote] = useState<string>("");
  const fileInputRef: { current: HTMLInputElement | null } = useRef<HTMLInputElement | null>(null);
  const onAlbumChangeRef: { current: ((album: AlbumReadResponse) => void) | undefined } =
    useRef(onAlbumChange);
  const onNameDraftRef: { current: ((name: string) => void) | undefined } = useRef(onNameDraft);
  const onActionsRef: { current: ((actions: AlbumEditorActions | null) => void) | undefined } =
    useRef(onActions);
  const onBusyChangeRef: { current: ((isBusy: boolean) => void) | undefined } =
    useRef(onBusyChange);
  onAlbumChangeRef.current = onAlbumChange;
  onNameDraftRef.current = onNameDraft;
  onActionsRef.current = onActions;
  onBusyChangeRef.current = onBusyChange;

  const autosave = useSkeletonAutosave<AlbumDraft>({
    delayMs: SKELETON_AUTOSAVE_DELAY_MS,
    readiness: albumDraftReadiness,
    fingerprint: albumDraftFingerprint,
    save: async (value: AlbumDraft): Promise<void> => {
      await patchAlbum(albumId, patchFromDraft(value));
    },
    formatError: formatSkeletonAutosaveError,
  });

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;
    setDraft(null);
    setLoadError(null);

    const loadAlbum = async (): Promise<void> => {

      try {
        const loadedAlbum: AlbumReadResponse = await fetchAlbumById(albumId);

        if (isCancelled) {
          return;
        }

        const loadedDraft: AlbumDraft = draftFromAlbum(loadedAlbum);
        setDraft(loadedDraft);
        setLoadError(null);
        autosave.noteSaved(loadedDraft);
        onNameDraftRef.current?.(loadedDraft.name);
        onAlbumChangeRef.current?.(loadedAlbum);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setLoadError(caughtError);
      }
    };

    void loadAlbum();

    return (): void => {
      isCancelled = true;
    };
  }, [albumId, autosave.noteSaved]);

  useEffect((): void => {
    if (!canWrite || draft === null) {
      return;
    }

    autosave.schedule(draft);
  }, [autosave.schedule, canWrite, draft]);

  useEffect((): (() => void) => {
    onActionsRef.current?.({
      flush: autosave.flush,
      isDirty: autosave.isDirty,
      abandon: autosave.abandon,
    });

    return (): void => {
      onActionsRef.current?.(null);
    };
  }, [autosave.flush, autosave.isDirty, autosave.abandon]);

  useEffect((): void => {
    onBusyChangeRef.current?.(isWorking);
  }, [isWorking]);

  useEffect((): (() => void) => {
    return (): void => {
      onBusyChangeRef.current?.(false);
    };
  }, []);

  const replaceFromServer = (loadedAlbum: AlbumReadResponse): void => {
    const loadedDraft: AlbumDraft = draftFromAlbum(loadedAlbum);
    setDraft(loadedDraft);
    autosave.noteSaved(loadedDraft);
    onNameDraftRef.current?.(loadedDraft.name);
    onAlbumChangeRef.current?.(loadedAlbum);
  };

  const applyDraft = (nextDraft: AlbumDraft): void => {
    setDraft(nextDraft);
    onNameDraftRef.current?.(nextDraft.name);
    setActionError(null);
  };

  const updateImage = (imageId: string, patch: AlbumImageFieldPatch): void => {

    if (draft === null) {
      return;
    }

    applyDraft({
      name: draft.name,
      images: withAlbumImagePatch(draft.images, imageId, patch),
    });
  };

  const handleAddFile = async (): Promise<void> => {

    if (!canWrite || file === null || isWorking) {
      return;
    }

    const intakeError: string | null = albumImageFileIntakeError(
      file.name,
      intakeSource,
      intakeLicense,
      intakeNote,
    );

    if (intakeError !== null) {
      setActionError(new Error(intakeError));

      return;
    }

    setIsWorking(true);
    setActionError(null);

    try {
      await autosave.flush();

      if (autosave.isDirty()) {
        return;
      }

      await uploadAlbumImage(
        albumId,
        file,
        intakeLicense,
        intakeSource.trim(),
        intakeAlt.trim(),
        intakeLicense === "licensed" ? intakeNote.trim() : "",
      );
      const loadedAlbum: AlbumReadResponse = await fetchAlbumById(albumId);
      replaceFromServer(loadedAlbum);
      setFile(null);

      if (fileInputRef.current !== null) {
        fileInputRef.current.value = "";
      }
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setIsWorking(false);
    }
  };

  const handleImportUrl = async (): Promise<void> => {

    if (!canWrite || isWorking) {
      return;
    }

    const trimmedUrl: string = imageUrl.trim();
    const intakeError: string | null = albumImageUrlIntakeError(
      trimmedUrl,
      intakeSource,
      intakeLicense,
      intakeNote,
    );

    if (intakeError !== null) {
      setActionError(new Error(intakeError));

      return;
    }

    setIsWorking(true);
    setActionError(null);

    try {
      await autosave.flush();

      if (autosave.isDirty()) {
        return;
      }

      await importAlbumImage(albumId, {
        url: trimmedUrl,
        license: intakeLicense,
        source: intakeSource.trim(),
        alt_text: intakeAlt.trim() === "" ? null : intakeAlt.trim(),
        license_note: intakeLicense === "licensed" ? intakeNote.trim() : "",
      });
      const loadedAlbum: AlbumReadResponse = await fetchAlbumById(albumId);
      replaceFromServer(loadedAlbum);
      setImageUrl("");
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setIsWorking(false);
    }
  };

  const handleRemoveImage = async (imageId: string): Promise<void> => {

    if (!canWrite || isWorking) {
      return;
    }

    setIsWorking(true);
    setActionError(null);

    try {
      await autosave.flush();

      if (autosave.isDirty()) {
        return;
      }

      await deleteAlbumImage(albumId, imageId);
      const loadedAlbum: AlbumReadResponse = await fetchAlbumById(albumId);
      replaceFromServer(loadedAlbum);
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setIsWorking(false);
    }
  };

  const moveImage = (imageIndex: number, direction: -1 | 1): void => {

    if (draft === null) {
      return;
    }

    const nextImages: AlbumImageDraft[] | null = moveAlbumImage(draft.images, imageIndex, direction);

    if (nextImages === null) {
      return;
    }

    applyDraft({
      name: draft.name,
      images: nextImages,
    });
  };

  return (
    <div className="album-images-editor">
      <SkeletonAutosaveStatus
        state={autosave.state}
        onRetry={(): void => {
          void autosave.retry();
        }}
      />
      <ErrorBanner error={loadError} />
      <ErrorBanner error={actionError} />
      {draft === null ? null : (
        <>
          {showName ? (
            <label>
              Name
              <input
                id="album-name"
                value={draft.name}
                disabled={!canWrite}
                onChange={(changeEvent): void => {
                  applyDraft({
                    name: changeEvent.target.value,
                    images: draft.images,
                  });
                }}
              />
            </label>
          ) : null}
          <section className="slide-images" id="album-images" aria-label="Images">
            <h2>Images</h2>
            {draft.images.length === 0 ? <p className="empty-hint">No images yet.</p> : null}
            <div className="slide-image-drafts">
              {draft.images.map((image: AlbumImageDraft, imageIndex: number): ReactElement => {
                const displayImage: AlbumImageReadResponse = displayImageFromDraft(image, imageIndex);

                return (
                  <div className="image-editor" key={image.id}>
                    <img
                      src={albumImageDisplayUrl(albumId, displayImage)}
                      alt={image.altText === "" ? image.relativePath : image.altText}
                    />
                    <div className="stack-form">
                      <p className="mono">{image.relativePath}</p>
                      <label>
                        Alt
                        <input
                          id={`album-image-alt-${imageIndex}`}
                          value={image.altText}
                          disabled={!canWrite}
                          onChange={(changeEvent): void => {
                            updateImage(image.id, { altText: changeEvent.target.value });
                          }}
                        />
                      </label>
                      <label>
                        License
                        <select
                          id={`album-image-license-${imageIndex}`}
                          value={image.license}
                          disabled={!canWrite}
                          onChange={(changeEvent): void => {
                            const nextLicense: SlideImageLicense | null = slideImageLicenseFromSelect(
                              changeEvent.target.value,
                            );

                            if (nextLicense === null) {
                              return;
                            }

                            updateImage(image.id, albumImageLicensePatch(image, nextLicense));
                          }}
                        >
                          {ALBUM_IMAGE_LICENSES.map((licenseOption: SlideImageLicense): ReactElement => (
                            <option key={licenseOption} value={licenseOption}>
                              {licenseOption}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Source
                        <input
                          id={`album-image-source-${imageIndex}`}
                          value={image.source}
                          disabled={!canWrite}
                          onChange={(changeEvent): void => {
                            updateImage(image.id, { source: changeEvent.target.value });
                          }}
                        />
                      </label>
                      <label>
                        License note
                        <input
                          id={`album-image-note-${imageIndex}`}
                          value={image.licenseNote}
                          disabled={!canWrite || image.license !== "licensed"}
                          onChange={(changeEvent): void => {
                            updateImage(image.id, { licenseNote: changeEvent.target.value });
                          }}
                        />
                      </label>
                      <div className="button-row">
                        <button
                          type="button"
                          disabled={!canWrite || imageIndex === 0 || isWorking}
                          onClick={(): void => {
                            moveImage(imageIndex, -1);
                          }}
                        >
                          Move up
                        </button>
                        <button
                          type="button"
                          disabled={!canWrite || imageIndex === draft.images.length - 1 || isWorking}
                          onClick={(): void => {
                            moveImage(imageIndex, 1);
                          }}
                        >
                          Move down
                        </button>
                        <button
                          type="button"
                          className="danger"
                          disabled={!canWrite || isWorking}
                          onClick={(): void => {
                            void handleRemoveImage(image.id);
                          }}
                        >
                          Remove image
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
          {canWrite ? (
            <section className="slide-images" id="album-image-add" aria-label="Add an image">
              <h2>Add an image</h2>
              <p className="field-hint">
                Upload a file or add a URL. The license, source, and note are saved with it.
              </p>
              <label>
                File
                <input
                  id="album-image-file"
                  ref={fileInputRef}
                  type="file"
                  accept=".svg,.png,.jpg,.jpeg,image/svg+xml,image/png,image/jpeg"
                  onChange={(changeEvent): void => {
                    const nextFile: File | undefined = changeEvent.target.files?.[0];
                    setFile(nextFile ?? null);
                    setActionError(null);
                  }}
                />
              </label>
              <p className="field-hint">SVG, PNG, or JPEG. 8 MB each.</p>
              <div className="slide-image-url-row">
                <label>
                  Image URL
                  <input
                    id="album-image-url"
                    value={imageUrl}
                    onChange={(changeEvent): void => {
                      setImageUrl(changeEvent.target.value);
                      setActionError(null);
                    }}
                  />
                </label>
                <button
                  id="album-import-url"
                  type="button"
                  disabled={isWorking}
                  onClick={(): void => {
                    void handleImportUrl();
                  }}
                >
                  Add URL
                </button>
              </div>
              <label>
                License
                <select
                  id="album-intake-license"
                  value={intakeLicense}
                  onChange={(changeEvent): void => {
                    const nextLicense: SlideImageLicense | null = slideImageLicenseFromSelect(
                      changeEvent.target.value,
                    );

                    if (nextLicense === null) {
                      return;
                    }

                    setIntakeLicense(nextLicense);

                    if (nextLicense !== "licensed") {
                      setIntakeNote("");
                    }
                  }}
                >
                  {ALBUM_IMAGE_LICENSES.map((licenseOption: SlideImageLicense): ReactElement => (
                    <option key={licenseOption} value={licenseOption}>
                      {licenseOption}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Source
                <input
                  id="album-intake-source"
                  value={intakeSource}
                  onChange={(changeEvent): void => {
                    setIntakeSource(changeEvent.target.value);
                  }}
                />
              </label>
              <label>
                Alt
                <input
                  id="album-intake-alt"
                  value={intakeAlt}
                  onChange={(changeEvent): void => {
                    setIntakeAlt(changeEvent.target.value);
                  }}
                />
              </label>
              <label>
                License note
                <input
                  id="album-intake-note"
                  value={intakeNote}
                  disabled={intakeLicense !== "licensed"}
                  onChange={(changeEvent): void => {
                    setIntakeNote(changeEvent.target.value);
                  }}
                />
              </label>
              <div className="button-row">
                <button
                  id="album-upload-image"
                  type="button"
                  className="primary"
                  disabled={file === null || isWorking}
                  onClick={(): void => {
                    void handleAddFile();
                  }}
                >
                  {isWorking ? "Adding…" : "Add image"}
                </button>
              </div>
            </section>
          ) : null}
        </>
      )}
    </div>
  );
}
