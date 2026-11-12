import assert from "node:assert/strict";

import {
  instructionBodyForSave,
  instructionDraftFingerprint,
  instructionDraftFromDocument,
  instructionDraftReadiness,
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
