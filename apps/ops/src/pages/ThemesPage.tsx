import { useEffect, useRef, useState, type FormEvent, type ReactElement } from "react";

import {
  deleteTheme,
  duplicateTheme,
  fetchThemeById,
  listThemes,
  patchTheme,
} from "../api/client";
import type {
  ThemeElementCreateRequest,
  ThemeElementReadResponse,
  ThemeReadResponse,
} from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import { useCanWriteOps } from "../session/OpsSessionContext";
import {
  ThemeElementEditor,
  previewElementStateFromElements,
  type ThemePreviewElementState,
} from "./ThemeElementEditor";
import { ThemeLivePreview } from "./ThemeLivePreview";
import {
  ThemeFrameFields,
  frameDraftFromTheme,
  themePatchFromFrameDraft,
  type ThemeFrameDraft,
} from "./ThemeFrameFields";
import {
  advertisementTypeLabel,
  formatThemeTemplateKey,
  formatThemeTimestamp,
} from "./themeDisplay";
import { ThemeAutosaveStatus } from "./ThemeAutosaveStatus";
import {
  THEME_AUTOSAVE_DELAY_MS,
  combineAutosaveStates,
  formatThemeAutosaveError,
  leaveAfterAutosave,
  type ThemeAutosaveActions,
  type ThemeAutosaveState,
} from "./themeAutosave";
import { useThemeAutosave } from "./useThemeAutosave";

export interface ThemesPageProps {
  statusMessage: string;
  onCreateTheme: () => void;
}

/**
 * Themes tab: list saved themes. Selecting a row opens the frame and elements.
 * Duplicate opens the new Draft and leaves the source row as it was.
 * Delete removes the theme after a confirmation that names it.
 * Generate samples shows one preview and does not queue a post.
 *
 * @param props - Banner shown after create
 * @returns The Themes list or detail
 */
export function ThemesPage({
  statusMessage,
  onCreateTheme,
}: ThemesPageProps): ReactElement {

  const [themes, setThemes] = useState<ThemeReadResponse[]>([]);
  const [openedThemeId, setOpenedThemeId] = useState<string | null>(null);
  const [selectedTheme, setSelectedTheme] = useState<ThemeReadResponse | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadList = async (): Promise<void> => {

      try {
        const loadedThemes: ThemeReadResponse[] = await listThemes();

        if (isCancelled) {
          return;
        }

        setThemes(loadedThemes);
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

    if (openedThemeId === null) {
      setSelectedTheme(null);

      return (): void => {
        isCancelled = true;
      };
    }

    const loadDetail = async (): Promise<void> => {

      try {
        const loadedTheme: ThemeReadResponse = await fetchThemeById(openedThemeId);

        if (isCancelled) {
          return;
        }

        setSelectedTheme(loadedTheme);
        setLoadError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setSelectedTheme(null);
        setLoadError(caughtError);
      }
    };

    void loadDetail();

    return (): void => {
      isCancelled = true;
    };
  }, [openedThemeId]);

  if (openedThemeId !== null) {
    return (
      <ThemeDetailView
        selectedTheme={selectedTheme}
        loadError={loadError}
        statusMessage={statusMessage}
        onBack={(): void => {
          setOpenedThemeId(null);
        }}
        onThemeSaved={(updatedTheme: ThemeReadResponse): void => {
          setSelectedTheme(updatedTheme);
          setThemes((currentThemes: ThemeReadResponse[]): ThemeReadResponse[] => {
            return replaceThemeInList(currentThemes, updatedTheme);
          });
        }}
        onThemeDuplicated={(copiedTheme: ThemeReadResponse): void => {
          setThemes((currentThemes: ThemeReadResponse[]): ThemeReadResponse[] => {
            const withoutCopy: ThemeReadResponse[] = currentThemes.filter(
              (theme: ThemeReadResponse): boolean => theme.id !== copiedTheme.id,
            );

            return [copiedTheme, ...withoutCopy];
          });
          setSelectedTheme(copiedTheme);
          setOpenedThemeId(copiedTheme.id);
        }}
      />
    );
  }

  return (
    <ThemeListView
      themes={themes}
      loadError={loadError}
      statusMessage={statusMessage}
      onCreateTheme={onCreateTheme}
      onSelectTheme={(themeId: string): void => {
        setOpenedThemeId(themeId);
      }}
      onThemeDeleted={(themeId: string): void => {
        setThemes((currentThemes: ThemeReadResponse[]): ThemeReadResponse[] => {
          return currentThemes.filter(
            (theme: ThemeReadResponse): boolean => theme.id !== themeId,
          );
        });
      }}
    />
  );
}

