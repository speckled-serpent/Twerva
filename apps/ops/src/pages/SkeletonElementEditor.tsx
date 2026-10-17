import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactElement,
} from "react";

import {
  createSkeletonElement,
  deleteSkeletonElement,
  fetchSkeletonById,
  patchSkeletonElement,
} from "../api/client";
import type {
  SkeletonElementAlignment,
  SkeletonElementBand,
  SkeletonElementContentKind,
  SkeletonElementCreateRequest,
  SkeletonElementPatchRequest,
  SkeletonElementReadResponse,
  SkeletonElementTextSource,
  SkeletonReadResponse,
} from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { useCanWriteOps } from "../session/OpsSessionContext";
import {
  SKELETON_AUTOSAVE_DELAY_MS,
  combineAutosaveStates,
  formatSkeletonAutosaveError,
  type SkeletonAutosaveActions,
  type SkeletonAutosaveState,
} from "./skeletonAutosave";
import { useSkeletonAutosave } from "./useSkeletonAutosave";
import { SkeletonAssetAlbumField, loadSkeletonPickerAlbums } from "./SkeletonAssetAlbumField";
import { SkeletonFontFamilyField } from "./SkeletonFontFamilyField";
import { normalizeHexColor } from "./skeletonColors";
import { pickDefaultAlbumImage, type SkeletonImageAlbum } from "./skeletonAssets";
import { DEFAULT_FONT_FAMILY } from "./skeletonFonts";

export interface SkeletonElementEditorProps {
  skeleton: SkeletonReadResponse;
  onSkeletonUpdated: (updatedSkeleton: SkeletonReadResponse) => void;
  onLocalElementsChange?: (nextElements: SkeletonElementReadResponse[]) => void;
  onPreviewElementsChange?: (
    elements: SkeletonPreviewDraftElement[] | null,
    draftError: string | null,
  ) => void;
  onElementPatched?: (element: SkeletonElementReadResponse) => void;
  onValidationMessageChange?: (message: string | null) => void;
  onAutosaveStateChange?: (state: SkeletonAutosaveState) => void;
  autosaveActionsRef?: { current: SkeletonAutosaveActions | null };
}

interface BandOption {
  value: SkeletonElementBand;
  label: string;
}

interface ElementDraft {
  name: string;
  band: SkeletonElementBand;
  contentKind: SkeletonElementContentKind;
  rectangleColor: string;
  rectangleOpacity: string;
  rectangleRadius: string;
  textSource: SkeletonElementTextSource | null;
  fontFamily: string;
  fontSize: string;
  fontColor: string;
  bold: boolean;
  italic: boolean;
  underline: boolean;
  strikethrough: boolean;
  fontWeight: string;
  alignment: SkeletonElementAlignment;
  imageAssetRef: string;
}

const BAND_OPTIONS: BandOption[] = [
  { value: "top", label: "Top" },
  { value: "middle", label: "Middle" },
  { value: "bottom", label: "Bottom" },
];

/**
 * Add, edit, delete, reorder, and move skeleton elements. No placement fields.
 *
 * When `onLocalElementsChange` is set, edits stay in memory for Create Skeleton.
 *
 * @param props - The open skeleton and a callback after each saved change
 * @returns The element editor under the frame form
 */
