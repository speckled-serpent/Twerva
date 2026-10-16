import assert from "node:assert/strict";

import {
  DEFAULT_PREVIEW_WORD_COUNT,
  clampPreviewWordCount,
  loremIpsumWords,
  previewWordCountFromInput,
  textElementsInFrameOrder,
  wordCountForElement,
} from "./src/pages/themePreviewText.ts";

assert.equal(DEFAULT_PREVIEW_WORD_COUNT, 8);
assert.equal(clampPreviewWordCount(8), 8);
assert.equal(clampPreviewWordCount(0), 0);
assert.equal(clampPreviewWordCount(70), 70);
assert.equal(clampPreviewWordCount(71), 70);
assert.equal(clampPreviewWordCount(-4), 0);
assert.equal(clampPreviewWordCount(8.9), 8);
assert.equal(clampPreviewWordCount(Number.NaN), 8);

assert.equal(previewWordCountFromInput(""), 0);
assert.equal(previewWordCountFromInput("  12 "), 12);
assert.equal(previewWordCountFromInput("08"), 8);
assert.equal(previewWordCountFromInput("80"), 70);
assert.equal(previewWordCountFromInput("8.5"), null);
assert.equal(previewWordCountFromInput("nope"), null);

assert.equal(wordCountForElement({}, "title"), 8);
assert.equal(wordCountForElement({ title: 3 }, "title"), 3);
assert.equal(wordCountForElement({ title: 90 }, "title"), 70);

const eightWords: string = loremIpsumWords(8);
assert.equal(
  eightWords,
  "Lorem ipsum dolor sit amet, consectetur adipiscing elit,",
);
assert.equal(eightWords.split(/\s+/).length, 8);
assert.equal(loremIpsumWords(0), "");
assert.equal(loremIpsumWords(1), "Lorem");
assert.equal(loremIpsumWords(69).split(/\s+/).at(-1), "laborum.");
assert.equal(loremIpsumWords(70).split(/\s+/).length, 70);
assert.equal(loremIpsumWords(70).split(/\s+/).at(-1), "Lorem");
assert.equal(loremIpsumWords(80).split(/\s+/).length, 70);
assert.equal(loremIpsumWords(4), loremIpsumWords(4));

const orderedNames: string[] = textElementsInFrameOrder([
  { name: "middle-late", band: "middle", sort_order: 1, content_kind: "text" },
  { name: "photo", band: "top", sort_order: 0, content_kind: "image" },
  { name: "bottom", band: "bottom", sort_order: 0, content_kind: "text" },
  { name: "top", band: "top", sort_order: 2, content_kind: "text" },
  { name: "middle-early", band: "middle", sort_order: 0, content_kind: "text" },
]).map((element: { name: string }): string => element.name);

assert.deepEqual(orderedNames, ["top", "middle-early", "middle-late", "bottom"]);
