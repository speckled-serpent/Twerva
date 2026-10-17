import { useEffect, useState, type ReactElement } from "react";

import {
  deleteResearch,
  fetchResearchById,
  listResearch,
  patchResearch,
} from "../api/client";
import type {
  ResearchListItemResponse,
  ResearchPatchRequest,
  ResearchReadResponse,
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
import { useSkeletonAutosave } from "./useSkeletonAutosave";

const RESEARCH_TITLE_ERROR: string = "Title is required.";
const RESEARCH_BODY_MAX_CHARACTERS: number = 1_000_000;
const RESEARCH_BODY_TOO_LONG: string =
  "Research body must be 1,000,000 characters or fewer.";
const RESEARCH_BODY_NOT_TEXT: string = "Research body must be plain text.";

export interface ResearchOpenRequest {
  researchId: string;
  statusMessage: string;
}

export interface ResearchPageProps {
  openRequest: ResearchOpenRequest | null;
  onCreateResearch: () => void;
}

interface ResearchDraft {
  title: string;
  body: string;
}

interface ResearchDeleteTarget {
  id: string;
  title: string;
}

/**
 * Research: a list, and a detail that edits one document and autosaves.
 *
 * @param props - Optional open request from Create Research
 * @returns The Research page
 */
export function ResearchPage({ openRequest, onCreateResearch }: ResearchPageProps): ReactElement {

  const [listedResearch, setListedResearch] = useState<ResearchListItemResponse[]>([]);
  const [openedResearchId, setOpenedResearchId] = useState<string | null>(
    openRequest?.researchId ?? null,
  );
  const [loadError, setLoadError] = useState<unknown>(null);
  const [statusMessage, setStatusMessage] = useState<string>(openRequest?.statusMessage ?? "");
  const [reloadToken, setReloadToken] = useState<number>(0);

  useEffect((): (() => void) => {
    if (openRequest !== null) {
      setOpenedResearchId(openRequest.researchId);
      setStatusMessage(openRequest.statusMessage);
    }

    return (): void => {
      return;
    };
  }, [openRequest]);

  useEffect((): (() => void) => {
    if (openedResearchId !== null) {
      return (): void => {
        return;
      };
    }

    let isCancelled: boolean = false;

    const loadResearch = async (): Promise<void> => {

      try {
        const loadedResearch: ResearchListItemResponse[] = await listResearch();

        if (isCancelled) {
          return;
        }

        setListedResearch(loadedResearch);
        setLoadError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setLoadError(caughtError);
      }
    };

    void loadResearch();

    return (): void => {
      isCancelled = true;
    };
  }, [openedResearchId, reloadToken]);

  if (openedResearchId !== null) {
    return (
      <ResearchDetailView
        key={openedResearchId}
        researchId={openedResearchId}
        onBack={(): void => {
          setOpenedResearchId(null);
          setReloadToken((currentToken: number): number => currentToken + 1);
        }}
        onDeleted={(researchTitle: string): void => {
          setStatusMessage(`Deleted research ${researchTitle}.`);
          setOpenedResearchId(null);
          setReloadToken((currentToken: number): number => currentToken + 1);
        }}
      />
    );
  }

  return (
    <ResearchListView
      researchItems={listedResearch}
      loadError={loadError}
      statusMessage={statusMessage}
      onCreateResearch={onCreateResearch}
      onSelectResearch={(researchId: string): void => {
        setStatusMessage("");
        setOpenedResearchId(researchId);
      }}
      onResearchDeleted={(researchTitle: string): void => {
        setStatusMessage(`Deleted research ${researchTitle}.`);
        setReloadToken((currentToken: number): number => currentToken + 1);
      }}
    />
  );
}

interface ResearchListViewProps {
  researchItems: ResearchListItemResponse[];
  loadError: unknown;
  statusMessage: string;
  onCreateResearch: () => void;
  onSelectResearch: (researchId: string) => void;
  onResearchDeleted: (researchTitle: string) => void;
}

function ResearchListView({
  researchItems,
  loadError,
  statusMessage,
  onCreateResearch,
  onSelectResearch,
  onResearchDeleted,
}: ResearchListViewProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [pendingDelete, setPendingDelete] = useState<ResearchDeleteTarget | null>(null);
  const [deleteError, setDeleteError] = useState<unknown>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  const handleConfirmDelete = async (): Promise<void> => {

    if (!canWrite || pendingDelete === null) {
      return;
    }

    setIsDeleting(true);
    setDeleteError(null);

    try {
      await deleteResearch(pendingDelete.id);
      onResearchDeleted(pendingDelete.title);
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
          <h1>Research</h1>
          <p className="lede">
            A reusable text document. Open a row to edit the title and the body.
          </p>
        </div>
        <div className="page-header-actions">
          <button id="create-research" type="button" className="primary" onClick={onCreateResearch}>
            Create Research
          </button>
        </div>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}
      {loadError !== null ? null : researchItems.length === 0 ? (
        <p className="empty-hint">No research yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Title</th>
              <th>Words</th>
              <th>Created</th>
              <th>View</th>
              <th>Delete</th>
            </tr>
          </thead>
          <tbody>
            {researchItems.map((researchItem: ResearchListItemResponse): ReactElement => (
              <tr
                key={researchItem.id}
                className="clickable-row"
                onClick={(): void => {
                  onSelectResearch(researchItem.id);
                }}
              >
                <td>{researchItem.title}</td>
                <td>{researchItem.word_count.toLocaleString("en-US")}</td>
                <td className="mono">{formatSkeletonTimestamp(researchItem.created_at)}</td>
                <td>
                  <button
                    type="button"
                    onClick={(clickEvent): void => {
                      clickEvent.stopPropagation();
                      onSelectResearch(researchItem.id);
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
                      setPendingDelete({
                        id: researchItem.id,
                        title: researchItem.title,
                      });
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
        <DeleteResearchDialog
          researchTitle={pendingDelete.title}
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

interface ResearchDetailViewProps {
  researchId: string;
  onBack: () => void;
  onDeleted: (researchTitle: string) => void;
}

function ResearchDetailView({
  researchId,
  onBack,
  onDeleted,
}: ResearchDetailViewProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [researchItem, setResearchItem] = useState<ResearchReadResponse | null>(null);
  const [draft, setDraft] = useState<ResearchDraft | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [pendingDelete, setPendingDelete] = useState<boolean>(false);
  const [deleteError, setDeleteError] = useState<unknown>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  const autosave = useSkeletonAutosave<ResearchDraft>({
    delayMs: SKELETON_AUTOSAVE_DELAY_MS,
    readiness: researchDraftReadiness,
    fingerprint: researchDraftFingerprint,
    save: async (value: ResearchDraft): Promise<void> => {
      const savedResearch: ResearchReadResponse = await patchResearch(
        researchId,
        patchFromDraft(value),
      );
      setResearchItem(savedResearch);
    },
    formatError: formatSkeletonAutosaveError,
  });

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadResearchItem = async (): Promise<void> => {

      try {
        const loadedResearch: ResearchReadResponse = await fetchResearchById(researchId);

        if (isCancelled) {
          return;
        }

        const loadedDraft: ResearchDraft = draftFromResearch(loadedResearch);
        setResearchItem(loadedResearch);
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

    void loadResearchItem();

    return (): void => {
      isCancelled = true;
    };
  }, [researchId, autosave.noteSaved]);

  useEffect((): void => {
    if (!canWrite || draft === null) {
      return;
    }

    autosave.schedule(draft);
  }, [autosave.schedule, canWrite, draft]);

  const handleBack = (): void => {
    void leaveAfterAutosave(autosave.flush, autosave.isDirty, onBack);
  };

  const handleConfirmDelete = async (): Promise<void> => {

    if (!canWrite || researchItem === null || isDeleting) {
      return;
    }

    setIsDeleting(true);
    setDeleteError(null);

    try {
      await deleteResearch(researchId);
      onDeleted(researchItem.title);
    } catch (caughtError: unknown) {
      setDeleteError(caughtError);
    } finally {
      setIsDeleting(false);
    }
  };

  const displayTitle: string = draft?.title.trim() || researchItem?.title || "Research";
  const displayBody: string = draft?.body ?? researchItem?.body ?? "";

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>{displayTitle}</h1>
          <p className="lede">Title and body save on their own.</p>
          <SkeletonAutosaveStatus
            state={autosave.state}
            onRetry={(): void => {
              void autosave.retry();
            }}
          />
        </div>
        <div className="page-header-actions">
          <button type="button" onClick={handleBack}>
            Back to Research
          </button>
          <button
            id="delete-research"
            type="button"
            className="danger"
            disabled={!canWrite || researchItem === null || isDeleting}
            onClick={(): void => {
              setDeleteError(null);
              setPendingDelete(true);
            }}
          >
            Delete
          </button>
        </div>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      {loadError !== null || draft === null || researchItem === null ? (
        loadError === null ? <p className="empty-hint">Loading research…</p> : null
      ) : (
        <div className="research-editor">
          <p className="field-hint">
            Slug: {researchItem.slug}. Renaming does not change it.
          </p>
          <p className="field-hint">
            Created {formatSkeletonTimestamp(researchItem.created_at)}
            {" · "}
            Updated {formatSkeletonTimestamp(researchItem.updated_at)}
          </p>
          <label>
            Title
            <input
              id="research-title"
              value={draft.title}
              disabled={!canWrite}
              onChange={(changeEvent): void => {
                setDraft({
                  title: changeEvent.target.value,
                  body: draft.body,
                });
              }}
            />
          </label>
          <label>
            Body
            <textarea
              id="research-body"
              className="research-body"
              value={draft.body}
              disabled={!canWrite}
              spellCheck
              onChange={(changeEvent): void => {
                setDraft({
                  title: draft.title,
                  body: changeEvent.target.value,
                });
              }}
            />
          </label>
          <p id="research-counts" className="research-counts">
            {formatResearchCounts(displayBody)}
          </p>
        </div>
      )}
      {pendingDelete && researchItem !== null ? (
        <DeleteResearchDialog
          researchTitle={researchItem.title}
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

interface DeleteResearchDialogProps {
  researchTitle: string;
  deleteError: unknown;
  isDeleting: boolean;
  canWrite: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

function DeleteResearchDialog({
  researchTitle,
  deleteError,
  isDeleting,
  canWrite,
  onConfirm,
  onCancel,
}: DeleteResearchDialogProps): ReactElement {

  return (
    <div className="confirm-backdrop" onClick={onCancel}>
      <div
        className="confirm-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-research-heading"
        onClick={(clickEvent): void => {
          clickEvent.stopPropagation();
        }}
      >
        <h2 id="delete-research-heading">Delete {researchTitle}?</h2>
        <p>
          This removes the document. Nothing else uses it yet. This cannot be undone.
        </p>
        <ErrorBanner error={deleteError} />
        <div className="button-row">
          <button
            id="confirm-delete-research"
            type="button"
            className="danger"
            disabled={!canWrite || isDeleting}
            onClick={onConfirm}
          >
            {isDeleting ? "Deleting…" : "Delete research"}
          </button>
          <button
            id="cancel-delete-research"
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

function draftFromResearch(researchItem: ResearchReadResponse): ResearchDraft {

  const draft: ResearchDraft = {
    title: researchItem.title,
    body: researchItem.body,
  };

  return draft;
}

function patchFromDraft(draft: ResearchDraft): ResearchPatchRequest {

  const patchRequest: ResearchPatchRequest = {
    title: draft.title.trim(),
    body: draft.body,
  };

  return patchRequest;
}

function researchDraftReadiness(draft: ResearchDraft): AutosaveReadiness {

  if (draft.title.trim() === "") {
    const invalidTitle: AutosaveReadiness = {
      kind: "invalid",
      message: RESEARCH_TITLE_ERROR,
    };

    return invalidTitle;
  }

  if (draft.body.includes("\u0000")) {
    const invalidText: AutosaveReadiness = {
      kind: "invalid",
      message: RESEARCH_BODY_NOT_TEXT,
    };

    return invalidText;
  }

  if (draft.body.length > RESEARCH_BODY_MAX_CHARACTERS) {
    const invalidLength: AutosaveReadiness = {
      kind: "invalid",
      message: RESEARCH_BODY_TOO_LONG,
    };

    return invalidLength;
  }

  const ready: AutosaveReadiness = { kind: "ready" };

  return ready;
}

function researchDraftFingerprint(draft: ResearchDraft): string {

  const fingerprint: string = JSON.stringify({
    title: draft.title.trim(),
    body: draft.body,
  });

  return fingerprint;
}

/**
 * Count words the same way the API does: split on whitespace.
 *
 * @param body - The document currently in the editor
 * @returns A word count and a character count
 */
function formatResearchCounts(body: string): string {

  const wordCount: number = countResearchWords(body);
  const characterCount: number = body.length;
  const wordLabel: string = wordCount === 1 ? "word" : "words";
  const characterLabel: string = characterCount === 1 ? "character" : "characters";
  const countsLabel: string = (
    `${wordCount.toLocaleString("en-US")} ${wordLabel}`
    + ` · ${characterCount.toLocaleString("en-US")} ${characterLabel}`
  );

  return countsLabel;
}

function countResearchWords(body: string): number {

  const words: string[] = body.split(/\s+/).filter((word: string): boolean => word !== "");

  return words.length;
}
