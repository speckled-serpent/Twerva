import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactElement,
} from "react";

import {
  createThemeElement,
  deleteThemeElement,
  fetchThemeById,
  patchThemeElement,
} from "../api/client";
import type {
  ThemeElementAlignment,
  ThemeElementBand,
  ThemeElementContentKind,
  ThemeElementCreateRequest,
  ThemeElementPatchRequest,
  ThemeElementReadResponse,
  ThemeElementTextSource,
  ThemeReadResponse,
} from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { useCanWriteOps } from "../session/OpsSessionContext";
import {
  THEME_AUTOSAVE_DELAY_MS,
  combineAutosaveStates,
  formatThemeAutosaveError,
  type ThemeAutosaveActions,
  type ThemeAutosaveState,
} from "./themeAutosave";
import { useThemeAutosave } from "./useThemeAutosave";
import { ThemeAssetAlbumField, loadThemePickerAlbums } from "./ThemeAssetAlbumField";
import { ThemeFontFamilyField } from "./ThemeFontFamilyField";
import { normalizeHexColor } from "./themeColors";
import { pickDefaultAlbumImage, type ThemeImageAlbum } from "./themeAssets";
import { DEFAULT_FONT_FAMILY } from "./themeFonts";

export interface ThemeElementEditorProps {
  theme: ThemeReadResponse;
  onThemeUpdated: (updatedTheme: ThemeReadResponse) => void;
  onLocalElementsChange?: (nextElements: ThemeElementReadResponse[]) => void;
  onPreviewElementsChange?: (
    elements: ThemeElementCreateRequest[] | null,
    draftError: string | null,
  ) => void;
  onElementPatched?: (element: ThemeElementReadResponse) => void;
  onValidationMessageChange?: (message: string | null) => void;
  onAutosaveStateChange?: (state: ThemeAutosaveState) => void;
  autosaveActionsRef?: { current: ThemeAutosaveActions | null };
}

interface BandOption {
  value: ThemeElementBand;
  label: string;
}

interface ElementDraft {
  name: string;
  band: ThemeElementBand;
  contentKind: ThemeElementContentKind;
  rectangleColor: string;
  rectangleOpacity: string;
  rectangleRadius: string;
  textSource: ThemeElementTextSource | null;
  fontFamily: string;
  fontSize: string;
  fontColor: string;
  bold: boolean;
  italic: boolean;
  underline: boolean;
  strikethrough: boolean;
  fontWeight: string;
  alignment: ThemeElementAlignment;
  imageAssetRef: string;
}

const BAND_OPTIONS: BandOption[] = [
  { value: "top", label: "Top" },
  { value: "middle", label: "Middle" },
  { value: "bottom", label: "Bottom" },
];

/**
 * Add, edit, delete, reorder, and move theme elements. No placement fields.
 *
 * When `onLocalElementsChange` is set, edits stay in memory for Create Theme.
 *
 * @param props - The open theme and a callback after each saved change
 * @returns The element editor under the frame form
 */
