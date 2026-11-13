import assert from "node:assert/strict";

import type { CarouselInstructionReadResponse } from "./src/api/types.ts";
import {
  COLLECTION_GENERATE_HINT,
  COLLECTION_GENERATE_NEEDS_TEXT,
  COLLECTION_GENERATE_PENDING,
  collectionGenerateAccessibleName,
  collectionGenerateEnabled,
  collectionGenerateStatusMessage,
} from "./src/pages/carouselCollection.ts";
import type { InstructionDraft } from "./src/pages/carouselInstructions.ts";
import { INSTRUCTION_SAMPLE_TEMPLATE } from "./src/pages/instructionTemplate.ts";

const emptyDraft: InstructionDraft = { instructionId: null, body: "" };
const writtenDocument: CarouselInstructionReadResponse = {
  id: "written",
  position: 0,
  body: "Keep the quay.",
};
const writtenDraft: InstructionDraft = {
  instructionId: "written",
  body: "Keep the quay.",
};
const providerOffDetail: string = "Generate is off until OPENAI_API_KEY is set.";

assert.equal(
  collectionGenerateEnabled(
    [],
    emptyDraft,
    true,
    true,
    false,
    INSTRUCTION_SAMPLE_TEMPLATE,
  ),
  false,
);
assert.equal(
  collectionGenerateEnabled(
    [writtenDocument],
    writtenDraft,
    true,
    true,
    false,
    INSTRUCTION_SAMPLE_TEMPLATE,
  ),
  true,
);
assert.equal(
  collectionGenerateEnabled(
    [writtenDocument],
    writtenDraft,
    false,
    true,
    false,
    INSTRUCTION_SAMPLE_TEMPLATE,
  ),
  false,
);
assert.equal(
  collectionGenerateEnabled(
    [writtenDocument],
    writtenDraft,
    true,
    false,
    false,
    INSTRUCTION_SAMPLE_TEMPLATE,
  ),
  false,
);
assert.equal(
  collectionGenerateEnabled(
    [writtenDocument],
    writtenDraft,
    true,
    true,
    true,
    INSTRUCTION_SAMPLE_TEMPLATE,
  ),
  false,
);

assert.equal(
  collectionGenerateAccessibleName(
    [],
    emptyDraft,
    true,
    "",
    false,
    INSTRUCTION_SAMPLE_TEMPLATE,
  ),
  COLLECTION_GENERATE_NEEDS_TEXT,
);
assert.equal(
  collectionGenerateAccessibleName(
    [writtenDocument],
    writtenDraft,
    false,
    providerOffDetail,
    false,
    INSTRUCTION_SAMPLE_TEMPLATE,
  ),
  `Generate. ${providerOffDetail}`,
);
assert.equal(
  collectionGenerateAccessibleName(
    [writtenDocument],
    writtenDraft,
    true,
    "",
    true,
    INSTRUCTION_SAMPLE_TEMPLATE,
  ),
  COLLECTION_GENERATE_PENDING,
);
assert.equal(
  COLLECTION_GENERATE_HINT,
  "Generate writes a draft set from the instructions, the album, and the research. Accept the set to make those slides live.",
);
assert.doesNotMatch(COLLECTION_GENERATE_HINT, /later phase/);
assert.equal(
  collectionGenerateStatusMessage(4),
  "Drafted a set of 4 slides. Accept the set to make them live.",
);
