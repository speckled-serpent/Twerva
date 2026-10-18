import { useEffect, useRef, useState, type ReactElement } from "react";

import { deleteAlbum, listAlbums } from "../api/client";
import type { AlbumListItemResponse, AlbumReadResponse } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import { useCanWriteOps } from "../session/OpsSessionContext";
import { AlbumImagesEditor, type AlbumEditorActions } from "./AlbumImagesEditor";
import { formatSkeletonTimestamp } from "./skeletonDisplay";
import { leaveAfterAutosave } from "./skeletonAutosave";

export interface AlbumsOpenRequest {
  albumId: string;
  statusMessage: string;
}

export interface AlbumsPageProps {
  openRequest: AlbumsOpenRequest | null;
  onCreateAlbum: () => void;
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
  const [draftName, setDraftName] = useState<string>("");
  const [deleteError, setDeleteError] = useState<unknown>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [pendingDelete, setPendingDelete] = useState<boolean>(false);
  const [imagesBusy, setImagesBusy] = useState<boolean>(false);
  const albumEditorActionsRef: { current: AlbumEditorActions | null } = useRef(null);

  const handleBack = (): void => {
    const albumActions: AlbumEditorActions | null = albumEditorActionsRef.current;

    const flush = async (): Promise<void> => {

      if (albumActions === null) {
        return;
      }

      await albumActions.flush();
    };

    const isDirty = (): boolean => {

      if (albumActions === null) {
        return false;
      }

      return albumActions.isDirty();
    };

    void leaveAfterAutosave(flush, isDirty, onBack);
  };

  const handleConfirmDelete = async (): Promise<void> => {

    if (!canWrite || album === null || isDeleting) {
      return;
    }

    const albumName: string = album.name;
    setIsDeleting(true);
    setDeleteError(null);

    try {
      const albumActions: AlbumEditorActions | null = albumEditorActionsRef.current;

      if (albumActions !== null) {
        await albumActions.abandon();
      }

      await deleteAlbum(albumId);
      onDeleted(albumName);
    } catch (caughtError: unknown) {
      setDeleteError(caughtError);
      setIsDeleting(false);
    }
  };

  const headingName: string = draftName.trim() || album?.name || "Album";
  const deleteLocked: boolean = !canWrite || album === null || isDeleting || imagesBusy;

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>{headingName}</h1>
          <p className="lede">
            Images in this album. Name, order, and license fields save on their own.
          </p>
        </div>
        <div className="page-header-actions">
          <button type="button" onClick={handleBack}>
            Back to Albums
          </button>
          <button
            type="button"
            className="danger"
            disabled={deleteLocked}
            onClick={(): void => {
              setPendingDelete(true);
            }}
          >
            Delete album
          </button>
        </div>
      </div>
      <ReadOnlyNotice />
      <AlbumImagesEditor
        albumId={albumId}
        canWrite={canWrite}
        showName
        onAlbumChange={(loadedAlbum: AlbumReadResponse): void => {
          setAlbum(loadedAlbum);
        }}
        onNameDraft={setDraftName}
        onActions={(actions: AlbumEditorActions | null): void => {
          albumEditorActionsRef.current = actions;
        }}
        onBusyChange={setImagesBusy}
      />
      {pendingDelete && album !== null ? (
        <DeleteAlbumDialog
          albumName={album.name}
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

            setPendingDelete(false);
            setDeleteError(null);
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
