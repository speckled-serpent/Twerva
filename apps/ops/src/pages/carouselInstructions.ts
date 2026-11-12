import type { CarouselInstructionReadResponse } from "../api/types";
import type { AutosaveReadiness } from "./skeletonAutosave";

/**
 * The instruction body being edited.
 *
 * `instructionId` is null until the first typed save creates a row.
 * `body` is the textarea value. The sample is the placeholder, not this
 * string.
 */
export interface InstructionDraft {
  instructionId: string | null;
  body: string;
}

/**
 * Draft for a stored document, or an empty editor when the carousel has none.
 *
 * The sample template is not copied into the body.
 *
 * @param document - The document being edited, or null when there is no row
 * @returns The textarea draft
 */
export function instructionDraftFromDocument(
  document: CarouselInstructionReadResponse | null,
): InstructionDraft {

  if (document === null) {
    const emptyDraft: InstructionDraft = {
      instructionId: null,
      body: "",
    };

    return emptyDraft;
  }

  const storedDraft: InstructionDraft = {
    instructionId: document.id,
    body: document.body,
  };

  return storedDraft;
}

/**
 * Whether autosave should write this draft.
 *
 * Text is ready, including the first draft that has no row yet. A stored
 * document's empty body is ready, so clearing it PATCHes `""`. An empty
 * draft with no row is idle (`skip`), so autosave does not POST. The
 * sample placeholder is not a stored body.
 *
 * @param draft - The textarea draft
 * @returns Ready to save, or skip while the empty editor has no row
 */
export function instructionDraftReadiness(draft: InstructionDraft): AutosaveReadiness {

  if (draft.instructionId === null && draft.body === "") {
    const idle: AutosaveReadiness = { kind: "skip" };

    return idle;
  }

  const ready: AutosaveReadiness = { kind: "ready" };

  return ready;
}

/**
 * Identity of a body that should be written.
 *
 * The placeholder string is not this value. An empty textarea fingerprints
 * as `""`.
 *
 * @param draft - The textarea draft
 * @returns The body to store
 */
export function instructionDraftFingerprint(draft: InstructionDraft): string {

  return draft.body;
}

/**
 * The body a save sends. Never the sample placeholder.
 *
 * @param draft - A draft `instructionDraftReadiness` has called ready
 * @returns The textarea value
 */
export function instructionBodyForSave(draft: InstructionDraft): string {

  return draft.body;
}
