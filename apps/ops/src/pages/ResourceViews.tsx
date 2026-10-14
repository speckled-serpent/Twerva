import { useEffect, useState, type FormEvent, type ReactElement } from "react";

import {
  createResource,
  deleteSource,
  renameSource,
  replaceResourceFile,
  resourceFileUrl,
} from "../api/client";
import type { SourceListItemResponse, SourceReadResponse } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import { useCanWriteOps } from "../session/OpsSessionContext";

export type SourceTab = "albums" | "resources";

interface SourceTabBarProps {
  sourceTab: SourceTab;
  onTab: (sourceTab: SourceTab) => void;
}

export function SourceTabBar({ sourceTab, onTab }: SourceTabBarProps): ReactElement {

  return (
    <div className="ops-nav source-tabs" role="tablist" aria-label="Source kinds">
      <button
        id="tab-albums"
        type="button"
        role="tab"
        className={sourceTab === "albums" ? "ops-nav-button is-active" : "ops-nav-button"}
        aria-selected={sourceTab === "albums"}
        onClick={(): void => {
          onTab("albums");
        }}
      >
        Albums
      </button>
      <button
        id="tab-resources"
        type="button"
        role="tab"
        className={sourceTab === "resources" ? "ops-nav-button is-active" : "ops-nav-button"}
        aria-selected={sourceTab === "resources"}
        onClick={(): void => {
          onTab("resources");
        }}
      >
        Resources
      </button>
    </div>
  );
}

interface ResourceListViewProps {
  resources: SourceListItemResponse[];
  tabs: ReactElement;
  loadError: unknown;
  statusMessage: string;
  onOpenResource: (sourceId: string) => void;
  onResourceCreated: (createdSource: SourceReadResponse) => void;
  onResourceDeleted: (resourceName: string) => void;
}

