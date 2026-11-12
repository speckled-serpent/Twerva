import { useEffect, useRef, useState, type ReactElement } from "react";

import {
  createCarouselInstruction,
  deleteCarouselInstruction,
  patchCarouselInstruction,
  replaceCarouselInstructions,
} from "../api/client";
import type {
  CarouselInstructionReadResponse,
  CarouselReadResponse,
} from "../api/types";
import { SkeletonAutosaveStatus } from "./SkeletonAutosaveStatus";
import {
  INSTRUCTION_ADD_BODY,
  INSTRUCTIONS_GENERATE_HINT,
  instructionBodyForSave,
  instructionDocumentIds,
  instructionDocumentLabel,
  instructionDraftFingerprint,
  instructionDraftFromDocument,
  instructionDraftReadiness,
  instructionsAfterGenerateClick,
  instructionsGenerateAccessibleName,
  instructionsGenerateEnabled,
  moveInstructionDocuments,
  type InstructionDraft,
} from "./carouselInstructions";
import { renderInstructionMarkdown } from "./instructionMarkdown";
import {
  INSTRUCTION_SAMPLE_TEMPLATE,
  orderedInstructionDocuments,
} from "./instructionTemplate";
import {
  SKELETON_AUTOSAVE_DELAY_MS,
  formatSkeletonAutosaveError,
  leaveAfterAutosave,
} from "./skeletonAutosave";
import { useSkeletonAutosave } from "./useSkeletonAutosave";

export interface InstructionEditorActions {
  flush: () => Promise<void>;
  isDirty: () => boolean;
  abandon: () => Promise<void>;
}

export interface CarouselInstructionsStepProps {
  carousel: CarouselReadResponse;
  canWrite: boolean;
  onCarouselSaved: (savedCarousel: CarouselReadResponse) => void;
  onActions?: (actions: InstructionEditorActions | null) => void;
}

/**
 * Step 1: edit the selected instruction document, and add, remove, or reorder.
 *
 * The textarea starts empty. The sample is only the placeholder. The
 * first typed text POSTs a document. A later edit PATCHes that row.
 * Add stores an empty document and selects it. Remove and switching
 * flush a pending edit first. A reader can look and cannot change the list.
 *
 * @param props - The open carousel and the write callback
 * @returns The Instructions step
 */
