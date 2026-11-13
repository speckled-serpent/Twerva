import assert from "node:assert/strict";

import type { CarouselInstructionReadResponse } from "./src/api/types.ts";
import {
  INSTRUCTION_ADD_BODY,
  instructionBodyForSave,
  instructionDocumentIds,
  instructionDocumentLabel,
  instructionDraftFingerprint,
  instructionDraftFromDocument,
  instructionDraftReadiness,
  type InstructionDraft,
  instructionsGenerateEnabled,
  moveInstructionDocuments,
} from "./src/pages/carouselInstructions.ts";
import { INSTRUCTION_SAMPLE_TEMPLATE } from "./src/pages/instructionTemplate.ts";

const emptyEditor = instructionDraftFromDocument(null);
assert.equal(emptyEditor.instructionId, null);
assert.equal(emptyEditor.body, "");
assert.notEqual(emptyEditor.body, INSTRUCTION_SAMPLE_TEMPLATE);
assert.equal(instructionDraftReadiness(emptyEditor).kind, "skip");
assert.notEqual(instructionDraftFingerprint(emptyEditor), INSTRUCTION_SAMPLE_TEMPLATE);

const storedEmpty = instructionDraftFromDocument({
  id: "document-1",
  position: 0,
  body: "",
});
assert.equal(storedEmpty.instructionId, "document-1");
assert.equal(storedEmpty.body, "");
assert.equal(instructionDraftReadiness(storedEmpty).kind, "ready");
assert.equal(instructionBodyForSave(storedEmpty), "");
assert.notEqual(instructionBodyForSave(storedEmpty), INSTRUCTION_SAMPLE_TEMPLATE);
assert.notEqual(instructionDraftFingerprint(storedEmpty), INSTRUCTION_SAMPLE_TEMPLATE);

const typed = instructionDraftFromDocument(null);
typed.body = "Keep the quay.";
assert.equal(instructionDraftReadiness(typed).kind, "ready");
assert.equal(instructionBodyForSave(typed), "Keep the quay.");
assert.notEqual(instructionBodyForSave(typed), INSTRUCTION_SAMPLE_TEMPLATE);

assert.equal(INSTRUCTION_ADD_BODY, "");
assert.notEqual(INSTRUCTION_ADD_BODY, INSTRUCTION_SAMPLE_TEMPLATE);
assert.equal(instructionDocumentLabel(0), "Document 1");
assert.equal(instructionDocumentLabel(1), "Document 2");

const firstDocument: CarouselInstructionReadResponse = {
  id: "first",
  position: 0,
  body: "Open with the quay.",
};
const secondDocument: CarouselInstructionReadResponse = {
  id: "second",
  position: 1,
  body: "Close on the tide.",
};
const movedDown: CarouselInstructionReadResponse[] | null = moveInstructionDocuments(
  [firstDocument, secondDocument],
  0,
  1,
);

if (movedDown === null) {
  throw new Error("Moving the first document down should fit.");
}

assert.deepEqual(instructionDocumentIds(movedDown), ["second", "first"]);
assert.deepEqual(
  movedDown.map((document: CarouselInstructionReadResponse): string => document.body),
  ["Close on the tide.", "Open with the quay."],
);
assert.equal(moveInstructionDocuments([firstDocument, secondDocument], 0, -1), null);
assert.equal(moveInstructionDocuments([firstDocument, secondDocument], 1, 1), null);

const blankDocument: CarouselInstructionReadResponse = {
  id: "blank",
  position: 0,
  body: "",
};
const spaceDocument: CarouselInstructionReadResponse = {
  id: "space",
  position: 1,
  body: "  \n",
};
const writtenDocument: CarouselInstructionReadResponse = {
  id: "written",
  position: 2,
  body: "Keep the quay.",
};
const emptyDraft: InstructionDraft = { instructionId: null, body: "" };
const placeholderDraft: InstructionDraft = {
  instructionId: null,
  body: INSTRUCTION_SAMPLE_TEMPLATE,
};
const clearedDraft: InstructionDraft = { instructionId: "written", body: "" };

assert.equal(instructionsGenerateEnabled([], emptyDraft, true, INSTRUCTION_SAMPLE_TEMPLATE), false);
assert.equal(
  instructionsGenerateEnabled([], placeholderDraft, true, INSTRUCTION_SAMPLE_TEMPLATE),
  false,
);
assert.equal(
  instructionsGenerateEnabled(
    [blankDocument, spaceDocument, writtenDocument],
    { instructionId: "blank", body: "" },
    true,
    INSTRUCTION_SAMPLE_TEMPLATE,
  ),
  true,
);
assert.equal(
  instructionsGenerateEnabled(
    [blankDocument, spaceDocument, writtenDocument],
    clearedDraft,
    true,
    INSTRUCTION_SAMPLE_TEMPLATE,
  ),
  false,
);
assert.equal(
  instructionsGenerateEnabled(
    [writtenDocument],
    { instructionId: "written", body: "Keep the quay." },
    false,
    INSTRUCTION_SAMPLE_TEMPLATE,
  ),
  false,
);
