import { useEffect, useRef, useState, type FormEvent, type ReactElement } from "react";

import {
  deleteSkeleton,
  duplicateSkeleton,
  fetchSkeletonById,
  listSkeletons,
  patchSkeleton,
} from "../api/client";
import type {
  SkeletonElementReadResponse,
  SkeletonReadResponse,
} from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import { useCanWriteOps } from "../session/OpsSessionContext";
import {
  SkeletonElementEditor,
  previewElementStateFromElements,
  type SkeletonPreviewDraftElement,
  type SkeletonPreviewElementState,
} from "./SkeletonElementEditor";
import { SkeletonLivePreview } from "./SkeletonLivePreview";
import {
  SkeletonFrameFields,
  frameDraftFromSkeleton,
  skeletonPatchFromFrameDraft,
  type SkeletonFrameDraft,
} from "./SkeletonFrameFields";
import {
  advertisementTypeLabel,
  formatSkeletonTemplateKey,
  formatSkeletonTimestamp,
} from "./skeletonDisplay";
import { SkeletonAutosaveStatus } from "./SkeletonAutosaveStatus";
import {
  SKELETON_AUTOSAVE_DELAY_MS,
  combineAutosaveStates,
  formatSkeletonAutosaveError,
  leaveAfterAutosave,
  type SkeletonAutosaveActions,
  type SkeletonAutosaveState,
} from "./skeletonAutosave";
import { useSkeletonAutosave } from "./useSkeletonAutosave";

export interface SkeletonsPageProps {
  statusMessage: string;
  onCreateSkeleton: () => void;
}

/**
 * Skeletons tab: list saved skeletons. Selecting a row opens the frame and elements.
 * Duplicate opens the new Draft and leaves the carousel row as it was.
 * Delete removes the skeleton after a confirmation that names it.
 * Generate samples shows one preview and does not queue a post.
 *
 * @param props - Banner shown after create
 * @returns The Skeletons list or detail
 */
export function SkeletonsPage({
  statusMessage,
  onCreateSkeleton,
}: SkeletonsPageProps): ReactElement {

  const [skeletons, setSkeletons] = useState<SkeletonReadResponse[]>([]);
  const [openedSkeletonId, setOpenedSkeletonId] = useState<string | null>(null);
  const [selectedSkeleton, setSelectedSkeleton] = useState<SkeletonReadResponse | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadList = async (): Promise<void> => {

      try {
        const loadedSkeletons: SkeletonReadResponse[] = await listSkeletons();

        if (isCancelled) {
          return;
        }

        setSkeletons(loadedSkeletons);
        setLoadError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setLoadError(caughtError);
      }
    };

    void loadList();

    return (): void => {
      isCancelled = true;
    };
  }, []);

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    if (openedSkeletonId === null) {
      setSelectedSkeleton(null);

      return (): void => {
        isCancelled = true;
      };
    }

    const loadDetail = async (): Promise<void> => {

      try {
        const loadedSkeleton: SkeletonReadResponse = await fetchSkeletonById(openedSkeletonId);

        if (isCancelled) {
          return;
        }

        setSelectedSkeleton(loadedSkeleton);
        setLoadError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setSelectedSkeleton(null);
        setLoadError(caughtError);
      }
    };

    void loadDetail();

    return (): void => {
      isCancelled = true;
    };
  }, [openedSkeletonId]);

  if (openedSkeletonId !== null) {
    return (
      <SkeletonDetailView
        selectedSkeleton={selectedSkeleton}
        loadError={loadError}
        statusMessage={statusMessage}
        onBack={(): void => {
          setOpenedSkeletonId(null);
        }}
        onSkeletonSaved={(updatedSkeleton: SkeletonReadResponse): void => {
          setSelectedSkeleton(updatedSkeleton);
          setSkeletons((currentSkeletons: SkeletonReadResponse[]): SkeletonReadResponse[] => {
            return replaceSkeletonInList(currentSkeletons, updatedSkeleton);
          });
        }}
        onSkeletonDuplicated={(copiedSkeleton: SkeletonReadResponse): void => {
          setSkeletons((currentSkeletons: SkeletonReadResponse[]): SkeletonReadResponse[] => {
            const withoutCopy: SkeletonReadResponse[] = currentSkeletons.filter(
              (skeleton: SkeletonReadResponse): boolean => skeleton.id !== copiedSkeleton.id,
            );

            return [copiedSkeleton, ...withoutCopy];
          });
          setSelectedSkeleton(copiedSkeleton);
          setOpenedSkeletonId(copiedSkeleton.id);
        }}
      />
    );
  }

  return (
    <SkeletonListView
      skeletons={skeletons}
      loadError={loadError}
      statusMessage={statusMessage}
      onCreateSkeleton={onCreateSkeleton}
      onSelectSkeleton={(skeletonId: string): void => {
        setOpenedSkeletonId(skeletonId);
      }}
      onSkeletonDeleted={(skeletonId: string): void => {
        setSkeletons((currentSkeletons: SkeletonReadResponse[]): SkeletonReadResponse[] => {
          return currentSkeletons.filter(
            (skeleton: SkeletonReadResponse): boolean => skeleton.id !== skeletonId,
          );
        });
      }}
    />
  );
}