export function CarouselInstructionsStep({
  carousel,
  canWrite,
  onCarouselSaved,
  onActions,
}: CarouselInstructionsStepProps): ReactElement {

  const documents: CarouselInstructionReadResponse[] = orderedInstructionDocuments(
    carousel.instructions,
  );
  const [trackedCarouselId, setTrackedCarouselId] = useState<string>(carousel.id);
  const [draft, setDraft] = useState<InstructionDraft>(
    instructionDraftFromDocument(documents[0] ?? null),
  );
  const [isWorking, setIsWorking] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const carouselRef: { current: CarouselReadResponse } = useRef(carousel);
  const onCarouselSavedRef: { current: (savedCarousel: CarouselReadResponse) => void } =
    useRef(onCarouselSaved);
  const onActionsRef: { current: ((actions: InstructionEditorActions | null) => void) | undefined } =
    useRef(onActions);
  carouselRef.current = carousel;
  onCarouselSavedRef.current = onCarouselSaved;
  onActionsRef.current = onActions;

  if (carousel.id !== trackedCarouselId) {
    const loadedDraft: InstructionDraft = instructionDraftFromDocument(
      orderedInstructionDocuments(carousel.instructions)[0] ?? null,
    );
    setTrackedCarouselId(carousel.id);
    setDraft(loadedDraft);
    setActionError(null);
  }

  const autosave = useSkeletonAutosave<InstructionDraft>({
    delayMs: SKELETON_AUTOSAVE_DELAY_MS,
    readiness: instructionDraftReadiness,
    fingerprint: instructionDraftFingerprint,
    save: async (value: InstructionDraft): Promise<void> => {
      const currentCarousel: CarouselReadResponse = carouselRef.current;
      const savedCarousel: CarouselReadResponse = value.instructionId === null
        ? await createCarouselInstruction(
          currentCarousel.id,
          instructionBodyForSave(value),
        )
        : await patchCarouselInstruction(
          currentCarousel.id,
          value.instructionId,
          instructionBodyForSave(value),
        );
      const nextId: string | null = value.instructionId
        ?? createdInstructionId(savedCarousel);
      setDraft({
        instructionId: nextId,
        body: value.body,
      });
      onCarouselSavedRef.current(savedCarousel);
    },
    formatError: formatSkeletonAutosaveError,
  });

  useEffect((): void => {
    autosave.noteSaved(draft);
  }, [autosave.noteSaved, trackedCarouselId]);

  useEffect((): void => {
    if (!canWrite) {
      return;
    }

    autosave.schedule(draft);
  }, [autosave.schedule, canWrite, draft]);

  useEffect((): (() => void) => {
    onActionsRef.current?.({
      flush: autosave.flush,
      isDirty: autosave.isDirty,
      abandon: autosave.abandon,
    });

    return (): void => {
      onActionsRef.current?.(null);
    };
  }, [autosave.flush, autosave.isDirty, autosave.abandon]);

  const applyDraft = (nextDraft: InstructionDraft): void => {
    setDraft(nextDraft);
    autosave.noteSaved(nextDraft);
  };

  const selectDocument = (documentId: string): void => {

    if (documentId === draft.instructionId) {
      return;
    }

    void leaveAfterAutosave(
      autosave.flush,
      autosave.isDirty,
      (): void => {
        const currentDocuments: CarouselInstructionReadResponse[] =
          orderedInstructionDocuments(carouselRef.current.instructions);
        const nextDocument: CarouselInstructionReadResponse | null =
          currentDocuments.find(
            (document: CarouselInstructionReadResponse): boolean => document.id === documentId,
          ) ?? null;
        applyDraft(instructionDraftFromDocument(nextDocument));
      },
    );
  };

  const handleAdd = (): void => {

    if (!canWrite || isWorking) {
      return;
    }

    void leaveAfterAutosave(
      autosave.flush,
      autosave.isDirty,
      (): void => {
        void addEmptyDocument();
      },
    );
  };

  const addEmptyDocument = async (): Promise<void> => {

    setIsWorking(true);
    setActionError(null);

    try {
      const beforeIds: string[] = instructionDocumentIds(
        orderedInstructionDocuments(carouselRef.current.instructions),
      );
      const savedCarousel: CarouselReadResponse = await createCarouselInstruction(
        carouselRef.current.id,
        INSTRUCTION_ADD_BODY,
      );
      const created: CarouselInstructionReadResponse | null = findAddedDocument(
        beforeIds,
        savedCarousel.instructions,
      );
      applyDraft(instructionDraftFromDocument(created));
      onCarouselSavedRef.current(savedCarousel);
    } catch (caughtError: unknown) {
      setActionError(formatSkeletonAutosaveError(caughtError));
    } finally {
      setIsWorking(false);
    }
  };

  const handleRemove = (documentId: string): void => {

    if (!canWrite || isWorking) {
      return;
    }

    const removeDocument = (): void => {
      void removeStoredDocument(documentId);
    };

    if (documentId !== draft.instructionId) {
      removeDocument();

      return;
    }

    void leaveAfterAutosave(autosave.flush, autosave.isDirty, removeDocument);
  };

  const removeStoredDocument = async (documentId: string): Promise<void> => {

    const currentDocuments: CarouselInstructionReadResponse[] = orderedInstructionDocuments(
      carouselRef.current.instructions,
    );
    const removedIndex: number = currentDocuments.findIndex(
      (document: CarouselInstructionReadResponse): boolean => document.id === documentId,
    );
    setIsWorking(true);
    setActionError(null);

    try {
      const savedCarousel: CarouselReadResponse = await deleteCarouselInstruction(
        carouselRef.current.id,
        documentId,
      );
      const remaining: CarouselInstructionReadResponse[] = orderedInstructionDocuments(
        savedCarousel.instructions,
      );

      if (documentId === draft.instructionId) {
        const nextDocument: CarouselInstructionReadResponse | null = remaining.length === 0
          ? null
          : remaining[Math.min(removedIndex, remaining.length - 1)] ?? null;
        applyDraft(instructionDraftFromDocument(nextDocument));
      }

      onCarouselSavedRef.current(savedCarousel);
    } catch (caughtError: unknown) {
      setActionError(formatSkeletonAutosaveError(caughtError));
    } finally {
      setIsWorking(false);
    }
  };

  const handleMove = (documentIndex: number, direction: -1 | 1): void => {

    if (!canWrite || isWorking) {
      return;
    }

    const movedDocuments: CarouselInstructionReadResponse[] | null = moveInstructionDocuments(
      documents,
      documentIndex,
      direction,
    );

    if (movedDocuments === null) {
      return;
    }

    void storeMovedDocuments(movedDocuments);
  };

  const storeMovedDocuments = async (
    movedDocuments: CarouselInstructionReadResponse[],
  ): Promise<void> => {

    setIsWorking(true);
    setActionError(null);

    try {
      const savedCarousel: CarouselReadResponse = await replaceCarouselInstructions(
        carousel.id,
        instructionDocumentIds(movedDocuments),
      );
      onCarouselSavedRef.current(savedCarousel);
    } catch (caughtError: unknown) {
      setActionError(formatSkeletonAutosaveError(caughtError));
    } finally {
      setIsWorking(false);
    }
  };

  const previewIsSample: boolean = draft.body === "";
  const previewSource: string = previewIsSample
    ? INSTRUCTION_SAMPLE_TEMPLATE
    : draft.body;
  const generateEnabled: boolean = instructionsGenerateEnabled(
    documents,
    draft,
    canWrite,
    INSTRUCTION_SAMPLE_TEMPLATE,
  );

  return (
    <section
      id="carousel-instructions"
      className="stack-form"
      aria-label="Instructions"
    >
      {documents.length === 0 ? null : (
        <ol className="instruction-documents" aria-label="Instruction documents">
          {documents.map((
            document: CarouselInstructionReadResponse,
            documentIndex: number,
          ): ReactElement => {
            const isSelected: boolean = document.id === draft.instructionId;
            const isFirst: boolean = documentIndex === 0;
            const isLast: boolean = documentIndex === documents.length - 1;

            return (
              <li
                key={document.id}
                className={isSelected
                  ? "instruction-document is-selected"
                  : "instruction-document"}
              >
                <button
                  type="button"
                  className="instruction-document-label"
                  aria-pressed={isSelected}
                  onClick={(): void => {
                    selectDocument(document.id);
                  }}
                >
                  {instructionDocumentLabel(document.position)}
                </button>
                {canWrite ? (
                  <div className="button-row">
                    <button
                      type="button"
                      aria-label={`Move ${instructionDocumentLabel(document.position)} up`}
                      disabled={isWorking || isFirst}
                      onClick={(): void => {
                        handleMove(documentIndex, -1);
                      }}
                    >
                      Move up
                    </button>
                    <button
                      type="button"
                      aria-label={`Move ${instructionDocumentLabel(document.position)} down`}
                      disabled={isWorking || isLast}
                      onClick={(): void => {
                        handleMove(documentIndex, 1);
                      }}
                    >
                      Move down
                    </button>
                    <button
                      type="button"
                      aria-label={`Remove ${instructionDocumentLabel(document.position)}`}
                      disabled={isWorking}
                      onClick={(): void => {
                        handleRemove(document.id);
                      }}
                    >
                      Remove
                    </button>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ol>
      )}
      {canWrite ? (
        <div className="button-row">
          <button
            id="add-instruction"
            type="button"
            disabled={isWorking}
            onClick={handleAdd}
          >
            Add
          </button>
        </div>
      ) : null}
      {actionError === null ? null : (
        <p className="field-hint" role="alert">{actionError}</p>
      )}
      <label>
        Instructions
        <textarea
          id="instruction-body"
          className="instruction-body"
          value={draft.body}
          placeholder={INSTRUCTION_SAMPLE_TEMPLATE}
          disabled={!canWrite}
          onChange={(changeEvent): void => {
            setDraft({
              instructionId: draft.instructionId,
              body: changeEvent.target.value,
            });
          }}
        />
      </label>
      {canWrite ? (
        <SkeletonAutosaveStatus
          state={autosave.state}
          onRetry={(): void => {
            void autosave.retry();
          }}
        />
      ) : null}
      <InstructionMarkdownPreview source={previewSource} isSample={previewIsSample} />
      <div className="button-row">
        <button
          id="generate-instructions"
          type="button"
          disabled={!generateEnabled}
          aria-label={instructionsGenerateAccessibleName(generateEnabled)}
          onClick={(): void => {
            instructionsAfterGenerateClick(carouselRef.current);
          }}
        >
          Generate
        </button>
      </div>
      <p className="field-hint" id="generate-instructions-hint">
        {INSTRUCTIONS_GENERATE_HINT}
      </p>
    </section>
  );
}

/**
 * Preview of the draft, or of the sample while the textarea is empty.
 *
 * @param props - Markdown source and whether it is the unsaved sample
 * @returns Rendered headings, paragraphs, lists, and emphasis
 */
export function InstructionMarkdownPreview({
  source,
  isSample,
}: {
  source: string;
  isSample: boolean;
}): ReactElement {

  const html: string = renderInstructionMarkdown(source);

  return (
    <div className="instruction-preview" id="instruction-preview">
      {isSample ? <p className="field-hint">Sample. Not saved.</p> : null}
      <div dangerouslySetInnerHTML={{ __html: html }} />
    </div>
  );
}

function createdInstructionId(carousel: CarouselReadResponse): string | null {

  const documents: CarouselInstructionReadResponse[] = orderedInstructionDocuments(
    carousel.instructions,
  );
  const created: CarouselInstructionReadResponse | undefined = documents[
    documents.length - 1
  ];

  if (created === undefined) {
    return null;
  }

  return created.id;
}

function findAddedDocument(
  beforeIds: readonly string[],
  documents: readonly CarouselInstructionReadResponse[],
): CarouselInstructionReadResponse | null {

  const knownIds: Set<string> = new Set(beforeIds);
  const orderedDocuments: CarouselInstructionReadResponse[] = orderedInstructionDocuments(
    documents,
  );
  const created: CarouselInstructionReadResponse | undefined = orderedDocuments.find(
    (document: CarouselInstructionReadResponse): boolean => !knownIds.has(document.id),
  );

  if (created === undefined) {
    return null;
  }

  return created;
}
