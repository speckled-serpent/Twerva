import assert from "node:assert/strict";

import type {
  CarouselResearchReadResponse,
  ResearchCreateRequest,
  ResearchListItemResponse,
} from "./src/api/types.ts";
import {
  RESEARCH_ALL_ATTACHED_COPY,
  RESEARCH_BODY_STAYS_COPY,
  RESEARCH_EMPTY_LIBRARY_COPY,
  RESEARCH_NONE_ATTACHED_COPY,
  RESEARCH_READONLY_COPY,
  RESEARCH_TITLE_REQUIRED_COPY,
  moveAttachedResearch,
  researchActionErrorText,
  researchCreateRequest,
  researchInPositionOrder,
  researchItemIds,
  researchToChoose,
  trimmedResearchTitle,
} from "./src/pages/carouselResearch.ts";

assert.match(RESEARCH_NONE_ATTACHED_COPY, /optional/i);
assert.match(RESEARCH_NONE_ATTACHED_COPY, /none is attached/i);
assert.equal(RESEARCH_EMPTY_LIBRARY_COPY, "No research yet.");
assert.equal(RESEARCH_ALL_ATTACHED_COPY, "Every research item is already attached.");
assert.equal(RESEARCH_TITLE_REQUIRED_COPY, "Title is required.");
assert.match(RESEARCH_BODY_STAYS_COPY, /body stays on the Research page/);
assert.match(RESEARCH_READONLY_COPY, /admin action/);
assert.equal(trimmedResearchTitle("  "), null);
assert.equal(trimmedResearchTitle("  Field notes  "), "Field notes");

const createRequest: ResearchCreateRequest = researchCreateRequest("Field notes");
assert.deepEqual(createRequest, { title: "Field notes" });
assert.equal(Object.hasOwn(createRequest, "body"), false);

const harbor: CarouselResearchReadResponse = attachedResearch("harbor", "Harbor notes", 0);
const amber: CarouselResearchReadResponse = attachedResearch("amber", "Amber notes", 1);
const movedDown: CarouselResearchReadResponse[] | null = moveAttachedResearch(
  [harbor, amber],
  0,
  1,
);

if (movedDown === null) {
  throw new Error("Moving the first document down should fit.");
}

assert.deepEqual(researchItemIds(movedDown), ["amber", "harbor"]);

const reloaded: CarouselResearchReadResponse[] = researchInPositionOrder([
  attachedResearch("harbor", "Harbor notes", 1),
  attachedResearch("amber", "Amber notes", 0),
]);
assert.deepEqual(researchItemIds(reloaded), ["amber", "harbor"]);
assert.equal(moveAttachedResearch([harbor, amber], 0, -1), null);
assert.equal(moveAttachedResearch([harbor, amber], 1, 1), null);

const library: ResearchListItemResponse[] = [
  libraryResearch("amber", "Amber notes"),
  libraryResearch("harbor", "Harbor notes"),
];
assert.deepEqual(
  researchToChoose(library, [harbor, amber]).map(libraryTitle),
  [],
);
assert.deepEqual(
  researchToChoose(library, [harbor]).map(libraryTitle),
  ["Amber notes"],
);
assert.deepEqual(researchToChoose([], []).map(libraryTitle), []);

const conflict: { detailText: string } = { detailText: "Research item not found." };
assert.equal(researchActionErrorText(conflict), "Research item not found.");
assert.equal(
  researchActionErrorText(new Error("Research could not be attached.")),
  "Research could not be attached.",
);
assert.equal(researchActionErrorText("nope"), "The research list could not be changed.");

function attachedResearch(
  id: string,
  title: string,
  position: number,
): CarouselResearchReadResponse {

  return {
    id,
    title,
    slug: id,
    position,
  };
}

function libraryResearch(id: string, title: string): ResearchListItemResponse {

  return {
    id,
    title,
    slug: id,
    word_count: 0,
    character_count: 0,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

function libraryTitle(researchItem: ResearchListItemResponse): string {

  return researchItem.title;
}
