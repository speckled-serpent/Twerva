import { useEffect, useState, type ReactElement } from "react";

import {
  albumImageDisplayUrl,
  deleteAlbum,
  deleteAlbumImage,
  fetchAlbumById,
  importAlbumImage,
  listAlbums,
  patchAlbum,
  uploadAlbumImage,
} from "../api/client";
import type {
  AlbumImageReadResponse,
  AlbumListItemResponse,
  AlbumPatchRequest,
  AlbumReadResponse,
  SlideImageLicense,
} from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import { useCanWriteOps } from "../session/OpsSessionContext";
import { formatSkeletonTimestamp } from "./skeletonDisplay";
import { SkeletonAutosaveStatus } from "./SkeletonAutosaveStatus";
import {
  SKELETON_AUTOSAVE_DELAY_MS,
  formatSkeletonAutosaveError,
  leaveAfterAutosave,
  type AutosaveReadiness,
} from "./skeletonAutosave";
import {
  SLIDE_IMAGE_NOTE_ERROR,
  SLIDE_IMAGE_SOURCE_ERROR,
  SLIDE_IMAGE_TYPE_ERROR,
  SLIDE_IMAGE_URL_ERROR,
  SLIDE_IMAGE_URL_SCHEME_ERROR,
  isAllowedImageFileName,
  isHttpImageUrl,
} from "./slideImageDraft";
import { useSkeletonAutosave } from "./useSkeletonAutosave";

const LICENSE_OPTIONS: SlideImageLicense[] = [
  "cc0",
  "public_domain",
  "owned",
  "licensed",
];

const ALBUM_NAME_ERROR: string = "Name is required.";

export interface AlbumsOpenRequest {
  albumId: string;
  statusMessage: string;
}

export interface AlbumsPageProps {
  openRequest: AlbumsOpenRequest | null;
  onCreateAlbum: () => void;
}

interface AlbumImageDraft {
  id: string;
  altText: string;
  license: SlideImageLicense;
  source: string;
  licenseNote: string;
  relativePath: string;
  thumbnailPath: string | null;
}

interface AlbumDraft {
  name: string;
  images: AlbumImageDraft[];
}

/**
 * Albums: a list, and a detail that adds, removes, reorders, and autosaves.
 *
 * @param props - Optional open request from Create Album
 * @returns The Albums page
 */
