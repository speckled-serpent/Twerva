import assert from "node:assert/strict";

import type { CarouselInstructionReadResponse } from "./src/api/types.ts";
import {
  INSTRUCTION_SAMPLE_TEMPLATE,
  orderedInstructionDocuments,
} from "./src/pages/instructionTemplate.ts";

const sample: string = [
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

assert.equal(INSTRUCTION_SAMPLE_TEMPLATE, sample);
assert.equal(INSTRUCTION_SAMPLE_TEMPLATE.includes("textarea"), false);

const later: CarouselInstructionReadResponse = {
  id: "later",
  position: 1,
  body: "Second",
};
const earlier: CarouselInstructionReadResponse = {
  id: "earlier",
  position: 0,
  body: "",
};
const ordered: CarouselInstructionReadResponse[] = orderedInstructionDocuments([
  later,
  earlier,
]);

assert.deepEqual(
  ordered.map((document: CarouselInstructionReadResponse): number => document.position),
  [0, 1],
);
assert.equal(ordered[0]?.body, "");
assert.equal(ordered[1]?.body, "Second");
assert.deepEqual(orderedInstructionDocuments([]), []);