export function ThemeElementEditor({
  theme,
  onThemeUpdated,
  onLocalElementsChange,
  onPreviewElementsChange,
  onElementPatched,
  onValidationMessageChange,
  onAutosaveStateChange,
  autosaveActionsRef,
}: ThemeElementEditorProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [addDraft, setAddDraft] = useState<ElementDraft>(emptyElementDraft());
  const [isAddOpen, setIsAddOpen] = useState<boolean>(false);
  const [expandedElementIds, setExpandedElementIds] = useState<Record<string, boolean>>({});
  const [cardDrafts, setCardDrafts] = useState<Record<string, ElementDraft>>({});
  const [draftErrors, setDraftErrors] = useState<Record<string, string>>({});
  const [cardAutosaveStates, setCardAutosaveStates] = useState<
    Record<string, ThemeAutosaveState>
  >({});
  const [actionError, setActionError] = useState<unknown>(null);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const previewCallbackRef = useRef(onPreviewElementsChange);
  const lastPreviewKeyRef = useRef<string | null>(null);
  const themeRef = useRef(theme);
  const onThemeUpdatedRef = useRef(onThemeUpdated);
  const onLocalElementsChangeRef = useRef(onLocalElementsChange);
  const onElementPatchedRef = useRef(onElementPatched);
  const onValidationMessageChangeRef = useRef(onValidationMessageChange);
  const onAutosaveStateChangeRef = useRef(onAutosaveStateChange);
  const reloadSerialRef = useRef(0);
  const cardActionsRef = useRef<Map<string, ThemeAutosaveActions>>(new Map());
  previewCallbackRef.current = onPreviewElementsChange;
  themeRef.current = theme;
  onThemeUpdatedRef.current = onThemeUpdated;
  onLocalElementsChangeRef.current = onLocalElementsChange;
  onElementPatchedRef.current = onElementPatched;
  onValidationMessageChangeRef.current = onValidationMessageChange;
  onAutosaveStateChangeRef.current = onAutosaveStateChange;
  const fieldsDisabled: boolean = !canWrite || busyKey !== null;
  const isLocal: boolean = onLocalElementsChange !== undefined;
  const validationMessage: string | null = firstDraftError(draftErrors);
  const elementAutosaveState: ThemeAutosaveState = combineAutosaveStates(
    Object.values(cardAutosaveStates),
  );
  const elementAutosaveKey: string = [
    elementAutosaveState.phase,
    elementAutosaveState.message,
    elementAutosaveState.canRetry ? "retry" : "noretry",
  ].join("|");

  const reloadTheme = async (): Promise<ThemeReadResponse | null> => {

    const serial: number = reloadSerialRef.current + 1;
    reloadSerialRef.current = serial;
    const reloadedTheme: ThemeReadResponse = await fetchThemeById(themeRef.current.id);

    if (serial !== reloadSerialRef.current) {
      return null;
    }

    onThemeUpdatedRef.current(reloadedTheme);

    return reloadedTheme;
  };

  const publishLocalElements = (nextElements: ThemeElementReadResponse[]): void => {

    if (onLocalElementsChangeRef.current === undefined) {
      return;
    }

    onLocalElementsChangeRef.current(nextElements);
  };

  const handleCardDraftChange = useCallback((elementId: string, draft: ElementDraft): void => {

    setCardDrafts((currentDrafts: Record<string, ElementDraft>): Record<string, ElementDraft> => {
      const previousDraft: ElementDraft | undefined = currentDrafts[elementId];

      if (previousDraft !== undefined && JSON.stringify(previousDraft) === JSON.stringify(draft)) {
        return currentDrafts;
      }

      return { ...currentDrafts, [elementId]: draft };
    });
  }, []);

  const handleDraftError = useCallback((elementId: string, message: string | null): void => {

    setDraftErrors((currentErrors: Record<string, string>): Record<string, string> => {

      if (message === null || message === "") {

        if (!(elementId in currentErrors)) {
          return currentErrors;
        }

        const nextErrors: Record<string, string> = { ...currentErrors };

        delete nextErrors[elementId];

        return nextErrors;
      }

      if (currentErrors[elementId] === message) {
        return currentErrors;
      }

      return { ...currentErrors, [elementId]: message };
    });
  }, []);

  const handleCardAutosaveState = useCallback((
    elementId: string,
    autosaveState: ThemeAutosaveState | null,
  ): void => {

    setCardAutosaveStates((
      currentStates: Record<string, ThemeAutosaveState>,
    ): Record<string, ThemeAutosaveState> => {

      if (autosaveState === null) {

        if (!(elementId in currentStates)) {
          return currentStates;
        }

        const nextStates: Record<string, ThemeAutosaveState> = { ...currentStates };

        delete nextStates[elementId];

        return nextStates;
      }

      const previousState: ThemeAutosaveState | undefined = currentStates[elementId];

      if (
        previousState !== undefined
        && previousState.phase === autosaveState.phase
        && previousState.message === autosaveState.message
        && previousState.canRetry === autosaveState.canRetry
      ) {
        return currentStates;
      }

      return { ...currentStates, [elementId]: autosaveState };
    });
  }, []);

  const handleBindAutosave = useCallback((
    elementId: string,
    actions: ThemeAutosaveActions | null,
  ): void => {

    if (actions === null) {
      cardActionsRef.current.delete(elementId);

      return;
    }

    cardActionsRef.current.set(elementId, actions);
  }, []);

  const handleAddElement = async (formEvent: FormEvent): Promise<void> => {

    formEvent.preventDefault();

    if (!canWrite) {
      return;
    }

    setBusyKey("add");
    setActionError(null);
    setStatusMessage("");

    try {
      const draftToAdd: ElementDraft = await draftReadyToAdd(addDraft);
      const createRequest: ThemeElementCreateRequest = elementRequestFromDraft(draftToAdd);

      if (isLocal) {
        const createdElement: ThemeElementReadResponse = localElementFromRequest(
          theme.id,
          theme.elements,
          createRequest,
        );

        publishLocalElements([...theme.elements, createdElement]);
        setAddDraft(emptyElementDraft());
        setIsAddOpen(false);
        setStatusMessage("Element added. It is stored when you pause.");
      } else {
        await createThemeElement(theme.id, createRequest);
        await reloadTheme();
        setAddDraft(emptyElementDraft());
        setIsAddOpen(false);
        setStatusMessage("Element added.");
      }
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setBusyKey(null);
    }
  };

  const handleLocalSave = (elementId: string, draft: ElementDraft): void => {

    const currentElements: ThemeElementReadResponse[] = themeRef.current.elements;
    const currentElement: ThemeElementReadResponse | undefined = currentElements.find(
      (element: ThemeElementReadResponse): boolean => element.id === elementId,
    );

    if (currentElement === undefined) {
      return;
    }

    try {
      const request: ThemeElementCreateRequest = elementRequestFromDraft(draft);
      const currentRequest: ThemeElementCreateRequest = themeElementCreateRequestFromElement(
        currentElement,
      );

      if (JSON.stringify(request) === JSON.stringify(currentRequest)) {
        return;
      }

      const updatedElement: ThemeElementReadResponse = applyRequestToElement(
        currentElement,
        request,
      );

      publishLocalElements(
        placeSavedLocalElement(currentElements, currentElement, updatedElement),
      );
    } catch {
      return;
    }
  };

  const handleLocalDelete = (elementId: string): void => {

    publishLocalElements(deleteLocalElement(theme.elements, elementId));
  };

  const handleLocalMove = (elementId: string, nextSortOrder: number): void => {

    publishLocalElements(moveLocalElement(theme.elements, elementId, nextSortOrder));
  };

  useEffect((): void => {
    onValidationMessageChangeRef.current?.(validationMessage);
  }, [validationMessage]);

  const elementAutosaveStateRef = useRef(elementAutosaveState);
  elementAutosaveStateRef.current = elementAutosaveState;

  useEffect((): void => {
    onAutosaveStateChangeRef.current?.(elementAutosaveStateRef.current);
  }, [elementAutosaveKey]);

  if (autosaveActionsRef !== undefined) {
    autosaveActionsRef.current = {
      flush: (): Promise<void> => {
        const actions: ThemeAutosaveActions[] = [...cardActionsRef.current.values()];

        return Promise.all(actions.map(
          (action: ThemeAutosaveActions): Promise<void> => action.flush(),
        )).then((): void => {
          return;
        });
      },
      retry: (): Promise<void> => {
        const actions: ThemeAutosaveActions[] = [...cardActionsRef.current.values()];

        return Promise.all(actions.map(
          (action: ThemeAutosaveActions): Promise<void> => action.retry(),
        )).then((): void => {
          return;
        });
      },
      abandon: (): Promise<void> => {
        const actions: ThemeAutosaveActions[] = [...cardActionsRef.current.values()];

        return Promise.all(actions.map(
          (action: ThemeAutosaveActions): Promise<void> => action.abandon(),
        )).then((): void => {
          return;
        });
      },
      isDirty: (): boolean => {
        const actions: ThemeAutosaveActions[] = [...cardActionsRef.current.values()];

        return actions.some((action: ThemeAutosaveActions): boolean => action.isDirty());
      },
    };
  }

  useEffect((): void => {
    const previewCallback = previewCallbackRef.current;

    if (previewCallback === undefined) {
      return;
    }

    try {
      const requests: ThemeElementCreateRequest[] = previewRequestsFromElements(
        theme.elements,
        cardDrafts,
      );
      const previewKey: string = `${theme.id}:${JSON.stringify(requests)}`;

      if (previewKey === lastPreviewKeyRef.current) {
        return;
      }

      lastPreviewKeyRef.current = previewKey;
      previewCallback(requests, null);
    } catch (caughtError: unknown) {
      const message: string = caughtError instanceof Error
        ? caughtError.message
        : String(caughtError);
      const previewKey: string = `${theme.id}:error:${message}`;

      if (previewKey === lastPreviewKeyRef.current) {
        return;
      }

      lastPreviewKeyRef.current = previewKey;
      previewCallback(null, message);
    }
  }, [theme.id, theme.elements, cardDrafts]);

  useEffect((): (() => void) => {

    if (!isAddOpen) {
      return (): void => {
        return;
      };
    }

    const handleKeyDown = (keyEvent: KeyboardEvent): void => {

      if (keyEvent.key !== "Escape") {
        return;
      }

      setIsAddOpen(false);
    };

    window.addEventListener("keydown", handleKeyDown);

    return (): void => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isAddOpen]);

  const closeAddDialog = (): void => {

    setIsAddOpen(false);
  };

  return (
    <section className="summary-block">
      <h2>Elements</h2>
      {isAddOpen ? null : <ErrorBanner error={actionError} />}
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}
      <div className="button-row">
        <button
          type="button"
          disabled={fieldsDisabled}
          onClick={(): void => {
            setActionError(null);
            setIsAddOpen(true);
          }}
        >
          Add element
        </button>
      </div>

      {isAddOpen ? (
        <div
          className="confirm-backdrop"
          onClick={closeAddDialog}
        >
          <div
            className="confirm-dialog theme-add-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="add-element-heading"
            onClick={(clickEvent): void => {
              clickEvent.stopPropagation();
            }}
          >
            <button
              type="button"
              className="dialog-close"
              aria-label="Close"
              onClick={closeAddDialog}
            >
              ×
            </button>
            <h2 id="add-element-heading">Add element</h2>
            <form
              className="stack-form"
              onSubmit={(formEvent: FormEvent): void => {
                void handleAddElement(formEvent);
              }}
            >
              <ErrorBanner error={actionError} />
              <fieldset className="form-fieldset" disabled={fieldsDisabled}>
                <ElementFields
                  draft={addDraft}
                  onDraftChange={setAddDraft}
                  idPrefix="add-element"
                  showDetails={false}
                  autoFocusName={true}
                />
              </fieldset>
              <div className="button-row">
                <button type="submit" disabled={fieldsDisabled}>
                  {busyKey === "add" ? "Adding…" : "Add"}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      {BAND_OPTIONS.map((bandOption: BandOption): ReactElement | null => {
        const bandElements: ThemeElementReadResponse[] = elementsInBand(
          theme.elements,
          bandOption.value,
        );

        if (bandElements.length === 0) {
          return null;
        }

        return (
          <div className="theme-band" key={bandOption.value}>
            <h3>{bandOption.label}</h3>
            {bandElements.map(
              (element: ThemeElementReadResponse, elementIndex: number): ReactElement => (
                <ThemeElementCard
                  key={element.id}
                  themeId={theme.id}
                  element={element}
                  elementIndex={elementIndex}
                  bandLength={bandElements.length}
                  fieldsDisabled={fieldsDisabled}
                  isExpanded={expandedElementIds[element.id] === true}
                  onExpandedChange={(nextExpanded: boolean): void => {
                    setExpandedElementIds(
                      (currentIds: Record<string, boolean>): Record<string, boolean> => {

                        return { ...currentIds, [element.id]: nextExpanded };
                      },
                    );
                  }}
                  onError={setActionError}
                  onReload={async (message: string): Promise<void> => {
                    setStatusMessage(message);

                    if (!isLocal) {
                      await reloadTheme();
                    }
                  }}
                  onBusy={(isBusy: boolean): void => {
                    setBusyKey(isBusy ? element.id : null);
                  }}
                  onLocalSave={isLocal ? handleLocalSave : undefined}
                  onLocalDelete={isLocal ? handleLocalDelete : undefined}
                  onLocalMove={isLocal ? handleLocalMove : undefined}
                  onDraftChange={handleCardDraftChange}
                  onDraftError={handleDraftError}
                  onAutosaveState={handleCardAutosaveState}
                  onBindAutosave={handleBindAutosave}
                  onElementPatched={(patchedElement: ThemeElementReadResponse): void => {
                    onElementPatchedRef.current?.(patchedElement);
                  }}
                />
              ),
            )}
          </div>
        );
      })}
    </section>
  );
}

interface ThemeElementCardProps {
  themeId: string;
  element: ThemeElementReadResponse;
  elementIndex: number;
  bandLength: number;
  fieldsDisabled: boolean;
  isExpanded: boolean;
  onExpandedChange: (nextExpanded: boolean) => void;
  onError: (error: unknown) => void;
  onReload: (message: string) => Promise<void>;
  onBusy: (isBusy: boolean) => void;
  onLocalSave?: (elementId: string, draft: ElementDraft) => void;
  onLocalDelete?: (elementId: string) => void;
  onLocalMove?: (elementId: string, nextSortOrder: number) => void;
  onDraftChange: (elementId: string, draft: ElementDraft) => void;
  onDraftError: (elementId: string, message: string | null) => void;
  onAutosaveState: (elementId: string, state: ThemeAutosaveState | null) => void;
  onBindAutosave: (elementId: string, actions: ThemeAutosaveActions | null) => void;
  onElementPatched: (element: ThemeElementReadResponse) => void;
}

function ThemeElementCard({
  themeId,
  element,
  elementIndex,
  bandLength,
  fieldsDisabled,
  isExpanded,
  onExpandedChange,
  onError,
  onReload,
  onBusy,
  onLocalSave,
  onLocalDelete,
  onLocalMove,
  onDraftChange,
  onDraftError,
  onAutosaveState,
  onBindAutosave,
  onElementPatched,
}: ThemeElementCardProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [draft, setDraft] = useState<ElementDraft>(draftFromElement(element));
  const isLocal: boolean = onLocalSave !== undefined;
  const themeIdRef = useRef(themeId);
  const elementRef = useRef(element);
  const onReloadRef = useRef(onReload);
  const onElementPatchedRef = useRef(onElementPatched);
  const notedElementIdRef = useRef<string | null>(null);
  themeIdRef.current = themeId;
  elementRef.current = element;
  onReloadRef.current = onReload;
  onElementPatchedRef.current = onElementPatched;
  const draftError: string | null = readElementDraftError(draft);
  const autosave = useThemeAutosave<ElementDraft>({
    delayMs: THEME_AUTOSAVE_DELAY_MS,
    readiness: (nextDraft: ElementDraft) => {

      if (isLocal || !canWrite) {
        return { kind: "skip" };
      }

      const message: string | null = readElementDraftError(nextDraft);

      if (message !== null) {
        return { kind: "invalid", message };
      }

      return { kind: "ready" };
    },
    fingerprint: (nextDraft: ElementDraft): string => {
      return JSON.stringify(elementRequestFromDraft(nextDraft));
    },
    save: async (nextDraft: ElementDraft): Promise<void> => {
      const patchRequest: ThemeElementPatchRequest = elementRequestFromDraft(nextDraft);
      const patchedElement: ThemeElementReadResponse = await patchThemeElement(
        themeIdRef.current,
        elementRef.current.id,
        patchRequest,
      );

      if (nextDraft.band !== elementRef.current.band) {
        await onReloadRef.current("Element moved.");

        return;
      }

      onElementPatchedRef.current(patchedElement);
    },
    formatError: formatThemeAutosaveError,
  });
  const canMoveEarlier: boolean = canWrite && elementIndex > 0 && draft.band === element.band;
  const canMoveLater: boolean = (
    canWrite
    && elementIndex < bandLength - 1
    && draft.band === element.band
  );

  useEffect((): void => {
    onDraftChange(element.id, draft);
    onDraftError(element.id, draftError);

    if (!isLocal || draftError !== null || onLocalSave === undefined) {
      return;
    }

    onLocalSave(element.id, draft);
  }, [draft, draftError, element.id, isLocal, onDraftChange, onDraftError, onLocalSave]);

  useEffect((): void => {

    if (isLocal || !canWrite) {
      return;
    }

    if (notedElementIdRef.current !== element.id) {
      notedElementIdRef.current = element.id;
      autosave.noteSaved(draftFromElement(element));
    }

    autosave.schedule(draft);
  }, [autosave.noteSaved, autosave.schedule, canWrite, draft, element.id, isLocal]);

  useEffect((): void | (() => void) => {

    if (isLocal) {
      onBindAutosave(element.id, null);

      return;
    }

    onBindAutosave(element.id, autosave);

    return (): void => {
      onBindAutosave(element.id, null);
    };
  }, [
    autosave.flush,
    autosave.retry,
    autosave.abandon,
    autosave.isDirty,
    element.id,
    isLocal,
    onBindAutosave,
  ]);

  useEffect((): void | (() => void) => {

    if (isLocal) {
      onAutosaveState(element.id, null);

      return;
    }

    onAutosaveState(element.id, autosave.state);

    return (): void => {
      onAutosaveState(element.id, null);
    };
  }, [
    autosave.state.phase,
    autosave.state.message,
    autosave.state.canRetry,
    element.id,
    isLocal,
    onAutosaveState,
  ]);

  const handleDelete = async (): Promise<void> => {

    if (!canWrite) {
      return;
    }

    onBusy(true);
    onError(null);

    try {
      await autosave.abandon();

      if (onLocalDelete !== undefined) {
        onLocalDelete(element.id);
        await onReload("Element removed. It is stored when you pause.");

        return;
      }

      await deleteThemeElement(themeId, element.id);
      await onReload("Element deleted.");
    } catch (caughtError: unknown) {
      onError(caughtError);
    } finally {
      onBusy(false);
    }
  };

  const handleMove = async (nextSortOrder: number): Promise<void> => {

    if (!canWrite) {
      return;
    }

    onBusy(true);
    onError(null);

    try {
      await autosave.flush();

      if (onLocalMove !== undefined) {
        onLocalMove(element.id, nextSortOrder);
        await onReload("Element moved. It is stored when you pause.");

        return;
      }

      await patchThemeElement(themeId, element.id, { sort_order: nextSortOrder });
      await onReload("Element moved.");
    } catch (caughtError: unknown) {
      onError(caughtError);
    } finally {
      onBusy(false);
    }
  };

  const elementTitle: string = draft.name.trim() === "" ? "Untitled element" : draft.name;

  return (
    <article className="card theme-element-card">
      <button
        type="button"
        className="theme-element-summary"
        aria-expanded={isExpanded}
        onClick={(): void => {
          onExpandedChange(!isExpanded);
        }}
      >
        <ChevronIcon expanded={isExpanded} />
        <span>{elementTitle}</span>
      </button>
      {isExpanded ? (
        <form
          className="stack-form"
          onSubmit={(formEvent: FormEvent): void => {
            formEvent.preventDefault();
            void autosave.flush();
          }}
        >
          <fieldset className="form-fieldset" disabled={fieldsDisabled}>
            <ElementFields
              draft={draft}
              onDraftChange={setDraft}
              idPrefix={`element-${element.id}`}
              showDetails={true}
            />
          </fieldset>
          {draftError !== null ? <p className="field-error">{draftError}</p> : null}
          <div className="button-row">
            <button
              type="button"
              className="icon-button"
              aria-label="Move up"
              title="Move up"
              disabled={!canMoveEarlier || fieldsDisabled}
              onClick={(): void => {
                void handleMove(element.sort_order - 1);
              }}
            >
              <MoveUpIcon />
            </button>
            <button
              type="button"
              className="icon-button"
              aria-label="Move down"
              title="Move down"
              disabled={!canMoveLater || fieldsDisabled}
              onClick={(): void => {
                void handleMove(element.sort_order + 1);
              }}
            >
              <MoveDownIcon />
            </button>
            <button
              type="button"
              className="danger"
              disabled={fieldsDisabled}
              onClick={(): void => {
                void handleDelete();
              }}
            >
              Delete element
            </button>
          </div>
        </form>
      ) : null}
    </article>
  );
}

function MoveUpIcon(): ReactElement {

  return (
    <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      <path
        fill="currentColor"
        d="M10 3.75 4.25 9.5l1.4 1.4L9 7.55V16.25h2V7.55l3.35 3.35 1.4-1.4L10 3.75Z"
      />
    </svg>
  );
}

function MoveDownIcon(): ReactElement {

  return (
    <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      <path
        fill="currentColor"
        d="M10 16.25 15.75 10.5l-1.4-1.4L11 12.45V3.75H9v8.7L5.65 9.1l-1.4 1.4L10 16.25Z"
      />
    </svg>
  );
}

interface ElementFieldsProps {
  draft: ElementDraft;
  onDraftChange: (nextDraft: ElementDraft) => void;
  idPrefix: string;
  showDetails: boolean;
  autoFocusName?: boolean;
}

function ElementFields({
  draft,
  onDraftChange,
  idPrefix,
  showDetails,
  autoFocusName = false,
}: ElementFieldsProps): ReactElement {

  return (
    <>
      <label>
        Name
        <input
          id={`${idPrefix}-name`}
          value={draft.name}
          spellCheck={false}
          autoFocus={autoFocusName}
          onChange={(changeEvent): void => {
            onDraftChange({ ...draft, name: changeEvent.target.value });
          }}
        />
      </label>
      <p className="field-hint">This name labels the field when you edit a unit.</p>
      <div className="paired-fields">
        <label>
          Band
          <select
            aria-label="Band"
            value={draft.band}
            onChange={(changeEvent): void => {
              const nextBand: string = changeEvent.target.value;

              if (!isThemeElementBand(nextBand)) {
                return;
              }

              onDraftChange({ ...draft, band: nextBand });
            }}
          >
            {BAND_OPTIONS.map((bandOption: BandOption): ReactElement => (
              <option key={bandOption.value} value={bandOption.value}>
                {bandOption.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Content
          <select
            aria-label="Content"
            value={draft.contentKind}
            onChange={(changeEvent): void => {
              const nextKind: string = changeEvent.target.value;

              if (!isContentKind(nextKind)) {
                return;
              }

              onDraftChange({ ...draft, contentKind: nextKind });
            }}
          >
            <option value="text">Text</option>
            <option value="image">Image</option>
          </select>
        </label>
      </div>
      {showDetails ? (
        <ElementDetailFields
          draft={draft}
          onDraftChange={onDraftChange}
          idPrefix={idPrefix}
        />
      ) : null}
    </>
  );
}

function ElementDetailFields({
  draft,
  onDraftChange,
  idPrefix,
}: Omit<ElementFieldsProps, "showDetails">): ReactElement {

  return (
    <>
      <RectangleStyleFields draft={draft} onDraftChange={onDraftChange} />
      {draft.contentKind === "text" ? (
        <TextElementFields
          draft={draft}
          onDraftChange={onDraftChange}
          idPrefix={idPrefix}
        />
      ) : (
        <ThemeAssetAlbumField
          idPrefix={`${idPrefix}-image`}
          label="Image"
          assetRef={draft.imageAssetRef}
          disabled={false}
          onAssetRefChange={(nextAssetRef: string): void => {
            onDraftChange({ ...draft, imageAssetRef: nextAssetRef });
          }}
        />
      )}
    </>
  );
}

interface TextElementFieldsProps {
  draft: ElementDraft;
  onDraftChange: (nextDraft: ElementDraft) => void;
  idPrefix: string;
}

function TextElementFields({
  draft,
  onDraftChange,
  idPrefix,
}: TextElementFieldsProps): ReactElement {

  return (
    <div className="theme-subsection">
      <p className="section-label">Text</p>
      <div className="text-toolbar">
        <ThemeFontFamilyField
          fontFamily={draft.fontFamily}
          idPrefix={idPrefix}
          compact={true}
          onFontFamilyChange={(nextFontFamily: string): void => {
            onDraftChange({ ...draft, fontFamily: nextFontFamily });
          }}
        />
        <label className="toolbar-field">
          <span className="toolbar-caption">Size</span>
          <input
            className="toolbar-input"
            type="number"
            min={1}
            step={1}
            value={draft.fontSize}
            aria-label="Font size"
            title="Font size"
            onChange={(changeEvent): void => {
              onDraftChange({ ...draft, fontSize: changeEvent.target.value });
            }}
          />
        </label>
        <label className="toolbar-field">
          <span className="toolbar-caption">Color</span>
          <input
            className="toolbar-input"
            value={draft.fontColor}
            aria-label="Font color"
            title="Font color"
            placeholder="#112233"
            spellCheck={false}
            onChange={(changeEvent): void => {
              onDraftChange({ ...draft, fontColor: changeEvent.target.value });
            }}
            onBlur={(blurEvent): void => {
              onDraftChange({
                ...draft,
                fontColor: normalizeHexColor(blurEvent.currentTarget.value),
              });
            }}
          />
        </label>
        <label className="toolbar-field">
          <span className="toolbar-caption">Weight</span>
          <input
            className="toolbar-input"
            type="number"
            min={1}
            max={1000}
            step={1}
            value={draft.fontWeight}
            aria-label="Font weight"
            title="Font weight, 1 through 1000. Blank stores none."
            placeholder="—"
            onChange={(changeEvent): void => {
              onDraftChange({ ...draft, fontWeight: changeEvent.target.value });
            }}
          />
        </label>
      </div>
      <div className="text-toolbar" role="toolbar" aria-label="Text style">
        <AlignButton
          alignment="left"
          label="Align left"
          pressed={draft.alignment === "left"}
          onSelect={(): void => {
            onDraftChange({ ...draft, alignment: "left" });
          }}
        />
        <AlignButton
          alignment="center"
          label="Align center"
          pressed={draft.alignment === "center"}
          onSelect={(): void => {
            onDraftChange({ ...draft, alignment: "center" });
          }}
        />
        <AlignButton
          alignment="right"
          label="Align right"
          pressed={draft.alignment === "right"}
          onSelect={(): void => {
            onDraftChange({ ...draft, alignment: "right" });
          }}
        />
        <StyleToggle
          label="Bold"
          pressed={draft.bold}
          markClassName="is-bold"
          mark="B"
          onToggle={(): void => {
            onDraftChange({ ...draft, bold: !draft.bold });
          }}
        />
        <StyleToggle
          label="Italic"
          pressed={draft.italic}
          markClassName="is-italic"
          mark="I"
          onToggle={(): void => {
            onDraftChange({ ...draft, italic: !draft.italic });
          }}
        />
        <StyleToggle
          label="Underline"
          pressed={draft.underline}
          markClassName="is-underline"
          mark="U"
          onToggle={(): void => {
            onDraftChange({ ...draft, underline: !draft.underline });
          }}
        />
        <StyleToggle
          label="Strikethrough"
          pressed={draft.strikethrough}
          markClassName="is-strike"
          mark="S"
          onToggle={(): void => {
            onDraftChange({ ...draft, strikethrough: !draft.strikethrough });
          }}
        />
      </div>
    </div>
  );
}

interface AlignButtonProps {
  alignment: ThemeElementAlignment;
  label: string;
  pressed: boolean;
  onSelect: () => void;
}

function AlignButton({
  alignment,
  label,
  pressed,
  onSelect,
}: AlignButtonProps): ReactElement {

  const pressedClass: string = pressed ? "toolbar-toggle is-pressed" : "toolbar-toggle";

  return (
    <button
      type="button"
      className={pressedClass}
      aria-label={label}
      aria-pressed={pressed}
      title={label}
      onClick={onSelect}
    >
      <AlignIcon alignment={alignment} />
    </button>
  );
}

interface StyleToggleProps {
  label: string;
  pressed: boolean;
  markClassName: string;
  mark: string;
  onToggle: () => void;
}

function StyleToggle({
  label,
  pressed,
  markClassName,
  mark,
  onToggle,
}: StyleToggleProps): ReactElement {

  const pressedClass: string = pressed ? "toolbar-toggle is-pressed" : "toolbar-toggle";
  const markClass: string = `toolbar-mark ${markClassName}`;

  return (
    <button
      type="button"
      className={pressedClass}
      aria-label={label}
      aria-pressed={pressed}
      title={label}
      onClick={onToggle}
    >
      <span className={markClass}>{mark}</span>
    </button>
  );
}

async function draftReadyToAdd(addDraft: ElementDraft): Promise<ElementDraft> {

  if (addDraft.contentKind === "text") {

    return addDraft;
  }

  const albums: ThemeImageAlbum[] = await loadThemePickerAlbums();
  const imageAssetRef: string = pickDefaultAlbumImage(albums, Math.random());
  const imageDraft: ElementDraft = {
    ...addDraft,
    imageAssetRef,
  };

  return imageDraft;
}

function emptyElementDraft(): ElementDraft {

  const draft: ElementDraft = {
    name: "",
    band: "top",
    contentKind: "text",
    rectangleColor: "",
    rectangleOpacity: "100",
    rectangleRadius: "0",
    textSource: null,
    fontFamily: DEFAULT_FONT_FAMILY,
    fontSize: "64",
    fontColor: "#112233",
    bold: false,
    italic: false,
    underline: false,
    strikethrough: false,
    fontWeight: "",
    alignment: "left",
    imageAssetRef: "",
  };

  return draft;
}

function draftFromElement(element: ThemeElementReadResponse): ElementDraft {

  const draft: ElementDraft = {
    name: element.name,
    band: element.band,
    contentKind: element.content_kind,
    rectangleColor: element.rectangle_color ?? "",
    rectangleOpacity: String(element.rectangle_opacity),
    rectangleRadius: String(element.rectangle_radius),
    textSource: element.text_source,
    fontFamily: element.font_family ?? "",
    fontSize: element.font_size === null ? "" : String(element.font_size),
    fontColor: element.font_color ?? "",
    bold: element.bold,
    italic: element.italic,
    underline: element.underline,
    strikethrough: element.strikethrough,
    fontWeight: element.font_weight === null ? "" : String(element.font_weight),
    alignment: element.alignment ?? "left",
    imageAssetRef: element.image_asset_ref ?? "",
  };

  return draft;
}

/**
 * Build the create-body element from a staged row. Sort order is omitted
 * so the server appends; callers send rows in band order.
 *
 * @param element - Staged element from the create form
 * @returns The element payload for POST /api/v1/themes
 */
export function themeElementCreateRequestFromElement(
  element: ThemeElementReadResponse,
): ThemeElementCreateRequest {

  const request: ThemeElementCreateRequest = elementRequestFromDraft(
    draftFromElement(element),
  );

  return request;
}

/**
 * Return create payloads in Top, Middle, Bottom order.
 *
 * Each payload omits sort_order so the server appends and keeps this order.
 *
 * @param elements - Staged elements on the create form
 * @returns Element bodies for one theme create
 */
export function themeElementCreateRequestsInBandOrder(
  elements: ThemeElementReadResponse[],
): ThemeElementCreateRequest[] {

  const bandRank: Record<ThemeElementBand, number> = {
    top: 0,
    middle: 1,
    bottom: 2,
  };
  const orderedElements: ThemeElementReadResponse[] = [...elements].sort(
    (left: ThemeElementReadResponse, right: ThemeElementReadResponse): number => {

      if (left.band !== right.band) {
        return bandRank[left.band] - bandRank[right.band];
      }

      return left.sort_order - right.sort_order;
    },
  );
  const requests: ThemeElementCreateRequest[] = orderedElements.map(
    (element: ThemeElementReadResponse): ThemeElementCreateRequest => {

      return themeElementCreateRequestFromElement(element);
    },
  );

  return requests;
}

export interface ThemePreviewElementState {
  elements: ThemeElementCreateRequest[] | null;
  draftError: string | null;
}

/**
 * Build the preview payload for elements that are already on the theme.
 *
 * Card drafts are not included. A bad font size returns the message and
 * no element list, which is the same result the editor effect reports.
 *
 * @param elements - Saved or staged elements
 * @returns Element bodies for one preview, or a client draft error
 */
export function previewElementStateFromElements(
  elements: ThemeElementReadResponse[],
): ThemePreviewElementState {

  try {
    const requests: ThemeElementCreateRequest[] = previewRequestsFromElements(elements, {});
    const previewState: ThemePreviewElementState = {
      elements: requests,
      draftError: null,
    };

    return previewState;
  } catch (caughtError: unknown) {
    const message: string = caughtError instanceof Error
      ? caughtError.message
      : String(caughtError);
    const previewState: ThemePreviewElementState = {
      elements: null,
      draftError: message,
    };

    return previewState;
  }
}

function previewRequestsFromElements(
  elements: ThemeElementReadResponse[],
  cardDrafts: Record<string, ElementDraft>,
): ThemeElementCreateRequest[] {

  const bandOrder: ThemeElementBand[] = ["top", "middle", "bottom"];
  const requests: ThemeElementCreateRequest[] = [];

  bandOrder.forEach((band: ThemeElementBand): void => {
    const members: ThemeElementReadResponse[] = elements.filter(
      (element: ThemeElementReadResponse): boolean => {
        const draft: ElementDraft = cardDrafts[element.id] ?? draftFromElement(element);

        return draft.band === band;
      },
    );
    const stayed: ThemeElementReadResponse[] = members
      .filter((element: ThemeElementReadResponse): boolean => element.band === band)
      .sort(
        (left: ThemeElementReadResponse, right: ThemeElementReadResponse): number => {

          return left.sort_order - right.sort_order;
        },
      );
    const moved: ThemeElementReadResponse[] = members.filter(
      (element: ThemeElementReadResponse): boolean => element.band !== band,
    );
    const orderedMembers: ThemeElementReadResponse[] = [...stayed, ...moved];

    orderedMembers.forEach((element: ThemeElementReadResponse, index: number): void => {
      const draft: ElementDraft = cardDrafts[element.id] ?? draftFromElement(element);
      const request: ThemeElementCreateRequest = elementRequestFromDraft(draft);
      request.sort_order = index;
      requests.push(request);
    });
  });

  return requests;
}

function readElementDraftError(draft: ElementDraft): string | null {

  try {
    elementRequestFromDraft(draft);

    return null;
  } catch (caughtError: unknown) {
    const message: string = caughtError instanceof Error
      ? caughtError.message
      : String(caughtError);

    return message;
  }
}

function firstDraftError(draftErrors: Record<string, string>): string | null {

  const messages: string[] = Object.values(draftErrors);

  if (messages.length === 0) {
    return null;
  }

  const firstMessage: string = messages[0];

  return firstMessage;
}

function elementRequestFromDraft(
  draft: ElementDraft,
): ThemeElementCreateRequest {

  const fontWeight: number | null = parseOptionalFontWeight(draft.fontWeight);
  const elementName: string = requiredElementName(draft.name);
  const request: ThemeElementCreateRequest = {
    name: elementName,
    band: draft.band,
    content_kind: draft.contentKind,
    rectangle_color: normalizeHexColor(draft.rectangleColor),
    rectangle_opacity: parseRectangleOpacity(draft.rectangleOpacity),
    rectangle_radius: parseRectangleRadius(draft.rectangleRadius),
    bold: draft.bold,
    italic: draft.italic,
    underline: draft.underline,
    strikethrough: draft.strikethrough,
    font_weight: fontWeight,
  };

  if (draft.contentKind === "text") {
    request.text_source = draft.textSource;
    request.font_family = draft.fontFamily.trim();
    request.font_size = parseRequiredFontSize(draft.fontSize);
    request.font_color = normalizeHexColor(draft.fontColor);
    request.alignment = draft.alignment;
    request.image_asset_ref = null;

    return request;
  }

  request.text_source = null;
  request.image_asset_ref = draft.imageAssetRef.trim();

  return request;
}

const RECTANGLE_OPACITY_MAX: number = 100;
const RECTANGLE_RADIUS_MAX: number = 10000;

function RectangleStyleFields({
  draft,
  onDraftChange,
}: {
  draft: ElementDraft;
  onDraftChange: (nextDraft: ElementDraft) => void;
}): ReactElement {

  return (
    <div className="theme-subsection">
      <p className="section-label">Rectangle</p>
      <div className="compact-field-row">
        <label>
          Color
          <input
            className="compact-input"
            value={draft.rectangleColor}
            aria-label="Rectangle color"
            title="Blank means a clear rectangle."
            placeholder="#AABBCC"
            spellCheck={false}
            onChange={(changeEvent): void => {
              onDraftChange({ ...draft, rectangleColor: changeEvent.target.value });
            }}
            onBlur={(blurEvent): void => {
              onDraftChange({
                ...draft,
                rectangleColor: normalizeHexColor(blurEvent.currentTarget.value),
              });
            }}
          />
        </label>
        <label>
          Opacity
          <input
            className="compact-input"
            type="number"
            min={0}
            max={RECTANGLE_OPACITY_MAX}
            step={1}
            value={draft.rectangleOpacity}
            aria-label="Rectangle opacity"
            title="0 is clear. 100 is solid."
            onChange={(changeEvent): void => {
              onDraftChange({ ...draft, rectangleOpacity: changeEvent.target.value });
            }}
          />
        </label>
        <label>
          Radius
          <input
            className="compact-input"
            type="number"
            min={0}
            max={RECTANGLE_RADIUS_MAX}
            step={1}
            value={draft.rectangleRadius}
            aria-label="Rectangle radius"
            title="Corner radius in pixels."
            onChange={(changeEvent): void => {
              onDraftChange({ ...draft, rectangleRadius: changeEvent.target.value });
            }}
          />
        </label>
      </div>
    </div>
  );
}

function parseRectangleOpacity(rawValue: string): number {

  const trimmedValue: string = rawValue.trim();

  if (trimmedValue === "") {
    return 100;
  }

  if (!/^\d+$/.test(trimmedValue)) {
    throw new Error("rectangle_opacity must be an integer from 0 through 100.");
  }

  const opacity: number = Number(trimmedValue);

  if (opacity > RECTANGLE_OPACITY_MAX) {
    throw new Error("rectangle_opacity must be an integer from 0 through 100.");
  }

  return opacity;
}

function parseRectangleRadius(rawValue: string): number {

  const trimmedValue: string = rawValue.trim();

  if (trimmedValue === "") {
    return 0;
  }

  if (!/^\d+$/.test(trimmedValue)) {
    throw new Error("rectangle_radius must be an integer from 0 through 10000.");
  }

  const radius: number = Number(trimmedValue);

  if (radius > RECTANGLE_RADIUS_MAX) {
    throw new Error("rectangle_radius must be an integer from 0 through 10000.");
  }

  return radius;
}

function requiredElementName(rawName: string): string {

  const elementName: string = rawName.trim();

  if (elementName === "") {
    throw new Error("Name is required.");
  }

  return elementName;
}

function parseRequiredFontSize(rawValue: string): number {

  const trimmedValue: string = rawValue.trim();

  if (!/^\d+$/.test(trimmedValue)) {
    throw new Error("font_size must be a positive integer.");
  }

  const fontSize: number = Number(trimmedValue);

  if (fontSize < 1) {
    throw new Error("font_size must be a positive integer.");
  }

  return fontSize;
}

function parseOptionalFontWeight(rawValue: string): number | null {

  const trimmedValue: string = rawValue.trim();

  if (trimmedValue === "") {
    return null;
  }

  if (!/^\d+$/.test(trimmedValue)) {
    throw new Error("font_weight must be from 1 through 1000.");
  }

  const fontWeight: number = Number(trimmedValue);

  return fontWeight;
}

function elementsInBand(
  elements: ThemeElementReadResponse[],
  band: ThemeElementBand,
): ThemeElementReadResponse[] {

  const members: ThemeElementReadResponse[] = elements.filter(
    (element: ThemeElementReadResponse): boolean => element.band === band,
  );
  const orderedMembers: ThemeElementReadResponse[] = [...members].sort(
    (left: ThemeElementReadResponse, right: ThemeElementReadResponse): number => {

      return left.sort_order - right.sort_order;
    },
  );

  return orderedMembers;
}

function isThemeElementBand(value: string): value is ThemeElementBand {

  return value === "top" || value === "middle" || value === "bottom";
}

function isContentKind(value: string): value is ThemeElementContentKind {

  return value === "text" || value === "image";
}

function localElementFromRequest(
  themeId: string,
  existingElements: ThemeElementReadResponse[],
  request: ThemeElementCreateRequest,
): ThemeElementReadResponse {

  const bandCount: number = existingElements.filter(
    (element: ThemeElementReadResponse): boolean => element.band === request.band,
  ).length;
  const now: string = new Date().toISOString();
  const createdElement: ThemeElementReadResponse = {
    id: crypto.randomUUID(),
    theme_id: themeId,
    band: request.band,
    sort_order: bandCount,
    content_kind: request.content_kind,
    name: request.name,
    rectangle_color: emptyToNull(request.rectangle_color),
    rectangle_opacity: request.rectangle_opacity ?? 100,
    rectangle_radius: request.rectangle_radius ?? 0,
    text_source: request.content_kind === "text" ? request.text_source ?? null : null,
    font_family: request.content_kind === "text" ? request.font_family ?? null : null,
    font_size: request.content_kind === "text" ? request.font_size ?? null : null,
    font_color: request.content_kind === "text" ? request.font_color ?? null : null,
    bold: request.bold ?? false,
    italic: request.italic ?? false,
    underline: request.underline ?? false,
    strikethrough: request.strikethrough ?? false,
    font_weight: request.font_weight ?? null,
    alignment: request.content_kind === "text" ? request.alignment ?? null : null,
    image_asset_ref: request.content_kind === "image"
      ? request.image_asset_ref ?? null
      : null,
    created_at: now,
    updated_at: now,
  };

  return createdElement;
}

function applyRequestToElement(
  element: ThemeElementReadResponse,
  request: ThemeElementCreateRequest,
): ThemeElementReadResponse {

  const updatedElement: ThemeElementReadResponse = {
    ...element,
    band: request.band,
    content_kind: request.content_kind,
    name: request.name,
    rectangle_color: emptyToNull(request.rectangle_color),
    rectangle_opacity: request.rectangle_opacity ?? 100,
    rectangle_radius: request.rectangle_radius ?? 0,
    text_source: request.content_kind === "text" ? request.text_source ?? null : null,
    font_family: request.content_kind === "text" ? request.font_family ?? null : null,
    font_size: request.content_kind === "text" ? request.font_size ?? null : null,
    font_color: request.content_kind === "text" ? request.font_color ?? null : null,
    bold: request.bold ?? false,
    italic: request.italic ?? false,
    underline: request.underline ?? false,
    strikethrough: request.strikethrough ?? false,
    font_weight: request.font_weight ?? null,
    alignment: request.content_kind === "text" ? request.alignment ?? null : null,
    image_asset_ref: request.content_kind === "image"
      ? request.image_asset_ref ?? null
      : null,
    updated_at: new Date().toISOString(),
  };

  return updatedElement;
}

function placeSavedLocalElement(
  elements: ThemeElementReadResponse[],
  previous: ThemeElementReadResponse,
  updated: ThemeElementReadResponse,
): ThemeElementReadResponse[] {

  if (updated.band === previous.band) {
    const sameBand: ThemeElementReadResponse[] = elements.map(
      (element: ThemeElementReadResponse): ThemeElementReadResponse => {

        if (element.id !== updated.id) {
          return element;
        }

        return { ...updated, sort_order: previous.sort_order };
      },
    );

    return sameBand;
  }

  const withoutMoved: ThemeElementReadResponse[] = elements.filter(
    (element: ThemeElementReadResponse): boolean => element.id !== previous.id,
  );
  const compacted: ThemeElementReadResponse[] = compactBand(withoutMoved, previous.band);
  const destinationLength: number = compacted.filter(
    (element: ThemeElementReadResponse): boolean => element.band === updated.band,
  ).length;
  const movedElement: ThemeElementReadResponse = {
    ...updated,
    sort_order: destinationLength,
  };

  return [...compacted, movedElement];
}

function deleteLocalElement(
  elements: ThemeElementReadResponse[],
  elementId: string,
): ThemeElementReadResponse[] {

  const target: ThemeElementReadResponse | undefined = elements.find(
    (element: ThemeElementReadResponse): boolean => element.id === elementId,
  );

  if (target === undefined) {
    return elements;
  }

  const withoutTarget: ThemeElementReadResponse[] = elements.filter(
    (element: ThemeElementReadResponse): boolean => element.id !== elementId,
  );

  return compactBand(withoutTarget, target.band);
}

function moveLocalElement(
  elements: ThemeElementReadResponse[],
  elementId: string,
  requestedSortOrder: number,
): ThemeElementReadResponse[] {

  const target: ThemeElementReadResponse | undefined = elements.find(
    (element: ThemeElementReadResponse): boolean => element.id === elementId,
  );

  if (target === undefined) {
    return elements;
  }

  const others: ThemeElementReadResponse[] = elements.filter(
    (element: ThemeElementReadResponse): boolean => element.id !== elementId,
  );
  const targetMembers: ThemeElementReadResponse[] = others
    .filter((element: ThemeElementReadResponse): boolean => element.band === target.band)
    .sort(
      (left: ThemeElementReadResponse, right: ThemeElementReadResponse): number => {

        return left.sort_order - right.sort_order;
      },
    );
  const targetIndex: number = requestedSortOrder > targetMembers.length
    ? targetMembers.length
    : requestedSortOrder;
  const placedMembers: ThemeElementReadResponse[] = [...targetMembers];

  placedMembers.splice(targetIndex, 0, target);

  const movedAt: string = new Date().toISOString();
  const compactedMembers: ThemeElementReadResponse[] = placedMembers.map(
    (member: ThemeElementReadResponse, index: number): ThemeElementReadResponse => {

      return {
        ...member,
        sort_order: index,
        updated_at: member.id === elementId ? movedAt : member.updated_at,
      };
    },
  );
  const rest: ThemeElementReadResponse[] = others.filter(
    (element: ThemeElementReadResponse): boolean => element.band !== target.band,
  );

  return [...rest, ...compactedMembers];
}

function compactBand(
  elements: ThemeElementReadResponse[],
  band: ThemeElementBand,
): ThemeElementReadResponse[] {

  const members: ThemeElementReadResponse[] = elements
    .filter((element: ThemeElementReadResponse): boolean => element.band === band)
    .sort(
      (left: ThemeElementReadResponse, right: ThemeElementReadResponse): number => {

        return left.sort_order - right.sort_order;
      },
    );
  const orderById: Map<string, number> = new Map(
    members.map(
      (element: ThemeElementReadResponse, index: number): [string, number] => {

        return [element.id, index];
      },
    ),
  );
  const compacted: ThemeElementReadResponse[] = elements.map(
    (element: ThemeElementReadResponse): ThemeElementReadResponse => {

      const nextOrder: number | undefined = orderById.get(element.id);

      if (nextOrder === undefined) {
        return element;
      }

      return { ...element, sort_order: nextOrder };
    },
  );

  return compacted;
}

function emptyToNull(value: string | null | undefined): string | null {

  if (value === undefined || value === null || value.trim() === "") {
    return null;
  }

  return value;
}

function ChevronIcon({ expanded }: { expanded: boolean }): ReactElement {

  const chevronClass: string = expanded ? "chevron is-open" : "chevron";

  return (
    <svg
      className={chevronClass}
      viewBox="0 0 16 16"
      width="16"
      height="16"
      aria-hidden="true"
    >
      <path
        d="M6 3.5 L11 8 L6 12.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function AlignIcon({ alignment }: { alignment: ThemeElementAlignment }): ReactElement {

  const middleLine: string = alignment === "left"
    ? "M3 10h8"
    : alignment === "center"
      ? "M5 10h10"
      : "M8 10h9";
  const bottomLine: string = alignment === "left"
    ? "M3 14h11"
    : alignment === "center"
      ? "M4 14h12"
      : "M6 14h11";

  return (
    <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
      <path
        d={`M3 6h14 ${middleLine} ${bottomLine}`}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}
