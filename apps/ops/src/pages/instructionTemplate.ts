import type { CarouselInstructionReadResponse } from "../api/types";

/**
 * Documents in position order.
 *
 * The detail route already returns that order. Sorting keeps a
 * reversed payload in the same order the step shows.
 *
 * @param documents - Instruction rows from the carousel detail
 * @returns A new list sorted by position
 */
export function orderedInstructionDocuments(
  documents: readonly CarouselInstructionReadResponse[],
): CarouselInstructionReadResponse[] {

  const orderedDocuments: CarouselInstructionReadResponse[] = [...documents];
  orderedDocuments.sort(
    (
      left: CarouselInstructionReadResponse,
      right: CarouselInstructionReadResponse,
    ): number => left.position - right.position,
  );

  return orderedDocuments;
}

/**
 * Sample shown in an empty Instructions step.
 *
 * It is a placeholder for the operator. It is not written to a document
 * unless the operator types it. Task 5.6 uses this same text as the
 * textarea placeholder.
 */
export const INSTRUCTION_SAMPLE_TEMPLATE: string = [
  "# What this carousel is for",
  "",
  "Who it is for, and what they should take from it.",
  "",
  "## Voice",
  "",
  "Short sentences. One idea per slide.",
  "",
  "## Include",
  "",
  "- The claim this carousel makes",
  "- A fact that has to stay accurate",
  "",
  "## Leave out",
  "",
  "- Anything this carousel should not say",
].join("\n");
