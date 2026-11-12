import { useEffect, useRef, useState, type ReactElement } from "react";

import {
  createCarouselInstruction,
  patchCarouselInstruction,
} from "../api/client";
import type {
  CarouselInstructionReadResponse,
  CarouselReadResponse,
} from "../api/types";
import { SkeletonAutosaveStatus } from "./SkeletonAutosaveStatus";
import {
  instructionBodyForSave,
  instructionDraftFingerprint,
  instructionDraftFromDocument,
  instructionDraftReadiness,
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
 * Step 1: edit one instruction document, with a preview and autosave.
 *
 * The textarea starts empty. The sample is only the placeholder. The
 * first text POSTs a document. A later edit PATCHes that row. Clearing
 * a stored document leaves the row and stores `""`. A reader sees a
 * disabled textarea and does not schedule a save.
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
  const openDocument: CarouselInstructionReadResponse | null = documents[0] ?? null;
  const otherDocuments: CarouselInstructionReadResponse[] = documents.slice(1);
  const [trackedCarouselId, setTrackedCarouselId] = useState<string>(carousel.id);
  const [draft, setDraft] = useState<InstructionDraft>(
    instructionDraftFromDocument(openDocument),
  );
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

  const previewIsSample: boolean = draft.body === "";
  const previewSource: string = previewIsSample
    ? INSTRUCTION_SAMPLE_TEMPLATE
    : draft.body;

  return (
    <section
      id="carousel-instructions"
      className="stack-form"
      aria-label="Instructions"
    >
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
      {otherDocuments.length === 0 ? null : (
        <ol className="instruction-documents">
          {otherDocuments.map((document: CarouselInstructionReadResponse): ReactElement => (
            <li key={document.id}>
              <pre className="instruction-source">{document.body}</pre>
            </li>
          ))}
        </ol>
      )}
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
