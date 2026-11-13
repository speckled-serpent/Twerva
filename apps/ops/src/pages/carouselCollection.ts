import type { CarouselInstructionReadResponse } from "../api/types";
import {
  instructionsGenerateEnabled,
  type InstructionDraft,
} from "./carouselInstructions.ts";

/** Line under the carousel Generate button. */
export const COLLECTION_GENERATE_HINT: string =
  "Generate writes a draft set from the instructions, the album, and the research. Accept the set to make those slides live.";

/** Accessible name when no instruction document has text. */
export const COLLECTION_GENERATE_NEEDS_TEXT: string =
  "Generate. Add instruction text first.";

/** Accessible name while a generated set is still waiting. */
export const COLLECTION_GENERATE_PENDING: string =
  "Generate. Accept or discard the generated set first.";

/**
 * Whether Generate can draft a set.
 *
 * An admin needs instruction text, a provider that is on, and no pending
 * set. A reader stays disabled. The sample placeholder does not count.
 *
 * @param documents - Stored instruction documents
 * @param draft - The textarea for the selected document
 * @param canWrite - True for an admin
 * @param textGenerationAvailable - True when the provider can be called
 * @param hasPendingBatch - True when a generated set is still waiting
 * @param placeholder - The sample text, which does not count as instruction text
 * @returns True when the button can be pressed
 */
export function collectionGenerateEnabled(
  documents: readonly CarouselInstructionReadResponse[],
  draft: InstructionDraft,
  canWrite: boolean,
  textGenerationAvailable: boolean,
  hasPendingBatch: boolean,
  placeholder: string = "",
): boolean {

  if (!canWrite || !textGenerationAvailable || hasPendingBatch) {
    return false;
  }

  return instructionsGenerateEnabled(documents, draft, true, placeholder);
}

/**
 * Accessible name for the carousel Generate button.
 *
 * No instruction text, a provider that is off, and a pending set each
 * name the reason. Otherwise the name is Generate.
 *
 * @param documents - Stored instruction documents
 * @param draft - The textarea for the selected document
 * @param textGenerationAvailable - True when the provider can be called
 * @param textGenerationDetail - The message shown when the provider is off
 * @param hasPendingBatch - True when a generated set is still waiting
 * @param placeholder - The sample text, which does not count as instruction text
 * @returns The accessible name
 */
export function collectionGenerateAccessibleName(
  documents: readonly CarouselInstructionReadResponse[],
  draft: InstructionDraft,
  textGenerationAvailable: boolean,
  textGenerationDetail: string,
  hasPendingBatch: boolean,
  placeholder: string = "",
): string {

  const hasInstructionText: boolean = instructionsGenerateEnabled(
    documents,
    draft,
    true,
    placeholder,
  );

  if (!hasInstructionText) {
    return COLLECTION_GENERATE_NEEDS_TEXT;
  }

  if (!textGenerationAvailable) {
    return `Generate. ${textGenerationDetail}`;
  }

  if (hasPendingBatch) {
    return COLLECTION_GENERATE_PENDING;
  }

  return "Generate";
}

/**
 * Status line after a set is drafted.
 *
 * @param slideCount - How many slides the set contains
 * @returns The status sentence
 */
export function collectionGenerateStatusMessage(slideCount: number): string {

  return `Drafted a set of ${slideCount} slides. Accept the set to make them live.`;
}