export function AlbumsPage({ openRequest, onCreateAlbum }: AlbumsPageProps): ReactElement {

  const [listedAlbums, setListedAlbums] = useState<AlbumListItemResponse[]>([]);
  const [openedAlbumId, setOpenedAlbumId] = useState<string | null>(openRequest?.albumId ?? null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [statusMessage, setStatusMessage] = useState<string>(openRequest?.statusMessage ?? "");
  const [reloadToken, setReloadToken] = useState<number>(0);

  useEffect((): (() => void) => {
    if (openRequest !== null) {
      setOpenedAlbumId(openRequest.albumId);
      setStatusMessage(openRequest.statusMessage);
    }

    return (): void => {
      return;
    };
  }, [openRequest]);

  useEffect((): (() => void) => {
    if (openedAlbumId !== null) {
      return (): void => {
        return;
      };
    }

    let isCancelled: boolean = false;

    const loadAlbums = async (): Promise<void> => {

      try {
        const loadedAlbums: AlbumListItemResponse[] = await listAlbums();

        if (isCancelled) {
          return;
        }

        setListedAlbums(loadedAlbums);
        setLoadError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setLoadError(caughtError);
      }
    };

    void loadAlbums();

    return (): void => {
      isCancelled = true;
    };
  }, [openedAlbumId, reloadToken]);

  if (openedAlbumId !== null) {
    return (
      <AlbumDetailView
        key={openedAlbumId}
        albumId={openedAlbumId}
        onBack={(): void => {
          setOpenedAlbumId(null);
          setReloadToken((currentToken: number): number => currentToken + 1);
        }}
        onDeleted={(albumName: string): void => {
          setStatusMessage(`Deleted album ${albumName}.`);
          setOpenedAlbumId(null);
          setReloadToken((currentToken: number): number => currentToken + 1);
        }}
      />
    );
  }

  return (
    <AlbumListView
      albums={listedAlbums}
      loadError={loadError}
      statusMessage={statusMessage}
      onCreateAlbum={onCreateAlbum}
      onSelectAlbum={(albumId: string): void => {
        setStatusMessage("");
        setOpenedAlbumId(albumId);
      }}
      onAlbumDeleted={(albumName: string): void => {
        setStatusMessage(`Deleted album ${albumName}.`);
        setReloadToken((currentToken: number): number => currentToken + 1);
      }}
    />
  );
}

interface AlbumListViewProps {
  albums: AlbumListItemResponse[];
  loadError: unknown;
  statusMessage: string;
  onCreateAlbum: () => void;
  onSelectAlbum: (albumId: string) => void;
  onAlbumDeleted: (albumName: string) => void;
}

function AlbumListView({
  albums,
  loadError,
  statusMessage,
  onCreateAlbum,
  onSelectAlbum,
  onAlbumDeleted,
}: AlbumListViewProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [pendingDelete, setPendingDelete] = useState<AlbumListItemResponse | null>(null);
  const [deleteError, setDeleteError] = useState<unknown>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  const handleConfirmDelete = async (): Promise<void> => {

    if (!canWrite || pendingDelete === null) {
      return;
    }

    setIsDeleting(true);
    setDeleteError(null);

    try {
      await deleteAlbum(pendingDelete.id);
      onAlbumDeleted(pendingDelete.name);
      setPendingDelete(null);
    } catch (caughtError: unknown) {
      setDeleteError(caughtError);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>Albums</h1>
          <p className="lede">
            A reusable collection of images. Open a row to add, remove, or reorder them.
          </p>
        </div>
        <div className="page-header-actions">
          <button type="button" className="primary" onClick={onCreateAlbum}>
            Create Album
          </button>
        </div>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}
      {loadError !== null ? null : albums.length === 0 ? (
        <p className="empty-hint">No albums yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Images</th>
              <th>Created</th>
              <th>View</th>
              <th>Delete</th>
            </tr>
          </thead>
          <tbody>
            {albums.map((album: AlbumListItemResponse): ReactElement => (
              <tr
                key={album.id}
                className="clickable-row"
                onClick={(): void => {
                  onSelectAlbum(album.id);
                }}
              >
                <td>{album.name}</td>
                <td>{album.image_count}</td>
                <td className="mono">{formatSkeletonTimestamp(album.created_at)}</td>
                <td>
                  <button
                    type="button"
                    onClick={(clickEvent): void => {
                      clickEvent.stopPropagation();
                      onSelectAlbum(album.id);
                    }}
                  >
                    View
                  </button>
                </td>
                <td>
                  <button
                    type="button"
                    className="danger"
                    disabled={!canWrite || isDeleting}
                    onClick={(clickEvent): void => {
                      clickEvent.stopPropagation();
                      setDeleteError(null);
                      setPendingDelete(album);
                    }}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {pendingDelete === null ? null : (
        <DeleteAlbumDialog
          albumName={pendingDelete.name}
          deleteError={deleteError}
          isDeleting={isDeleting}
          canWrite={canWrite}
          onConfirm={(): void => {
            void handleConfirmDelete();
          }}
          onCancel={(): void => {
            if (isDeleting) {
              return;
            }

            setPendingDelete(null);
            setDeleteError(null);
          }}
        />
      )}
    </section>
  );
}

interface AlbumDetailViewProps {
  albumId: string;
  onBack: () => void;
  onDeleted: (albumName: string) => void;
}

function AlbumDetailView({ albumId, onBack, onDeleted }: AlbumDetailViewProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [album, setAlbum] = useState<AlbumReadResponse | null>(null);
  const [draft, setDraft] = useState<AlbumDraft | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [isWorking, setIsWorking] = useState<boolean>(false);
  const [pendingDelete, setPendingDelete] = useState<boolean>(false);
  const [file, setFile] = useState<File | null>(null);
  const [imageUrl, setImageUrl] = useState<string>("");
  const [intakeLicense, setIntakeLicense] = useState<SlideImageLicense>("cc0");
  const [intakeSource, setIntakeSource] = useState<string>("");
  const [intakeAlt, setIntakeAlt] = useState<string>("");
  const [intakeNote, setIntakeNote] = useState<string>("");

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

    const loadAlbum = async (): Promise<void> => {

      try {
        const loadedAlbum: AlbumReadResponse = await fetchAlbumById(albumId);

        if (isCancelled) {
          return;
        }

        const loadedDraft: AlbumDraft = draftFromAlbum(loadedAlbum);
        setAlbum(loadedAlbum);
        setDraft(loadedDraft);
        setLoadError(null);
        autosave.noteSaved(loadedDraft);
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

  const replaceFromServer = (loadedAlbum: AlbumReadResponse): void => {
    const loadedDraft: AlbumDraft = draftFromAlbum(loadedAlbum);
    setAlbum(loadedAlbum);
    setDraft(loadedDraft);
    autosave.noteSaved(loadedDraft);
  };

  const handleBack = (): void => {
    void leaveAfterAutosave(autosave.flush, autosave.isDirty, onBack);
  };

  const handleAddFile = async (): Promise<void> => {

    if (!canWrite || file === null || isWorking) {
      return;
    }

    const intakeError: string | null = fileIntakeError(file.name, intakeSource, intakeLicense, intakeNote);

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
    const intakeError: string | null = urlIntakeError(trimmedUrl, intakeSource, intakeLicense, intakeNote);

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

  const handleConfirmDelete = async (): Promise<void> => {

    if (!canWrite || album === null || isWorking) {
      return;
    }

    const albumName: string = album.name;
    setIsWorking(true);
    setActionError(null);

    try {
      await autosave.abandon();
      await deleteAlbum(albumId);
      onDeleted(albumName);
    } catch (caughtError: unknown) {
      setActionError(caughtError);
      setIsWorking(false);
    }
  };

  const moveImage = (imageIndex: number, direction: -1 | 1): void => {

    if (draft === null) {
      return;
    }

    const nextIndex: number = imageIndex + direction;

    if (nextIndex < 0 || nextIndex >= draft.images.length) {
      return;
    }

    const nextImages: AlbumImageDraft[] = [...draft.images];
    const movingImage: AlbumImageDraft | undefined = nextImages[imageIndex];
    const swappedImage: AlbumImageDraft | undefined = nextImages[nextIndex];

    if (movingImage === undefined || swappedImage === undefined) {
      return;
    }

    nextImages[imageIndex] = swappedImage;
    nextImages[nextIndex] = movingImage;
    setDraft({
      name: draft.name,
      images: nextImages,
    });
    setActionError(null);
  };

  const updateImage = (imageId: string, patch: Partial<AlbumImageDraft>): void => {

    if (draft === null) {
      return;
    }

    const nextImages: AlbumImageDraft[] = draft.images.map(
      (image: AlbumImageDraft): AlbumImageDraft => {
        if (image.id !== imageId) {
          return image;
        }

        return { ...image, ...patch };
      },
    );
    setDraft({
      name: draft.name,
      images: nextImages,
    });
    setActionError(null);
  };

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>{draft?.name.trim() || album?.name || "Album"}</h1>
          <p className="lede">
            Images in this album. Name, order, and license fields save on their own.
          </p>
          <SkeletonAutosaveStatus
            state={autosave.state}
            onRetry={(): void => {
              void autosave.retry();
            }}
          />
        </div>
        <div className="page-header-actions">
          <button type="button" onClick={handleBack}>
            Back to Albums
          </button>
          <button
            type="button"
            className="danger"
            disabled={!canWrite || album === null || isWorking}
            onClick={(): void => {
              setPendingDelete(true);
            }}
          >
            Delete album
          </button>
        </div>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      <ErrorBanner error={actionError} />
      {draft === null ? null : (
        <>
          <label>
            Name
            <input
              id="album-name"
              value={draft.name}
              disabled={!canWrite}
              onChange={(changeEvent): void => {
                setDraft({
                  name: changeEvent.target.value,
                  images: draft.images,
                });
              }}
            />
          </label>
          <section className="slide-images">
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
                            const nextLicense: SlideImageLicense = changeEvent.target.value as SlideImageLicense;
                            updateImage(image.id, {
                              license: nextLicense,
                              licenseNote: nextLicense === "licensed" ? image.licenseNote : "",
                            });
                          }}
                        >
                          {LICENSE_OPTIONS.map((licenseOption: SlideImageLicense): ReactElement => (
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
            <section className="slide-images">
              <h2>Add an image</h2>
              <p className="field-hint">
                Upload a file or add a URL. The license, source, and note are saved with it.
              </p>
              <label>
                File
                <input
                  id="album-image-file"
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
                    const nextLicense: SlideImageLicense = changeEvent.target.value as SlideImageLicense;
                    setIntakeLicense(nextLicense);

                    if (nextLicense !== "licensed") {
                      setIntakeNote("");
                    }
                  }}
                >
                  {LICENSE_OPTIONS.map((licenseOption: SlideImageLicense): ReactElement => (
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
      {pendingDelete && album !== null ? (
        <DeleteAlbumDialog
          albumName={album.name}
          deleteError={actionError}
          isDeleting={isWorking}
          canWrite={canWrite}
          onConfirm={(): void => {
            void handleConfirmDelete();
          }}
          onCancel={(): void => {
            if (isWorking) {
              return;
            }

            setPendingDelete(false);
            setActionError(null);
          }}
        />
      ) : null}
    </section>
  );
}

interface DeleteAlbumDialogProps {
  albumName: string;
  deleteError: unknown;
  isDeleting: boolean;
  canWrite: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

function DeleteAlbumDialog({
  albumName,
  deleteError,
  isDeleting,
  canWrite,
  onConfirm,
  onCancel,
}: DeleteAlbumDialogProps): ReactElement {

  return (
    <div className="confirm-backdrop" onClick={onCancel}>
      <div
        className="confirm-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-album-heading"
        onClick={(clickEvent): void => {
          clickEvent.stopPropagation();
        }}
      >
        <h2 id="delete-album-heading">Delete {albumName}?</h2>
        <p>
          This removes {albumName} and its images. A skeleton or artifact that still
          stores one of those files blocks the delete. This cannot be undone.
        </p>
        <ErrorBanner error={deleteError} />
        <div className="button-row">
          <button
            id="confirm-delete-album"
            type="button"
            className="danger"
            disabled={!canWrite || isDeleting}
            onClick={onConfirm}
          >
            {isDeleting ? "Deleting…" : "Delete album"}
          </button>
          <button
            id="cancel-delete-album"
            type="button"
            disabled={isDeleting}
            onClick={onCancel}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

function draftFromAlbum(album: AlbumReadResponse): AlbumDraft {

  const orderedImages: AlbumImageReadResponse[] = [...album.images].sort(
    (left: AlbumImageReadResponse, right: AlbumImageReadResponse): number => (
      left.position - right.position
    ),
  );
  const imageDrafts: AlbumImageDraft[] = orderedImages.map(
    (image: AlbumImageReadResponse): AlbumImageDraft => {
      const imageDraft: AlbumImageDraft = {
        id: image.id,
        altText: image.alt_text ?? "",
        license: image.license,
        source: image.source,
        licenseNote: image.license === "licensed" ? image.license_note : "",
        relativePath: image.relative_path,
        thumbnailPath: image.thumbnail_path,
      };

      return imageDraft;
    },
  );
  const draft: AlbumDraft = {
    name: album.name,
    images: imageDrafts,
  };

  return draft;
}

function patchFromDraft(draft: AlbumDraft): AlbumPatchRequest {

  const patchRequest: AlbumPatchRequest = {
    name: draft.name.trim(),
    images: draft.images.map((image: AlbumImageDraft) => ({
      id: image.id,
      alt_text: image.altText.trim() === "" ? null : image.altText.trim(),
      license: image.license,
      source: image.source.trim(),
      license_note: image.license === "licensed" ? image.licenseNote.trim() : "",
    })),
  };

  return patchRequest;
}

function albumDraftReadiness(draft: AlbumDraft): AutosaveReadiness {

  if (draft.name.trim() === "") {
    const invalidName: AutosaveReadiness = {
      kind: "invalid",
      message: ALBUM_NAME_ERROR,
    };

    return invalidName;
  }

  for (const image of draft.images) {
    if (image.source.trim() === "") {
      const invalidSource: AutosaveReadiness = {
        kind: "invalid",
        message: SLIDE_IMAGE_SOURCE_ERROR,
      };

      return invalidSource;
    }

    if (image.license === "licensed" && image.licenseNote.trim() === "") {
      const invalidNote: AutosaveReadiness = {
        kind: "invalid",
        message: SLIDE_IMAGE_NOTE_ERROR,
      };

      return invalidNote;
    }
  }

  const ready: AutosaveReadiness = { kind: "ready" };

  return ready;
}

function albumDraftFingerprint(draft: AlbumDraft): string {

  const fingerprint: string = JSON.stringify({
    name: draft.name.trim(),
    images: draft.images.map((image: AlbumImageDraft) => ({
      id: image.id,
      altText: image.altText.trim(),
      license: image.license,
      source: image.source.trim(),
      licenseNote: image.license === "licensed" ? image.licenseNote.trim() : "",
    })),
  });

  return fingerprint;
}

function displayImageFromDraft(image: AlbumImageDraft, position: number): AlbumImageReadResponse {

  const displayImage: AlbumImageReadResponse = {
    id: image.id,
    position,
    relative_path: image.relativePath,
    media_type: "jpeg",
    byte_size: 0,
    width: null,
    height: null,
    alt_text: image.altText === "" ? null : image.altText,
    license: image.license,
    source: image.source,
    license_note: image.licenseNote,
    intake: "upload",
    thumbnail_path: image.thumbnailPath,
  };

  return displayImage;
}

function fileIntakeError(
  fileName: string,
  source: string,
  imageLicense: SlideImageLicense,
  licenseNote: string,
): string | null {

  if (!isAllowedImageFileName(fileName)) {
    return SLIDE_IMAGE_TYPE_ERROR;
  }

  return sharedIntakeError(source, imageLicense, licenseNote);
}

function urlIntakeError(
  imageUrl: string,
  source: string,
  imageLicense: SlideImageLicense,
  licenseNote: string,
): string | null {

  if (imageUrl === "") {
    return SLIDE_IMAGE_URL_ERROR;
  }

  if (!isHttpImageUrl(imageUrl)) {
    return SLIDE_IMAGE_URL_SCHEME_ERROR;
  }

  return sharedIntakeError(source, imageLicense, licenseNote);
}

function sharedIntakeError(
  source: string,
  imageLicense: SlideImageLicense,
  licenseNote: string,
): string | null {

  if (source.trim() === "") {
    return SLIDE_IMAGE_SOURCE_ERROR;
  }

  if (imageLicense === "licensed" && licenseNote.trim() === "") {
    return SLIDE_IMAGE_NOTE_ERROR;
  }

  return null;
}
