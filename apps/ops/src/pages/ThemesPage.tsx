import { useEffect, useState, type FormEvent, type ReactElement } from "react";

import {
  deleteTheme,
  duplicateTheme,
  fetchThemeById,
  listThemes,
  patchTheme,
} from "../api/client";
import type {
  ThemeElementCreateRequest,
  ThemePatchRequest,
  ThemeReadResponse,
} from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import { useCanWriteOps } from "../session/OpsSessionContext";
import { ThemeElementEditor } from "./ThemeElementEditor";
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
  themeStatusLabel,
} from "./themeDisplay";

export interface ThemesPageProps {
  statusMessage: string;
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
export function ThemesPage({ statusMessage }: ThemesPageProps): ReactElement {

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
  onSelectTheme: (themeId: string) => void;
  onThemeDeleted: (themeId: string) => void;
}

function ThemeListView({
  themes,
  loadError,
  statusMessage,
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
            Create lives on Create Theme. Delete asks before it removes a row.
          </p>
        </div>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}

      {loadError !== null ? null : themes.length === 0 ? (
        <p>No themes yet. Use Create Theme to save a carousel theme.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
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
                <td>{themeStatusLabel(theme.status)}</td>
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
  const [previewElements, setPreviewElements] = useState<ThemeElementCreateRequest[] | null>(
    null,
  );
  const [previewDraftError, setPreviewDraftError] = useState<string | null>(null);
  const [editedForKey, setEditedForKey] = useState<string | null>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [isBusy, setIsBusy] = useState<boolean>(false);
  const [isDuplicating, setIsDuplicating] = useState<boolean>(false);
  const [saveMessage, setSaveMessage] = useState<string>("");
  const [saveMessageKey, setSaveMessageKey] = useState<string | null>(null);
  const themeKey: string | null = themeFrameKey(selectedTheme);
  const frameDraft: ThemeFrameDraft | null = frameDraftForTheme(
    selectedTheme,
    themeKey,
    editedDraft,
    editedForKey,
  );
  const visibleSaveMessage: string = saveMessageKey === themeKey ? saveMessage : "";
  const fieldsDisabled: boolean = !canWrite || isBusy || isDuplicating;
  const duplicateDisabled: boolean = !canWrite || isBusy || isDuplicating || selectedTheme === null;

  const rememberDraft = (nextDraft: ThemeFrameDraft): void => {

    if (themeKey === null) {
      return;
    }

    setEditedForKey(themeKey);
    setEditedDraft(nextDraft);
    setActionError(null);
  };

  const handleSaveFrame = async (formEvent: FormEvent): Promise<void> => {

    formEvent.preventDefault();

    if (!canWrite || selectedTheme === null || frameDraft === null) {
      return;
    }

    setIsBusy(true);
    setActionError(null);
    setSaveMessage("");

    try {
      const themePatchRequest: ThemePatchRequest = themePatchFromFrameDraft(frameDraft);
      await patchTheme(selectedTheme.id, themePatchRequest);
      const reloadedTheme: ThemeReadResponse = await fetchThemeById(selectedTheme.id);
      const reloadedKey: string | null = themeFrameKey(reloadedTheme);

      onThemeSaved(reloadedTheme);
      setEditedDraft(null);
      setEditedForKey(null);
      setSaveMessage("Frame saved.");
      setSaveMessageKey(reloadedKey);
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setIsBusy(false);
    }
  };

  const handleDuplicate = async (): Promise<void> => {

    if (!canWrite || selectedTheme === null) {
      return;
    }

    setIsDuplicating(true);
    setActionError(null);

    try {
      const copiedTheme: ThemeReadResponse = await duplicateTheme(selectedTheme.id);

      onThemeDuplicated(copiedTheme);
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setIsDuplicating(false);
    }
  };

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>{selectedTheme === null ? "Theme" : selectedTheme.name}</h1>
          <p className="lede">
            Draft or Live, background, spacing, and full-width elements.
          </p>
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
          <button type="button" onClick={onBack} disabled={isDuplicating}>
            Back to list
          </button>
        </div>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      <ErrorBanner error={actionError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}
      {visibleSaveMessage !== "" ? (
        <p className="status-banner">{visibleSaveMessage}</p>
      ) : null}

      {selectedTheme === null || frameDraft === null ? (
        loadError === null ? <p>Loading theme…</p> : null
      ) : (
        <>
          <div className="theme-editor-layout">
            <ThemeLivePreview
              frameDraft={frameDraft}
              elements={previewElements}
              draftError={previewDraftError}
            />
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
              void handleSaveFrame(formEvent);
            }}
          >
            <ThemeFrameFields
              frameDraft={frameDraft}
              onDraftChange={rememberDraft}
              disabled={fieldsDisabled}
            />
            <div className="button-row">
              <button type="submit" disabled={fieldsDisabled}>
                {isBusy ? "Saving…" : "Save frame"}
              </button>
            </div>
          </form>
          <ThemeElementEditor
            theme={selectedTheme}
            onThemeUpdated={onThemeSaved}
            onPreviewElementsChange={(
              elements: ThemeElementCreateRequest[] | null,
              draftError: string | null,
            ): void => {
              setPreviewElements(elements);
              setPreviewDraftError(draftError);
            }}
          />
          </div>
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

function themeFrameKey(theme: ThemeReadResponse | null): string | null {

  if (theme === null) {
    return null;
  }

  const frameKey: string = `${theme.id}:${theme.updated_at}`;

  return frameKey;
}

function frameDraftForTheme(
  theme: ThemeReadResponse | null,
  themeKey: string | null,
  editedDraft: ThemeFrameDraft | null,
  editedForKey: string | null,
): ThemeFrameDraft | null {

  if (theme === null) {
    return null;
  }

  if (editedDraft !== null && editedForKey === themeKey) {
    return editedDraft;
  }

  const frameDraft: ThemeFrameDraft = frameDraftFromTheme(theme);

  return frameDraft;
}
