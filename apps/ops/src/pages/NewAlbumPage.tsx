import { useState, type FormEvent, type ReactElement } from "react";

import { createAlbum } from "../api/client";
import type { AlbumReadResponse } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import { useCanWriteOps } from "../session/OpsSessionContext";

export const CREATE_ALBUM_NAME_ERROR: string = "Name is required.";

export interface NewAlbumPageProps {
  onCreated: (createdAlbum: AlbumReadResponse) => void;
  onCancel: () => void;
}

/**
 * Create Album: a name, then open the album so images can be added.
 *
 * @param props - Success and cancel navigation callbacks
 * @returns The create-album form
 */
export function NewAlbumPage({ onCreated, onCancel }: NewAlbumPageProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [albumName, setAlbumName] = useState<string>("");
  const [saveError, setSaveError] = useState<unknown>(null);
  const [isSaving, setIsSaving] = useState<boolean>(false);

  const handleCreate = async (submitEvent: FormEvent<HTMLFormElement>): Promise<void> => {
    submitEvent.preventDefault();

    if (!canWrite || isSaving) {
      return;
    }

    if (albumName.trim() === "") {
      setSaveError(new Error(CREATE_ALBUM_NAME_ERROR));

      return;
    }

    setIsSaving(true);
    setSaveError(null);

    try {
      const createdAlbum: AlbumReadResponse = await createAlbum({
        name: albumName.trim(),
      });

      onCreated(createdAlbum);
    } catch (caughtError: unknown) {
      setSaveError(caughtError);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>Create Album</h1>
          <p className="lede">
            An album is a collection of images. After this, it opens so you can add them.
          </p>
        </div>
        <button type="button" onClick={onCancel}>
          Back to Albums
        </button>
      </div>
      <ReadOnlyNotice />
      {canWrite ? (
        <form
          id="create-album-form"
          className="stack-form"
          onSubmit={(submitEvent: FormEvent<HTMLFormElement>): void => {
            void handleCreate(submitEvent);
          }}
        >
          <label>
            Name
            <input
              id="create-album-name"
              value={albumName}
              onChange={(changeEvent): void => {
                setAlbumName(changeEvent.target.value);
              }}
            />
          </label>
          <ErrorBanner error={saveError} />
          <div className="button-row">
            <button id="create-album-submit" type="submit" className="primary" disabled={isSaving}>
              {isSaving ? "Creating…" : "Create Album"}
            </button>
            <button type="button" onClick={onCancel} disabled={isSaving}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <p>Creating an album is an admin action.</p>
      )}
    </section>
  );
}
