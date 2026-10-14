import { useState, type FormEvent, type ReactElement } from "react";

import { createAlbum, createResource } from "../api/client";
import type { SourceReadResponse } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import { useCanWriteOps } from "../session/OpsSessionContext";
import {
  CREATE_SOURCE_FILE_ERROR,
  createSourceFieldError,
  type CreateSourceKind,
} from "./createSource";

export interface NewSourcePageProps {
  onCreated: (createdSource: SourceReadResponse) => void;
  onCancel: () => void;
}

/**
 * Create Source tab: pick Album or Resource, then save and open it.
 *
 * @param props - Success and cancel navigation callbacks
 * @returns The create-source form
 */
export function NewSourcePage({ onCreated, onCancel }: NewSourcePageProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [kind, setKind] = useState<CreateSourceKind>("album");
  const [sourceName, setSourceName] = useState<string>("");
  const [provenance, setProvenance] = useState<string>("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [saveError, setSaveError] = useState<unknown>(null);
  const [isSaving, setIsSaving] = useState<boolean>(false);

  const handleCreate = async (submitEvent: FormEvent<HTMLFormElement>): Promise<void> => {
    submitEvent.preventDefault();

    if (!canWrite || isSaving) {
      return;
    }

    const fieldError: string | null = createSourceFieldError(
      kind,
      sourceName,
      provenance,
      selectedFile === null ? null : selectedFile.name,
    );

    if (fieldError !== null) {
      setSaveError(new Error(fieldError));

      return;
    }

    setIsSaving(true);
    setSaveError(null);

    try {
      let createdSource: SourceReadResponse;

      if (kind === "album") {
        createdSource = await createAlbum({ name: sourceName.trim(), kind: "album" });
      } else if (selectedFile === null) {
        setSaveError(new Error(CREATE_SOURCE_FILE_ERROR));

        return;
      } else {
        createdSource = await createResource(sourceName.trim(), provenance.trim(), selectedFile);
      }

      onCreated(createdSource);
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
          <h1>Create Source</h1>
          <p className="lede">
            An album holds units. A resource is one Markdown or TXT file and a provenance note.
          </p>
        </div>
        <button type="button" onClick={onCancel}>
          Back to Sources
        </button>
      </div>
      <ReadOnlyNotice />
      {canWrite ? (
        <form
          id="create-source-form"
          className="stack-form"
          onSubmit={(submitEvent: FormEvent<HTMLFormElement>): void => {
            void handleCreate(submitEvent);
          }}
        >
          <fieldset>
            <legend>Kind</legend>
            <label>
              <input
                id="create-source-kind-album"
                type="radio"
                name="create-source-kind"
                checked={kind === "album"}
                onChange={(): void => {
                  setKind("album");
                  setSaveError(null);
                }}
              />
              Album
            </label>
            <label>
              <input
                id="create-source-kind-resource"
                type="radio"
                name="create-source-kind"
                checked={kind === "resource"}
                onChange={(): void => {
                  setKind("resource");
                  setSaveError(null);
                }}
              />
              Resource
            </label>
          </fieldset>
          <label>
            Name
            <input
              id="create-source-name"
              value={sourceName}
              onChange={(changeEvent): void => {
                setSourceName(changeEvent.target.value);
              }}
            />
          </label>
          {kind === "resource" ? (
            <>
              <label>
                Provenance
                <textarea
                  id="create-source-provenance"
                  rows={3}
                  value={provenance}
                  onChange={(changeEvent): void => {
                    setProvenance(changeEvent.target.value);
                  }}
                />
              </label>
              <label>
                File
                <input
                  id="create-source-file"
                  type="file"
                  accept=".md,.txt,text/markdown,text/plain"
                  onChange={(changeEvent): void => {
                    const fileList: FileList | null = changeEvent.target.files;
                    setSelectedFile(fileList === null || fileList.length === 0 ? null : fileList[0]);
                  }}
                />
              </label>
              <p className="field-hint">Markdown (.md) or plain text (.txt). 2 MB.</p>
            </>
          ) : (
            <p className="field-hint">After this, the album opens so you can add units.</p>
          )}
          <ErrorBanner error={saveError} />
          <div className="button-row">
            <button id="create-source-submit" type="submit" disabled={isSaving}>
              {isSaving ? "Creating…" : "Create source"}
            </button>
            <button type="button" onClick={onCancel} disabled={isSaving}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <p>Creating a source is an admin action.</p>
      )}
    </section>
  );
}