export function SkeletonElementEditor({
  skeleton,
  onSkeletonUpdated,
  onLocalElementsChange,
  onPreviewElementsChange,
  onElementPatched,
  onValidationMessageChange,
  onAutosaveStateChange,
  autosaveActionsRef,
}: SkeletonElementEditorProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [addDraft, setAddDraft] = useState<ElementDraft>(emptyElementDraft());
  const [isAddOpen, setIsAddOpen] = useState<boolean>(false);
  const [expandedElementIds, setExpandedElementIds] = useState<Record<string, boolean>>({});
  const [cardDrafts, setCardDrafts] = useState<Record<string, ElementDraft>>({});
  const [draftErrors, setDraftErrors] = useState<Record<string, string>>({});
  const [cardAutosaveStates, setCardAutosaveStates] = useState<
    Record<string, SkeletonAutosaveState>
  >({});
  const [actionError, setActionError] = useState<unknown>(null);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const previewCallbackRef = useRef(onPreviewElementsChange);
  const lastPreviewKeyRef = useRef<string | null>(null);
  const skeletonRef = useRef(skeleton);
  const onSkeletonUpdatedRef = useRef(onSkeletonUpdated);
  const onLocalElementsChangeRef = useRef(onLocalElementsChange);
  const onElementPatchedRef = useRef(onElementPatched);
  const onValidationMessageChangeRef = useRef(onValidationMessageChange);
  const onAutosaveStateChangeRef = useRef(onAutosaveStateChange);
  const reloadSerialRef = useRef(0);
  const cardActionsRef = useRef<Map<string, SkeletonAutosaveActions>>(new Map());
  previewCallbackRef.current = onPreviewElementsChange;
  skeletonRef.current = skeleton;
  onSkeletonUpdatedRef.current = onSkeletonUpdated;
  onLocalElementsChangeRef.current = onLocalElementsChange;
  onElementPatchedRef.current = onElementPatched;
  onValidationMessageChangeRef.current = onValidationMessageChange;
  onAutosaveStateChangeRef.current = onAutosaveStateChange;
  const fieldsDisabled: boolean = !canWrite || busyKey !== null;
  const isLocal: boolean = onLocalElementsChange !== undefined;
  const validationMessage: string | null = firstDraftError(draftErrors);
  const elementAutosaveState: SkeletonAutosaveState = combineAutosaveStates(
    Object.values(cardAutosaveStates),
  );
  const elementAutosaveKey: string = [
    elementAutosaveState.phase,
    elementAutosaveState.message,
    elementAutosaveState.canRetry ? "retry" : "noretry",
  ].join("|");

  const reloadSkeleton = async (): Promise<SkeletonReadResponse | null> => {

    const serial: number = reloadSerialRef.current + 1;
    reloadSerialRef.current = serial;
    const reloadedSkeleton: SkeletonReadResponse = await fetchSkeletonById(skeletonRef.current.id);

    if (serial !== reloadSerialRef.current) {
      return null;
    }

    onSkeletonUpdatedRef.current(reloadedSkeleton);

    return reloadedSkeleton;
  };

  const publishLocalElements = (nextElements: SkeletonElementReadResponse[]): void => {

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
    autosaveState: SkeletonAutosaveState | null,
  ): void => {

    setCardAutosaveStates((
      currentStates: Record<string, SkeletonAutosaveState>,
    ): Record<string, SkeletonAutosaveState> => {

      if (autosaveState === null) {

        if (!(elementId in currentStates)) {
          return currentStates;
        }

        const nextStates: Record<string, SkeletonAutosaveState> = { ...currentStates };

        delete nextStates[elementId];

        return nextStates;
      }

      const previousState: SkeletonAutosaveState | undefined = currentStates[elementId];

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
    actions: SkeletonAutosaveActions | null,
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
      const createRequest: SkeletonElementCreateRequest = elementRequestFromDraft(draftToAdd);

      if (isLocal) {
        const createdElement: SkeletonElementReadResponse = localElementFromRequest(
          skeleton.id,
          skeleton.elements,
          createRequest,
        );

        publishLocalElements([...skeleton.elements, createdElement]);
        setAddDraft(emptyElementDraft());
        setIsAddOpen(false);
        setStatusMessage("Element added. It is stored when you pause.");
      } else {
        await createSkeletonElement(skeleton.id, createRequest);
        await reloadSkeleton();
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

    const currentElements: SkeletonElementReadResponse[] = skeletonRef.current.elements;
    const currentElement: SkeletonElementReadResponse | undefined = currentElements.find(
      (element: SkeletonElementReadResponse): boolean => element.id === elementId,
    );

    if (currentElement === undefined) {
      return;
    }

    try {
      const request: SkeletonElementCreateRequest = elementRequestFromDraft(draft);
      const currentRequest: SkeletonElementCreateRequest = skeletonElementCreateRequestFromElement(
        currentElement,
      );

      if (JSON.stringify(request) === JSON.stringify(currentRequest)) {
        return;
      }

      const updatedElement: SkeletonElementReadResponse = applyRequestToElement(
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

    publishLocalElements(deleteLocalElement(skeleton.elements, elementId));
  };

  const handleLocalMove = (elementId: string, nextSortOrder: number): void => {

    publishLocalElements(moveLocalElement(skeleton.elements, elementId, nextSortOrder));
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
        const actions: SkeletonAutosaveActions[] = [...cardActionsRef.current.values()];

        return Promise.all(actions.map(
          (action: SkeletonAutosaveActions): Promise<void> => action.flush(),
        )).then((): void => {
          return;
        });
      },
      retry: (): Promise<void> => {
        const actions: SkeletonAutosaveActions[] = [...cardActionsRef.current.values()];

        return Promise.all(actions.map(
          (action: SkeletonAutosaveActions): Promise<void> => action.retry(),
        )).then((): void => {
          return;
        });
      },
      abandon: (): Promise<void> => {
        const actions: SkeletonAutosaveActions[] = [...cardActionsRef.current.values()];

        return Promise.all(actions.map(
          (action: SkeletonAutosaveActions): Promise<void> => action.abandon(),
        )).then((): void => {
          return;
        });
      },
      isDirty: (): boolean => {
        const actions: SkeletonAutosaveActions[] = [...cardActionsRef.current.values()];

        return actions.some((action: SkeletonAutosaveActions): boolean => action.isDirty());
      },
    };
  }

  useEffect((): void => {
    const previewCallback = previewCallbackRef.current;

    if (previewCallback === undefined) {
      return;
    }

    try {
      const requests: SkeletonPreviewDraftElement[] = previewRequestsFromElements(
        skeleton.elements,
        cardDrafts,
      );
      const previewKey: string = `${skeleton.id}:${JSON.stringify(requests)}`;

      if (previewKey === lastPreviewKeyRef.current) {
        return;
      }

      lastPreviewKeyRef.current = previewKey;
      previewCallback(requests, null);
    } catch (caughtError: unknown) {
      const message: string = caughtError instanceof Error
        ? caughtError.message
        : String(caughtError);
      const previewKey: string = `${skeleton.id}:error:${message}`;

      if (previewKey === lastPreviewKeyRef.current) {
        return;
      }

      lastPreviewKeyRef.current = previewKey;
      previewCallback(null, message);
    }
  }, [skeleton.id, skeleton.elements, cardDrafts]);

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
            className="confirm-dialog skeleton-add-dialog"
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
        const bandElements: SkeletonElementReadResponse[] = elementsInBand(
          skeleton.elements,
          bandOption.value,
        );

        if (bandElements.length === 0) {
          return null;
        }

        return (
          <div className="skeleton-band" key={bandOption.value}>
            <h3>{bandOption.label}</h3>
            {bandElements.map(
              (element: SkeletonElementReadResponse, elementIndex: number): ReactElement => (
                <SkeletonElementCard
                  key={element.id}
                  skeletonId={skeleton.id}
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
                      await reloadSkeleton();
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
                  onElementPatched={(patchedElement: SkeletonElementReadResponse): void => {
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

interface SkeletonElementCardProps {
  skeletonId: string;
  element: SkeletonElementReadResponse;
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
  onAutosaveState: (elementId: string, state: SkeletonAutosaveState | null) => void;
  onBindAutosave: (elementId: string, actions: SkeletonAutosaveActions | null) => void;
  onElementPatched: (element: SkeletonElementReadResponse) => void;
}

function SkeletonElementCard({
  skeletonId,
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
}: SkeletonElementCardProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [draft, setDraft] = useState<ElementDraft>(draftFromElement(element));
  const isLocal: boolean = onLocalSave !== undefined;
  const skeletonIdRef = useRef(skeletonId);
  const elementRef = useRef(element);
  const onReloadRef = useRef(onReload);
  const onElementPatchedRef = useRef(onElementPatched);
  const notedElementIdRef = useRef<string | null>(null);
  skeletonIdRef.current = skeletonId;
  elementRef.current = element;
  onReloadRef.current = onReload;
  onElementPatchedRef.current = onElementPatched;
  const draftError: string | null = readElementDraftError(draft);
  const autosave = useSkeletonAutosave<ElementDraft>({
    delayMs: SKELETON_AUTOSAVE_DELAY_MS,
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
      const patchRequest: SkeletonElementPatchRequest = elementRequestFromDraft(nextDraft);
      const patchedElement: SkeletonElementReadResponse = await patchSkeletonElement(
        skeletonIdRef.current,
        elementRef.current.id,
        patchRequest,
      );

      if (nextDraft.band !== elementRef.current.band) {
        await onReloadRef.current("Element moved.");

        return;
      }

      onElementPatchedRef.current(patchedElement);
    },
    formatError: formatSkeletonAutosaveError,
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

      await deleteSkeletonElement(skeletonId, element.id);
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

      await patchSkeletonElement(skeletonId, element.id, { sort_order: nextSortOrder });
      await onReload("Element moved.");
    } catch (caughtError: unknown) {
      onError(caughtError);
    } finally {
      onBusy(false);
    }
  };

  const elementTitle: string = draft.name.trim() === "" ? "Untitled element" : draft.name;

  return (
    <article className="card skeleton-element-card">
      <button
        type="button"
        className="skeleton-element-summary"
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
      <p className="field-hint">This name labels the field when you edit a slide.</p>
      <div className="paired-fields">
        <label>
          Band
          <select
            aria-label="Band"
            value={draft.band}
            onChange={(changeEvent): void => {
              const nextBand: string = changeEvent.target.value;

              if (!isSkeletonElementBand(nextBand)) {
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
        <SkeletonAssetAlbumField
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
    <div className="skeleton-subsection">
      <p className="section-label">Text</p>
      <div className="text-toolbar">
        <SkeletonFontFamilyField
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
  alignment: SkeletonElementAlignment;
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

  const albums: SkeletonImageAlbum[] = await loadSkeletonPickerAlbums();
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

function draftFromElement(element: SkeletonElementReadResponse): ElementDraft {

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
 * @returns The element payload for POST /api/v1/skeletons
 */
export function skeletonElementCreateRequestFromElement(
  element: SkeletonElementReadResponse,
): SkeletonElementCreateRequest {

  const request: SkeletonElementCreateRequest = elementRequestFromDraft(
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
 * @returns Element bodies for one skeleton create
 */
export function skeletonElementCreateRequestsInBandOrder(
  elements: SkeletonElementReadResponse[],
): SkeletonElementCreateRequest[] {

  const bandRank: Record<SkeletonElementBand, number> = {
    top: 0,
    middle: 1,
    bottom: 2,
  };
  const orderedElements: SkeletonElementReadResponse[] = [...elements].sort(
    (left: SkeletonElementReadResponse, right: SkeletonElementReadResponse): number => {

      if (left.band !== right.band) {
        return bandRank[left.band] - bandRank[right.band];
      }

      return left.sort_order - right.sort_order;
    },
  );
  const requests: SkeletonElementCreateRequest[] = orderedElements.map(
    (element: SkeletonElementReadResponse): SkeletonElementCreateRequest => {

      return skeletonElementCreateRequestFromElement(element);
    },
  );

  return requests;
}

export interface SkeletonPreviewDraftElement extends SkeletonElementCreateRequest {
  element_id: string;
}

export interface SkeletonPreviewElementState {
  elements: SkeletonPreviewDraftElement[] | null;
  draftError: string | null;
}

/**
 * Build the preview payload for elements that are already on the skeleton.
 *
 * Card drafts are not included. A bad font size returns the message and
 * no element list, which is the same result the editor effect reports.
 *
 * @param elements - Saved or staged elements
 * @returns Element bodies for one preview, or a client draft error
 */
export function previewElementStateFromElements(
  elements: SkeletonElementReadResponse[],
): SkeletonPreviewElementState {

  try {
    const requests: SkeletonPreviewDraftElement[] = previewRequestsFromElements(elements, {});
    const previewState: SkeletonPreviewElementState = {
      elements: requests,
      draftError: null,
    };

    return previewState;
  } catch (caughtError: unknown) {
    const message: string = caughtError instanceof Error
      ? caughtError.message
      : String(caughtError);
    const previewState: SkeletonPreviewElementState = {
      elements: null,
      draftError: message,
    };

    return previewState;
  }
}

function previewRequestsFromElements(
  elements: SkeletonElementReadResponse[],
  cardDrafts: Record<string, ElementDraft>,
): SkeletonPreviewDraftElement[] {

  const bandOrder: SkeletonElementBand[] = ["top", "middle", "bottom"];
  const requests: SkeletonPreviewDraftElement[] = [];

  bandOrder.forEach((band: SkeletonElementBand): void => {
    const members: SkeletonElementReadResponse[] = elements.filter(
      (element: SkeletonElementReadResponse): boolean => {
        const draft: ElementDraft = cardDrafts[element.id] ?? draftFromElement(element);

        return draft.band === band;
      },
    );
    const stayed: SkeletonElementReadResponse[] = members
      .filter((element: SkeletonElementReadResponse): boolean => element.band === band)
      .sort(
        (left: SkeletonElementReadResponse, right: SkeletonElementReadResponse): number => {

          return left.sort_order - right.sort_order;
        },
      );
    const moved: SkeletonElementReadResponse[] = members.filter(
      (element: SkeletonElementReadResponse): boolean => element.band !== band,
    );
    const orderedMembers: SkeletonElementReadResponse[] = [...stayed, ...moved];

    orderedMembers.forEach((element: SkeletonElementReadResponse, index: number): void => {
      const draft: ElementDraft = cardDrafts[element.id] ?? draftFromElement(element);
      const draftedRequest: SkeletonElementCreateRequest = elementRequestFromDraft(draft);
      const request: SkeletonPreviewDraftElement = {
        ...draftedRequest,
        element_id: element.id,
        sort_order: index,
      };
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
): SkeletonElementCreateRequest {

  const fontWeight: number | null = parseOptionalFontWeight(draft.fontWeight);
  const elementName: string = requiredElementName(draft.name);
  const request: SkeletonElementCreateRequest = {
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
    <div className="skeleton-subsection">
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
  elements: SkeletonElementReadResponse[],
  band: SkeletonElementBand,
): SkeletonElementReadResponse[] {

  const members: SkeletonElementReadResponse[] = elements.filter(
    (element: SkeletonElementReadResponse): boolean => element.band === band,
  );
  const orderedMembers: SkeletonElementReadResponse[] = [...members].sort(
    (left: SkeletonElementReadResponse, right: SkeletonElementReadResponse): number => {

      return left.sort_order - right.sort_order;
    },
  );

  return orderedMembers;
}

function isSkeletonElementBand(value: string): value is SkeletonElementBand {

  return value === "top" || value === "middle" || value === "bottom";
}

function isContentKind(value: string): value is SkeletonElementContentKind {

  return value === "text" || value === "image";
}

function localElementFromRequest(
  skeletonId: string,
  existingElements: SkeletonElementReadResponse[],
  request: SkeletonElementCreateRequest,
): SkeletonElementReadResponse {

  const bandCount: number = existingElements.filter(
    (element: SkeletonElementReadResponse): boolean => element.band === request.band,
  ).length;
  const now: string = new Date().toISOString();
  const createdElement: SkeletonElementReadResponse = {
    id: crypto.randomUUID(),
    skeleton_id: skeletonId,
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
  element: SkeletonElementReadResponse,
  request: SkeletonElementCreateRequest,
): SkeletonElementReadResponse {

  const updatedElement: SkeletonElementReadResponse = {
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
  elements: SkeletonElementReadResponse[],
  previous: SkeletonElementReadResponse,
  updated: SkeletonElementReadResponse,
): SkeletonElementReadResponse[] {

  if (updated.band === previous.band) {
    const sameBand: SkeletonElementReadResponse[] = elements.map(
      (element: SkeletonElementReadResponse): SkeletonElementReadResponse => {

        if (element.id !== updated.id) {
          return element;
        }

        return { ...updated, sort_order: previous.sort_order };
      },
    );

    return sameBand;
  }

  const withoutMoved: SkeletonElementReadResponse[] = elements.filter(
    (element: SkeletonElementReadResponse): boolean => element.id !== previous.id,
  );
  const compacted: SkeletonElementReadResponse[] = compactBand(withoutMoved, previous.band);
  const destinationLength: number = compacted.filter(
    (element: SkeletonElementReadResponse): boolean => element.band === updated.band,
  ).length;
  const movedElement: SkeletonElementReadResponse = {
    ...updated,
    sort_order: destinationLength,
  };

  return [...compacted, movedElement];
}

function deleteLocalElement(
  elements: SkeletonElementReadResponse[],
  elementId: string,
): SkeletonElementReadResponse[] {

  const target: SkeletonElementReadResponse | undefined = elements.find(
    (element: SkeletonElementReadResponse): boolean => element.id === elementId,
  );

  if (target === undefined) {
    return elements;
  }

  const withoutTarget: SkeletonElementReadResponse[] = elements.filter(
    (element: SkeletonElementReadResponse): boolean => element.id !== elementId,
  );

  return compactBand(withoutTarget, target.band);
}

function moveLocalElement(
  elements: SkeletonElementReadResponse[],
  elementId: string,
  requestedSortOrder: number,
): SkeletonElementReadResponse[] {

  const target: SkeletonElementReadResponse | undefined = elements.find(
    (element: SkeletonElementReadResponse): boolean => element.id === elementId,
  );

  if (target === undefined) {
    return elements;
  }

  const others: SkeletonElementReadResponse[] = elements.filter(
    (element: SkeletonElementReadResponse): boolean => element.id !== elementId,
  );
  const targetMembers: SkeletonElementReadResponse[] = others
    .filter((element: SkeletonElementReadResponse): boolean => element.band === target.band)
    .sort(
      (left: SkeletonElementReadResponse, right: SkeletonElementReadResponse): number => {

        return left.sort_order - right.sort_order;
      },
    );
  const targetIndex: number = requestedSortOrder > targetMembers.length
    ? targetMembers.length
    : requestedSortOrder;
  const placedMembers: SkeletonElementReadResponse[] = [...targetMembers];

  placedMembers.splice(targetIndex, 0, target);

  const movedAt: string = new Date().toISOString();
  const compactedMembers: SkeletonElementReadResponse[] = placedMembers.map(
    (member: SkeletonElementReadResponse, index: number): SkeletonElementReadResponse => {

      return {
        ...member,
        sort_order: index,
        updated_at: member.id === elementId ? movedAt : member.updated_at,
      };
    },
  );
  const rest: SkeletonElementReadResponse[] = others.filter(
    (element: SkeletonElementReadResponse): boolean => element.band !== target.band,
  );

  return [...rest, ...compactedMembers];
}

function compactBand(
  elements: SkeletonElementReadResponse[],
  band: SkeletonElementBand,
): SkeletonElementReadResponse[] {

  const members: SkeletonElementReadResponse[] = elements
    .filter((element: SkeletonElementReadResponse): boolean => element.band === band)
    .sort(
      (left: SkeletonElementReadResponse, right: SkeletonElementReadResponse): number => {

        return left.sort_order - right.sort_order;
      },
    );
  const orderById: Map<string, number> = new Map(
    members.map(
      (element: SkeletonElementReadResponse, index: number): [string, number] => {

        return [element.id, index];
      },
    ),
  );
  const compacted: SkeletonElementReadResponse[] = elements.map(
    (element: SkeletonElementReadResponse): SkeletonElementReadResponse => {

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

function AlignIcon({ alignment }: { alignment: SkeletonElementAlignment }): ReactElement {

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