interface ThemeListViewProps {
  themes: ThemeReadResponse[];
  loadError: unknown;
  statusMessage: string;
  onCreateTheme: () => void;
  onSelectTheme: (themeId: string) => void;
  onThemeDeleted: (themeId: string) => void;
}

function ThemeListView({
  themes,
  loadError,
  statusMessage,
  onCreateTheme,
  onSelectTheme,
  onThemeDeleted,
}: ThemeListViewProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [pendingDelete, setPendingDelete] = useState<ThemeReadResponse | null>(null);
  const [deleteError, setDeleteError] = useState<unknown>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  const handleConfirmDelete = async (): Promise<void> => {

    if (!canWrite || pendingDelete === null) {
      return;
    }

    setIsDeleting(true);
    setDeleteError(null);

    try {
      await deleteTheme(pendingDelete.id);
      onThemeDeleted(pendingDelete.id);
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
          <h1>Themes</h1>
          <p className="lede">
            Visual styling for carousels. Open a row for the saved record.
            Delete asks before it removes a row.
          </p>
        </div>
        <div className="page-header-actions">
          <button type="button" className="primary" onClick={onCreateTheme}>
            Create theme
          </button>
        </div>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}

      {loadError !== null ? null : themes.length === 0 ? (
        <p className="empty-hint">No themes yet.</p>
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
            {themes.map((theme: ThemeReadResponse): ReactElement => (
              <tr
                key={theme.id}
                className="clickable-row"
                onClick={(): void => {
                  onSelectTheme(theme.id);
                }}
              >
                <td>{theme.name}</td>
                <td>{advertisementTypeLabel(theme.advertisement_type)}</td>
                <td className="mono">{formatThemeTimestamp(theme.created_at)}</td>
                <td>
                  <button
                    type="button"
                    onClick={(clickEvent): void => {
                      clickEvent.stopPropagation();
                      onSelectTheme(theme.id);
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
                      setPendingDelete(theme);
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
            aria-labelledby="delete-theme-heading"
            onClick={(clickEvent): void => {
              clickEvent.stopPropagation();
            }}
          >
            <h2 id="delete-theme-heading">Delete {pendingDelete.name}?</h2>
            <p>
              This removes {pendingDelete.name} and its elements. This cannot be undone.
            </p>
            <ErrorBanner error={deleteError} />
            <div className="button-row">
              <button
                id="confirm-delete-theme"
                type="button"
                className="danger"
                disabled={!canWrite || isDeleting}
                onClick={(): void => {
                  void handleConfirmDelete();
                }}
              >
                {isDeleting ? "Deleting…" : "Delete theme"}
              </button>
              <button
                id="cancel-delete-theme"
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

interface ThemePreviewReport extends ThemePreviewElementState {
  themeId: string;
}

interface ThemeDetailViewProps {
  selectedTheme: ThemeReadResponse | null;
  loadError: unknown;
  statusMessage: string;
  onBack: () => void;
  onThemeSaved: (updatedTheme: ThemeReadResponse) => void;
  onThemeDuplicated: (copiedTheme: ThemeReadResponse) => void;
}

function ThemeDetailView({
  selectedTheme,
  loadError,
  statusMessage,
  onBack,
  onThemeSaved,
  onThemeDuplicated,
}: ThemeDetailViewProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [editedDraft, setEditedDraft] = useState<ThemeFrameDraft | null>(null);
  const [previewReport, setPreviewReport] = useState<ThemePreviewReport | null>(null);
  const [editedForThemeId, setEditedForThemeId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [isDuplicating, setIsDuplicating] = useState<boolean>(false);
  const [elementAutosaveState, setElementAutosaveState] = useState<ThemeAutosaveState>({
    phase: "idle",
    message: "",
    canRetry: false,
  });
  const selectedThemeRef = useRef(selectedTheme);
  const elementActionsRef = useRef<ThemeAutosaveActions | null>(null);
  const notedFrameIdRef = useRef<string | null>(null);
  selectedThemeRef.current = selectedTheme;
  const frameDraft: ThemeFrameDraft | null = frameDraftForTheme(
    selectedTheme,
    editedDraft,
    editedForThemeId,
  );
  const frameAutosave = useThemeAutosave<ThemeFrameDraft>({
    delayMs: THEME_AUTOSAVE_DELAY_MS,
    readiness: (nextDraft: ThemeFrameDraft) => {

      if (!canWrite) {
        return { kind: "skip" };
      }

      try {
        themePatchFromFrameDraft(nextDraft);

        return { kind: "ready" };
      } catch (caughtError: unknown) {
        const message: string = caughtError instanceof Error
          ? caughtError.message
          : String(caughtError);

        return { kind: "invalid", message };
      }
    },
    fingerprint: (nextDraft: ThemeFrameDraft): string => {
      return JSON.stringify(themePatchFromFrameDraft(nextDraft));
    },
    save: async (nextDraft: ThemeFrameDraft): Promise<void> => {
      const theme: ThemeReadResponse | null = selectedThemeRef.current;

      if (theme === null) {
        return;
      }

      const updatedTheme: ThemeReadResponse = await patchTheme(
        theme.id,
        themePatchFromFrameDraft(nextDraft),
      );
      onThemeSaved(updatedTheme);
    },
    formatError: formatThemeAutosaveError,
  });
  const autosaveState: ThemeAutosaveState = combineAutosaveStates([
    frameAutosave.state,
    elementAutosaveState,
  ]);
  const savedPreview: ThemePreviewElementState | null = selectedTheme === null
    ? null
    : previewElementStateFromElements(selectedTheme.elements);
  const activePreview: ThemePreviewElementState | null = (
    previewReport !== null
    && selectedTheme !== null
    && previewReport.themeId === selectedTheme.id
  )
    ? previewReport
    : savedPreview;
  const fieldsDisabled: boolean = !canWrite || isDuplicating;
  const duplicateDisabled: boolean = !canWrite || isDuplicating || selectedTheme === null;

  const rememberDraft = (nextDraft: ThemeFrameDraft): void => {

    if (selectedTheme === null) {
      return;
    }

    setEditedForThemeId(selectedTheme.id);
    setEditedDraft(nextDraft);
    setActionError(null);
  };

  const flushThemeEdits = async (): Promise<void> => {

    await Promise.all([
      frameAutosave.flush(),
      elementActionsRef.current?.flush() ?? Promise.resolve(),
    ]);
  };

  const themeEditsAreDirty = (): boolean => {

    return frameAutosave.isDirty() || (elementActionsRef.current?.isDirty() ?? false);
  };

  const retryAutosave = (): void => {
    void frameAutosave.retry();
    void elementActionsRef.current?.retry();
  };

  const selectedThemeId: string | null = selectedTheme === null ? null : selectedTheme.id;

  useEffect((): void => {
    const theme: ThemeReadResponse | null = selectedThemeRef.current;

    if (!canWrite || theme === null || frameDraft === null) {
      return;
    }

    if (notedFrameIdRef.current !== theme.id) {
      notedFrameIdRef.current = theme.id;
      frameAutosave.noteSaved(frameDraftFromTheme(theme));
    }

    frameAutosave.schedule(frameDraft);
  }, [
    canWrite,
    frameAutosave.noteSaved,
    frameAutosave.schedule,
    frameDraft,
    selectedThemeId,
  ]);

  const handleDuplicate = async (): Promise<void> => {

    if (!canWrite || selectedTheme === null) {
      return;
    }

    setIsDuplicating(true);
    setActionError(null);

    try {
      await flushThemeEdits();

      if (themeEditsAreDirty()) {
        return;
      }

      const copiedTheme: ThemeReadResponse = await duplicateTheme(selectedTheme.id);

      onThemeDuplicated(copiedTheme);
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setIsDuplicating(false);
    }
  };

  const handleBack = (): void => {
    void leaveAfterAutosave(flushThemeEdits, themeEditsAreDirty, onBack);
  };

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>{selectedTheme === null ? "Theme" : selectedTheme.name}</h1>
          <p className="lede">
            Background, spacing, and full-width elements.
            Edits save on their own.
          </p>
          <ThemeAutosaveStatus state={autosaveState} onRetry={retryAutosave} />
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

      {selectedTheme === null || frameDraft === null ? (
        loadError === null ? <p>Loading theme…</p> : null
      ) : (
        <>
          <div className="theme-editor-layout">
          <div className="theme-editor-main">
          <dl className="campaign-detail-list">
            <dt>Name</dt>
            <dd>{selectedTheme.name}</dd>
            <dt>Slug</dt>
            <dd className="mono">{selectedTheme.slug}</dd>
            <dt>Advertisement type</dt>
            <dd>{advertisementTypeLabel(selectedTheme.advertisement_type)}</dd>
            <dt>Template</dt>
            <dd className="mono">{formatThemeTemplateKey(selectedTheme.template_key)}</dd>
            <dt>Created</dt>
            <dd className="mono">{formatThemeTimestamp(selectedTheme.created_at)}</dd>
            <dt>Updated</dt>
            <dd className="mono">{formatThemeTimestamp(selectedTheme.updated_at)}</dd>
          </dl>

          <form
            className="stack-form campaign-form"
            onSubmit={(formEvent: FormEvent): void => {
              formEvent.preventDefault();
              void frameAutosave.flush();
            }}
          >
            <ThemeFrameFields
              frameDraft={frameDraft}
              onDraftChange={rememberDraft}
              disabled={fieldsDisabled}
            />
          </form>
          <ThemeElementEditor
            theme={selectedTheme}
            onThemeUpdated={onThemeSaved}
            onElementPatched={(patchedElement: ThemeElementReadResponse): void => {
              const currentTheme: ThemeReadResponse | null = selectedThemeRef.current;

              if (currentTheme === null) {
                return;
              }

              const nextElements: ThemeElementReadResponse[] = currentTheme.elements.map(
                (element: ThemeElementReadResponse): ThemeElementReadResponse => {

                  if (element.id !== patchedElement.id) {
                    return element;
                  }

                  return patchedElement;
                },
              );
              onThemeSaved({
                ...currentTheme,
                elements: nextElements,
              });
            }}
            onAutosaveStateChange={setElementAutosaveState}
            autosaveActionsRef={elementActionsRef}
            onPreviewElementsChange={(
              elements: ThemeElementCreateRequest[] | null,
              draftError: string | null,
            ): void => {
              if (selectedTheme === null) {
                return;
              }

              setPreviewReport({
                themeId: selectedTheme.id,
                elements,
                draftError,
              });
            }}
          />
          </div>
            <ThemeLivePreview
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

function replaceThemeInList(
  themes: ThemeReadResponse[],
  updatedTheme: ThemeReadResponse,
): ThemeReadResponse[] {

  const nextThemes: ThemeReadResponse[] = themes.map(
    (theme: ThemeReadResponse): ThemeReadResponse => {

      if (theme.id !== updatedTheme.id) {
        return theme;
      }

      return updatedTheme;
    },
  );

  return nextThemes;
}

function frameDraftForTheme(
  theme: ThemeReadResponse | null,
  editedDraft: ThemeFrameDraft | null,
  editedForThemeId: string | null,
): ThemeFrameDraft | null {

  if (theme === null) {
    return null;
  }

  if (editedDraft !== null && editedForThemeId === theme.id) {
    return editedDraft;
  }

  const frameDraft: ThemeFrameDraft = frameDraftFromTheme(theme);

  return frameDraft;
}
