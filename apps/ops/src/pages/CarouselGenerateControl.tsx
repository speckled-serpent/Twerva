import { useState, type ReactElement } from "react";

import { generateCarouselCollection } from "../api/client";
import type {
  CarouselReadResponse,
  PendingSlideDraftBatchResponse,
  TextGenerationStatusResponse,
} from "../api/types";
import {
  COLLECTION_GENERATE_HINT,
  collectionGenerateAccessibleName,
  collectionGenerateEnabled,
  collectionGenerateStatusMessage,
} from "./carouselCollection";
import type { InstructionDraft } from "./carouselInstructions";
import { INSTRUCTION_SAMPLE_TEMPLATE } from "./instructionTemplate";

export interface CarouselGenerateControlProps {
  carousel: CarouselReadResponse;
  instructionDraft: InstructionDraft;
  canWrite: boolean;
  textGeneration: TextGenerationStatusResponse;
  flushBeforeGenerate: (afterFlush: () => void) => void;
  onCarouselSaved: (savedCarousel: CarouselReadResponse) => void;
  onStatusMessage: (message: string) => void;
  onError: (error: unknown) => void;
}

/**
 * Generate for the whole carousel, placed under Content.
 *
 * The click flushes open edits, then posts the collection route.
 * A reader, a provider that is off, and a pending set stay disabled.
 *
 * @param props - The open carousel, the instruction draft, and the save callbacks
 * @returns The button, the hint, and the provider message when Generate is off
 */
export function CarouselGenerateControl({
  carousel,
  instructionDraft,
  canWrite,
  textGeneration,
  flushBeforeGenerate,
  onCarouselSaved,
  onStatusMessage,
  onError,
}: CarouselGenerateControlProps): ReactElement {

  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const hasPendingBatch: boolean = carousel.pending_slide_draft_batch !== null;
  const enabled: boolean = collectionGenerateEnabled(
    carousel.instructions,
    instructionDraft,
    canWrite,
    textGeneration.available,
    hasPendingBatch,
    INSTRUCTION_SAMPLE_TEMPLATE,
  );
  const accessibleName: string = isGenerating
    ? "Generating…"
    : collectionGenerateAccessibleName(
      carousel.instructions,
      instructionDraft,
      textGeneration.available,
      textGeneration.detail,
      hasPendingBatch,
      INSTRUCTION_SAMPLE_TEMPLATE,
    );

  const draftCollection = async (): Promise<void> => {
    setIsGenerating(true);
    onError(null);

    try {
      const savedCarousel: CarouselReadResponse = await generateCarouselCollection(carousel.id);
      const pendingBatch: PendingSlideDraftBatchResponse | null =
        savedCarousel.pending_slide_draft_batch;
      const slideCount: number = pendingBatch === null ? 0 : pendingBatch.slide_count;
      onCarouselSaved(savedCarousel);
      onStatusMessage(collectionGenerateStatusMessage(slideCount));
    } catch (caughtError: unknown) {
      onError(caughtError);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="carousel-generate" id="carousel-generate">
      <div className="button-row">
        <button
          id="generate-instructions"
          type="button"
          disabled={!enabled || isGenerating}
          aria-label={accessibleName}
          onClick={(): void => {
            flushBeforeGenerate((): void => {
              void draftCollection();
            });
          }}
        >
          {isGenerating ? "Generating…" : "Generate"}
        </button>
      </div>
      <p className="field-hint" id="generate-instructions-hint">
        {COLLECTION_GENERATE_HINT}
      </p>
      {textGeneration.available ? null : (
        <p className="field-hint" id="generate-instructions-unavailable">
          {textGeneration.detail}
        </p>
      )}
    </div>
  );
}