interface SkeletonListViewProps {
  skeletons: SkeletonReadResponse[];
  loadError: unknown;
  statusMessage: string;
  onCreateSkeleton: () => void;
  onSelectSkeleton: (skeletonId: string) => void;
  onSkeletonDeleted: (skeletonId: string) => void;
}

function SkeletonListView({
  skeletons,
  loadError,
  statusMessage,
  onCreateSkeleton,
  onSelectSkeleton,
  onSkeletonDeleted,
}: SkeletonListViewProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [pendingDelete, setPendingDelete] = useState<SkeletonReadResponse | null>(null);
  const [deleteError, setDeleteError] = useState<unknown>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  const handleConfirmDelete = async (): Promise<void> => {

    if (!canWrite || pendingDelete === null) {
      return;
    }

    setIsDeleting(true);
    setDeleteError(null);

    try {
      await deleteSkeleton(pendingDelete.id);
      onSkeletonDeleted(pendingDelete.id);
      setPendingDelete(null);
    } catch (caughtError: unknown) {
      setDeleteError(caughtError);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleCancelDelete = (): void => {

    if (isDeleting) {
      return;
    }

    setPendingDelete(null);
    setDeleteError(null);
  };

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>Skeletons</h1>
          <p className="lede">
            Visual styling for carousels. Open a row for the saved record.
            Delete asks before it removes a row.
          </p>
        </div>
        <div className="page-header-actions">
          <button type="button" className="primary" onClick={onCreateSkeleton}>
            Create Skeleton
          </button>
        </div>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}

      {loadError !== null ? null : skeletons.length === 0 ? (
        <p className="empty-hint">No skeletons yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Advertisement type</th>
              <th>Created</th>
              <th>View</th>
              <th>Delete</th>
            </tr>
          </thead>
          <tbody>
            {skeletons.map((skeleton: SkeletonReadResponse): ReactElement => (
              <tr
                key={skeleton.id}
                className="clickable-row"
                onClick={(): void => {
                  onSelectSkeleton(skeleton.id);
                }}
              >
                <td>{skeleton.name}</td>
                <td>{advertisementTypeLabel(skeleton.advertisement_type)}</td>
                <td className="mono">{formatSkeletonTimestamp(skeleton.created_at)}</td>
                <td>
                  <button
                    type="button"
                    onClick={(clickEvent): void => {
                      clickEvent.stopPropagation();
                      onSelectSkeleton(skeleton.id);
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
                      setPendingDelete(skeleton);
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
        <div
          className="confirm-backdrop"
          onClick={handleCancelDelete}
        >
          <div
            className="confirm-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-skeleton-heading"
            onClick={(clickEvent): void => {
              clickEvent.stopPropagation();
            }}
          >
            <h2 id="delete-skeleton-heading">Delete {pendingDelete.name}?</h2>
            <p>
              This removes {pendingDelete.name} and its elements. This cannot be undone.
            </p>
            <ErrorBanner error={deleteError} />
            <div className="button-row">
              <button
                id="confirm-delete-skeleton"
                type="button"
                className="danger"
                disabled={!canWrite || isDeleting}
                onClick={(): void => {
                  void handleConfirmDelete();
                }}
              >
                {isDeleting ? "Deleting…" : "Delete skeleton"}
              </button>
              <button
                id="cancel-delete-skeleton"
                type="button"
                disabled={isDeleting}
                onClick={handleCancelDelete}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

interface SkeletonPreviewReport extends SkeletonPreviewElementState {
  skeletonId: string;
}

interface SkeletonDetailViewProps {
  selectedSkeleton: SkeletonReadResponse | null;
  loadError: unknown;
  statusMessage: string;
  onBack: () => void;
  onSkeletonSaved: (updatedSkeleton: SkeletonReadResponse) => void;
  onSkeletonDuplicated: (copiedSkeleton: SkeletonReadResponse) => void;
}

function SkeletonDetailView({
  selectedSkeleton,
  loadError,
  statusMessage,
  onBack,
  onSkeletonSaved,
  onSkeletonDuplicated,
}: SkeletonDetailViewProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [editedDraft, setEditedDraft] = useState<SkeletonFrameDraft | null>(null);
  const [previewReport, setPreviewReport] = useState<SkeletonPreviewReport | null>(null);
  const [editedForSkeletonId, setEditedForSkeletonId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [isDuplicating, setIsDuplicating] = useState<boolean>(false);
  const [elementAutosaveState, setElementAutosaveState] = useState<SkeletonAutosaveState>({
    phase: "idle",
    message: "",
    canRetry: false,
  });
  const selectedSkeletonRef = useRef(selectedSkeleton);
  const elementActionsRef = useRef<SkeletonAutosaveActions | null>(null);
  const notedFrameIdRef = useRef<string | null>(null);
  selectedSkeletonRef.current = selectedSkeleton;
  const frameDraft: SkeletonFrameDraft | null = frameDraftForSkeleton(
    selectedSkeleton,
    editedDraft,
    editedForSkeletonId,
  );
  const frameAutosave = useSkeletonAutosave<SkeletonFrameDraft>({
    delayMs: SKELETON_AUTOSAVE_DELAY_MS,
    readiness: (nextDraft: SkeletonFrameDraft) => {

      if (!canWrite) {
        return { kind: "skip" };
      }

      try {
        skeletonPatchFromFrameDraft(nextDraft);

        return { kind: "ready" };
      } catch (caughtError: unknown) {
        const message: string = caughtError instanceof Error
          ? caughtError.message
          : String(caughtError);

        return { kind: "invalid", message };
      }
    },
    fingerprint: (nextDraft: SkeletonFrameDraft): string => {
      return JSON.stringify(skeletonPatchFromFrameDraft(nextDraft));
    },
    save: async (nextDraft: SkeletonFrameDraft): Promise<void> => {
      const skeleton: SkeletonReadResponse | null = selectedSkeletonRef.current;

      if (skeleton === null) {
        return;
      }

      const updatedSkeleton: SkeletonReadResponse = await patchSkeleton(
        skeleton.id,
        skeletonPatchFromFrameDraft(nextDraft),
      );
      onSkeletonSaved(updatedSkeleton);
    },
    formatError: formatSkeletonAutosaveError,
  });
  const autosaveState: SkeletonAutosaveState = combineAutosaveStates([
    frameAutosave.state,
    elementAutosaveState,
  ]);
  const savedPreview: SkeletonPreviewElementState | null = selectedSkeleton === null
    ? null
    : previewElementStateFromElements(selectedSkeleton.elements);
  const activePreview: SkeletonPreviewElementState | null = (
    previewReport !== null
    && selectedSkeleton !== null
    && previewReport.skeletonId === selectedSkeleton.id
  )
    ? previewReport
    : savedPreview;
  const fieldsDisabled: boolean = !canWrite || isDuplicating;
  const duplicateDisabled: boolean = !canWrite || isDuplicating || selectedSkeleton === null;

  const rememberDraft = (nextDraft: SkeletonFrameDraft): void => {

    if (selectedSkeleton === null) {
      return;
    }

    setEditedForSkeletonId(selectedSkeleton.id);
    setEditedDraft(nextDraft);
    setActionError(null);
  };

  const flushSkeletonEdits = async (): Promise<void> => {

    await Promise.all([
      frameAutosave.flush(),
      elementActionsRef.current?.flush() ?? Promise.resolve(),
    ]);
  };

  const skeletonEditsAreDirty = (): boolean => {

    return frameAutosave.isDirty() || (elementActionsRef.current?.isDirty() ?? false);
  };

  const retryAutosave = (): void => {
    void frameAutosave.retry();
    void elementActionsRef.current?.retry();
  };

  const selectedSkeletonId: string | null = selectedSkeleton === null ? null : selectedSkeleton.id;

  useEffect((): void => {
    const skeleton: SkeletonReadResponse | null = selectedSkeletonRef.current;

    if (!canWrite || skeleton === null || frameDraft === null) {
      return;
    }

    if (notedFrameIdRef.current !== skeleton.id) {
      notedFrameIdRef.current = skeleton.id;
      frameAutosave.noteSaved(frameDraftFromSkeleton(skeleton));
    }

    frameAutosave.schedule(frameDraft);
  }, [
    canWrite,
    frameAutosave.noteSaved,
    frameAutosave.schedule,
    frameDraft,
    selectedSkeletonId,
  ]);

  const handleDuplicate = async (): Promise<void> => {

    if (!canWrite || selectedSkeleton === null) {
      return;
    }

    setIsDuplicating(true);
    setActionError(null);

    try {
      await flushSkeletonEdits();

      if (skeletonEditsAreDirty()) {
        return;
      }

      const copiedSkeleton: SkeletonReadResponse = await duplicateSkeleton(selectedSkeleton.id);

      onSkeletonDuplicated(copiedSkeleton);
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setIsDuplicating(false);
    }
  };

  const handleBack = (): void => {
    void leaveAfterAutosave(flushSkeletonEdits, skeletonEditsAreDirty, onBack);
  };

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>{selectedSkeleton === null ? "Skeleton" : selectedSkeleton.name}</h1>
          <p className="lede">
            Background, spacing, and full-width elements.
            Edits save on their own.
          </p>
          <SkeletonAutosaveStatus state={autosaveState} onRetry={retryAutosave} />
        </div>
        <div className="button-row">
          <button
            type="button"
            disabled={duplicateDisabled}
            onClick={(): void => {
              void handleDuplicate();
            }}
          >
            {isDuplicating ? "Duplicating…" : "Duplicate"}
          </button>
          <button type="button" onClick={handleBack} disabled={isDuplicating}>
            Back to list
          </button>
        </div>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      <ErrorBanner error={actionError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}

      {selectedSkeleton === null || frameDraft === null ? (
        loadError === null ? <p>Loading skeleton…</p> : null
      ) : (
        <>
          <div className="skeleton-editor-layout">
          <div className="skeleton-editor-main">
          <dl className="campaign-detail-list">
            <dt>Name</dt>
            <dd>{selectedSkeleton.name}</dd>
            <dt>Slug</dt>
            <dd className="mono">{selectedSkeleton.slug}</dd>
            <dt>Advertisement type</dt>
            <dd>{advertisementTypeLabel(selectedSkeleton.advertisement_type)}</dd>
            <dt>Template</dt>
            <dd className="mono">{formatSkeletonTemplateKey(selectedSkeleton.template_key)}</dd>
            <dt>Created</dt>
            <dd className="mono">{formatSkeletonTimestamp(selectedSkeleton.created_at)}</dd>
            <dt>Updated</dt>
            <dd className="mono">{formatSkeletonTimestamp(selectedSkeleton.updated_at)}</dd>
          </dl>

          <form
            className="stack-form campaign-form"
            onSubmit={(formEvent: FormEvent): void => {
              formEvent.preventDefault();
              void frameAutosave.flush();
            }}
          >
            <SkeletonFrameFields
              frameDraft={frameDraft}
              onDraftChange={rememberDraft}
              disabled={fieldsDisabled}
            />
          </form>
          <SkeletonElementEditor
            skeleton={selectedSkeleton}
            onSkeletonUpdated={onSkeletonSaved}
            onElementPatched={(patchedElement: SkeletonElementReadResponse): void => {
              const currentSkeleton: SkeletonReadResponse | null = selectedSkeletonRef.current;

              if (currentSkeleton === null) {
                return;
              }

              const nextElements: SkeletonElementReadResponse[] = currentSkeleton.elements.map(
                (element: SkeletonElementReadResponse): SkeletonElementReadResponse => {

                  if (element.id !== patchedElement.id) {
                    return element;
                  }

                  return patchedElement;
                },
              );
              onSkeletonSaved({
                ...currentSkeleton,
                elements: nextElements,
              });
            }}
            onAutosaveStateChange={setElementAutosaveState}
            autosaveActionsRef={elementActionsRef}
            onPreviewElementsChange={(
              elements: SkeletonPreviewDraftElement[] | null,
              draftError: string | null,
            ): void => {
              if (selectedSkeleton === null) {
                return;
              }

              setPreviewReport({
                skeletonId: selectedSkeleton.id,
                elements,
                draftError,
              });
            }}
          />
          </div>
            <SkeletonLivePreview
              frameDraft={frameDraft}
              elements={activePreview === null ? null : activePreview.elements}
              draftError={activePreview === null ? null : activePreview.draftError}
            />
          </div>
        </>
      )}
    </section>
  );
}

function replaceSkeletonInList(
  skeletons: SkeletonReadResponse[],
  updatedSkeleton: SkeletonReadResponse,
): SkeletonReadResponse[] {

  const nextSkeletons: SkeletonReadResponse[] = skeletons.map(
    (skeleton: SkeletonReadResponse): SkeletonReadResponse => {

      if (skeleton.id !== updatedSkeleton.id) {
        return skeleton;
      }

      return updatedSkeleton;
    },
  );

  return nextSkeletons;
}

function frameDraftForSkeleton(
  skeleton: SkeletonReadResponse | null,
  editedDraft: SkeletonFrameDraft | null,
  editedForSkeletonId: string | null,
): SkeletonFrameDraft | null {

  if (skeleton === null) {
    return null;
  }

  if (editedDraft !== null && editedForSkeletonId === skeleton.id) {
    return editedDraft;
  }

  const frameDraft: SkeletonFrameDraft = frameDraftFromSkeleton(skeleton);

  return frameDraft;
}