export function ResourceListView({
  resources,
  tabs,
  loadError,
  statusMessage,
  onOpenResource,
  onResourceCreated,
  onResourceDeleted,
}: ResourceListViewProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [resourceName, setResourceName] = useState<string>("");
  const [provenance, setProvenance] = useState<string>("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [saveError, setSaveError] = useState<unknown>(null);
  const [pendingDelete, setPendingDelete] = useState<SourceListItemResponse | null>(null);

  const handleCreate = async (submitEvent: FormEvent<HTMLFormElement>): Promise<void> => {
    submitEvent.preventDefault();

    if (!canWrite || selectedFile === null) {
      return;
    }

    setIsSaving(true);
    setSaveError(null);

    try {
      const createdSource: SourceReadResponse = await createResource(
        resourceName,
        provenance,
        selectedFile,
      );
      setResourceName("");
      setProvenance("");
      setSelectedFile(null);
      onResourceCreated(createdSource);
    } catch (caughtError: unknown) {
      setSaveError(caughtError);
    } finally {
      setIsSaving(false);
    }
  };

  const createDisabled: boolean = (
    isSaving
    || resourceName.trim() === ""
    || provenance.trim() === ""
    || selectedFile === null
  );

  return (
    <section>
      {tabs}
      <div className="page-header-row">
        <div>
          <h1>Sources</h1>
          <p className="lede">
            Resources. Each one is a Markdown or TXT file and a provenance note.
          </p>
        </div>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      <ErrorBanner error={saveError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}
      {canWrite ? (
        <form
          className="stack-form"
          onSubmit={(submitEvent: FormEvent<HTMLFormElement>): void => {
            void handleCreate(submitEvent);
          }}
        >
          <label>
            Name
            <input
              id="create-resource-name"
              value={resourceName}
              onChange={(changeEvent): void => {
                setResourceName(changeEvent.target.value);
              }}
            />
          </label>
          <label>
            Provenance
            <textarea
              id="create-resource-provenance"
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
              id="create-resource-file"
              type="file"
              accept=".md,.txt,text/markdown,text/plain"
              onChange={(changeEvent): void => {
                const fileList: FileList | null = changeEvent.target.files;
                setSelectedFile(fileList === null || fileList.length === 0 ? null : fileList[0]);
              }}
            />
          </label>
          <p>Markdown (.md) or plain text (.txt). 2 MB. The file is stored as uploaded.</p>
          <button id="create-resource-submit" type="submit" disabled={createDisabled}>
            {isSaving ? "Uploading…" : "Create resource"}
          </button>
        </form>
      ) : null}
      {loadError !== null ? null : resources.length === 0 ? (
        <p>No resources yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Open</th>
              <th>Delete</th>
            </tr>
          </thead>
          <tbody>
            {resources.map((resource: SourceListItemResponse): ReactElement => (
              <tr key={resource.id}>
                <td>{resource.name}</td>
                <td>
                  <button
                    type="button"
                    onClick={(): void => {
                      onOpenResource(resource.id);
                    }}
                  >
                    Open
                  </button>
                </td>
                <td>
                  {canWrite ? (
                    <button
                      type="button"
                      className="danger"
                      onClick={(): void => {
                        setPendingDelete(resource);
                      }}
                    >
                      Delete
                    </button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {pendingDelete === null ? null : (
        <form
          className="stack-form"
          onSubmit={(submitEvent: FormEvent<HTMLFormElement>): void => {
            submitEvent.preventDefault();
            void deleteSource(pendingDelete.id).then((): void => {
              const deletedName: string = pendingDelete.name;
              setPendingDelete(null);
              onResourceDeleted(deletedName);
            }).catch((caughtError: unknown): void => {
              setSaveError(caughtError);
              setPendingDelete(null);
            });
          }}
        >
          <p id="delete-resource-heading">Delete {pendingDelete.name}?</p>
          <p>This removes the resource and its file. Nothing in a theme points at it.</p>
          <button type="submit" className="danger">Delete resource</button>
          <button
            type="button"
            onClick={(): void => {
              setPendingDelete(null);
            }}
          >
            Cancel
          </button>
        </form>
      )}
    </section>
  );
}

interface ResourceDetailViewProps {
  source: SourceReadResponse | null;
  loadError: unknown;
  statusMessage: string;
  onBack: () => void;
  onChanged: (message: string) => void;
  onDeleted: () => void;
}

export function ResourceDetailView({
  source,
  loadError,
  statusMessage,
  onBack,
  onChanged,
  onDeleted,
}: ResourceDetailViewProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const resourceFile = source?.resource ?? null;
  const [name, setName] = useState<string>(source?.name ?? "");
  const [provenance, setProvenance] = useState<string>(resourceFile?.provenance ?? "");
  const [replaceFile, setReplaceFile] = useState<File | null>(null);
  const [saveError, setSaveError] = useState<unknown>(null);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [confirmDelete, setConfirmDelete] = useState<boolean>(false);

  useEffect((): void => {
    setName(source?.name ?? "");
    setProvenance(source?.resource?.provenance ?? "");
  }, [source?.id, source?.name, source?.resource?.body, source?.resource?.provenance]);

  const saveNote = async (): Promise<void> => {
    if (source === null || !canWrite) {
      return;
    }

    setIsSaving(true);
    setSaveError(null);

    try {
      await renameSource(source.id, { name, provenance });
      onChanged("Saved the note.");
    } catch (caughtError: unknown) {
      setSaveError(caughtError);
    } finally {
      setIsSaving(false);
    }
  };

  const saveReplacement = async (): Promise<void> => {
    if (source === null || replaceFile === null || !canWrite) {
      return;
    }

    setIsSaving(true);
    setSaveError(null);

    try {
      await replaceResourceFile(source.id, replaceFile);
      setReplaceFile(null);
      onChanged("Replaced the file.");
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
          <h1>{source === null ? "Resource" : source.name}</h1>
          <p className="lede">
            The note says where this text came from. Replacing the file uploads a new one.
          </p>
        </div>
        <button type="button" onClick={onBack}>
          Back to resources
        </button>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      <ErrorBanner error={saveError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}
      {source === null || resourceFile === null ? (
        <p>Loading resource…</p>
      ) : (
        <>
          <form
            className="stack-form"
            onSubmit={(submitEvent: FormEvent<HTMLFormElement>): void => {
              submitEvent.preventDefault();
              void saveNote();
            }}
          >
            <label>
              Name
              <input
                id="resource-name"
                value={name}
                disabled={!canWrite}
                onChange={(changeEvent): void => {
                  setName(changeEvent.target.value);
                }}
              />
            </label>
            <label>
              Provenance
              <textarea
                id="resource-provenance"
                rows={3}
                value={provenance}
                disabled={!canWrite}
                onChange={(changeEvent): void => {
                  setProvenance(changeEvent.target.value);
                }}
              />
            </label>
            {canWrite ? (
              <button id="save-resource-note" type="submit" disabled={isSaving || provenance.trim() === ""}>
                {isSaving ? "Saving…" : "Save note"}
              </button>
            ) : null}
          </form>
          {canWrite ? (
            <form
              className="stack-form"
              onSubmit={(submitEvent: FormEvent<HTMLFormElement>): void => {
                submitEvent.preventDefault();
                void saveReplacement();
              }}
            >
              <label>
                Replace file
                <input
                  id="replace-resource-file"
                  type="file"
                  accept=".md,.txt,text/markdown,text/plain"
                  onChange={(changeEvent): void => {
                    const fileList: FileList | null = changeEvent.target.files;
                    setReplaceFile(fileList === null || fileList.length === 0 ? null : fileList[0]);
                  }}
                />
              </label>
              <button id="replace-resource-submit" type="submit" disabled={isSaving || replaceFile === null}>
                Upload replacement
              </button>
            </form>
          ) : null}
          <p>
            <a id="resource-download" href={resourceFileUrl(source.id, true)}>
              Download {resourceFile.original_filename}
            </a>
          </p>
          {resourceFile.media_type === "markdown" && resourceFile.rendered_html !== null ? (
            <div
              id="resource-rendered"
              className="resource-markdown"
              dangerouslySetInnerHTML={{ __html: resourceFile.rendered_html }}
            />
          ) : null}
          <pre id="resource-body" className="resource-source-text">{resourceFile.body}</pre>
          {canWrite && !confirmDelete ? (
            <button
              type="button"
              className="danger"
              onClick={(): void => {
                setConfirmDelete(true);
              }}
            >
              Delete resource
            </button>
          ) : null}
          {canWrite && confirmDelete ? (
            <form
              className="stack-form"
              onSubmit={(submitEvent: FormEvent<HTMLFormElement>): void => {
                submitEvent.preventDefault();
                void deleteSource(source.id).then((): void => {
                  onDeleted();
                }).catch((caughtError: unknown): void => {
                  setSaveError(caughtError);
                  setConfirmDelete(false);
                });
              }}
            >
              <p>Delete this resource and its file?</p>
              <button type="submit" className="danger">Delete resource</button>
              <button
                type="button"
                onClick={(): void => {
                  setConfirmDelete(false);
                }}
              >
                Cancel
              </button>
            </form>
          ) : null}
        </>
      )}
    </section>
  );
}
