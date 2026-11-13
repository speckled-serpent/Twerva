import assert from "node:assert/strict";

import type { CarouselStepsResponse } from "./src/api/types.ts";
import {
  CAROUSEL_EDITOR_BLOCKS,
  CAROUSEL_LIST_LEDE,
  CAROUSEL_PAGE_SECTIONS,
  carouselPageLede,
  carouselPageSection,
  finalSectionNotice,
  sectionIsVisible,
  slidesSectionNotice,
  type CarouselEditorBlock,
  type CarouselPageSection,
} from "./src/pages/carouselPage.ts";
import {
  FINAL_CLOSED_DETAIL,
  SLIDES_ALBUM_REQUIRED_DETAIL,
} from "./src/pages/carouselSteps.ts";

const lockedSlides: CarouselStepsResponse = {
  basic: "done",
  instructions: "available",
  content: "available",
  slides: "locked",
  final: "locked",
};

const availableSlides: CarouselStepsResponse = {
  basic: "done",
  instructions: "done",
  content: "done",
  slides: "available",
  final: "locked",
};

const doneSlides: CarouselStepsResponse = {
  basic: "done",
  instructions: "done",
  content: "done",
  slides: "done",
  final: "locked",
};

assert.deepEqual(
  CAROUSEL_PAGE_SECTIONS.map((section: CarouselPageSection): string => section.label),
  ["Basic", "Instructions", "Content", "Slides", "Final"],
);
assert.deepEqual(
  CAROUSEL_PAGE_SECTIONS.map((section: CarouselPageSection): string => section.href),
  [
    "#carousel-basic",
    "#carousel-instructions",
    "#carousel-content",
    "#carousel-slides",
    "#carousel-final",
  ],
);

for (const section of CAROUSEL_PAGE_SECTIONS) {
  assert.equal(section.href, `#${section.id}`);
  assert.equal(/^\d/.test(section.label), false);
}

assert.deepEqual(
  CAROUSEL_EDITOR_BLOCKS.map((block: CarouselEditorBlock): string => (
    block.kind === "generate" ? "generate" : block.key
  )),
  ["basic", "instructions", "content", "generate", "slides", "final"],
);

const contentIndex: number = CAROUSEL_EDITOR_BLOCKS.findIndex(
  (block: CarouselEditorBlock): boolean => block.kind === "section" && block.key === "content",
);
const generateIndex: number = CAROUSEL_EDITOR_BLOCKS.findIndex(
  (block: CarouselEditorBlock): boolean => block.kind === "generate",
);
const slidesIndex: number = CAROUSEL_EDITOR_BLOCKS.findIndex(
  (block: CarouselEditorBlock): boolean => block.kind === "section" && block.key === "slides",
);

assert.equal(generateIndex, contentIndex + 1);
assert.equal(slidesIndex, generateIndex + 1);
assert.equal(
  CAROUSEL_PAGE_SECTIONS.some((section: CarouselPageSection): boolean => section.label === "Generate"),
  false,
);

assert.equal(slidesSectionNotice(lockedSlides), SLIDES_ALBUM_REQUIRED_DETAIL);
assert.equal(slidesSectionNotice(availableSlides), null);
assert.equal(slidesSectionNotice(doneSlides), null);
assert.equal(finalSectionNotice(), FINAL_CLOSED_DETAIL);
assert.match(finalSectionNotice(), /later phase/);

const storedSteps: number[] = [0, 1, 2, 3];
const slideStates: CarouselStepsResponse[] = [lockedSlides, availableSlides, doneSlides];

for (const section of CAROUSEL_PAGE_SECTIONS) {
  for (const editorStep of storedSteps) {
    for (const steps of slideStates) {
      assert.equal(sectionIsVisible(section, editorStep, steps), true);
    }
  }
}

const unknownSection: CarouselPageSection = {
  id: "carousel-missing",
  label: "Missing",
  href: "#carousel-missing",
  key: "basic",
};

assert.equal(sectionIsVisible(unknownSection, 0, lockedSlides), false);
assert.equal(sectionIsVisible(carouselPageSection("slides"), 1.5, lockedSlides), true);
assert.equal(sectionIsVisible(carouselPageSection("final"), 4, lockedSlides), true);

const lede: string = carouselPageLede(4);

assert.match(lede, /Basic, instructions, content, and slides are on this page/);
assert.match(lede, /4 live/);
assert.doesNotMatch(lede, /opens on/);
assert.match(CAROUSEL_LIST_LEDE, /one page/);
assert.doesNotMatch(CAROUSEL_LIST_LEDE, /saved step/);
assert.equal(carouselPageSection("content").id, "carousel-content");
assert.equal(carouselPageSection("slides").label, "Slides");
