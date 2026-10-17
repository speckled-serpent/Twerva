import type { SkeletonElementBand, SkeletonElementContentKind } from "../api/types";

export const PREVIEW_WORD_COUNT_MIN: number = 0;
export const PREVIEW_WORD_COUNT_MAX: number = 70;
export const DEFAULT_PREVIEW_WORD_COUNT: number = 8;

/**
 * Classic lorem ipsum, one whitespace-separated token per entry.
 *
 * Punctuation stays on the word it follows so a count is a word count.
 * The paragraph is 69 words. Counts past that repeat from the start.
 */
const LOREM_IPSUM_WORDS: readonly string[] = [
  "Lorem",
  "ipsum",
  "dolor",
  "sit",
  "amet,",
  "consectetur",
  "adipiscing",
  "elit,",
  "sed",
  "do",
  "eiusmod",
  "tempor",
  "incididunt",
  "ut",
  "labore",
  "et",
  "dolore",
  "magna",
  "aliqua.",
  "Ut",
  "enim",
  "ad",
  "minim",
  "veniam,",
  "quis",
  "nostrud",
  "exercitation",
  "ullamco",
  "laboris",
  "nisi",
  "ut",
  "aliquip",
  "ex",
  "ea",
  "commodo",
  "consequat.",
  "Duis",
  "aute",
  "irure",
  "dolor",
  "in",
  "reprehenderit",
  "in",
  "voluptate",
  "velit",
  "esse",
  "cillum",
  "dolore",
  "eu",
  "fugiat",
  "nulla",
  "pariatur.",
  "Excepteur",
  "sint",
  "occaecat",
  "cupidatat",
  "non",
  "proident,",
  "sunt",
  "in",
  "culpa",
  "qui",
  "officia",
  "deserunt",
  "mollit",
  "anim",
  "id",
  "est",
  "laborum.",
];

export interface FrameOrderedElement {
  band: SkeletonElementBand;
  sort_order?: number | null;
  content_kind: SkeletonElementContentKind;
}

/**
 * Keep an integer word count inside 0 through 70.
 *
 * Non-finite values use the preview default. The fractional part is dropped.
 *
 * @param wordCount - Raw count from an input or a stored preview value
 * @returns A count the preview can render
 */
export function clampPreviewWordCount(wordCount: number): number {

  if (!Number.isFinite(wordCount)) {
    return DEFAULT_PREVIEW_WORD_COUNT;
  }

  const truncatedCount: number = Math.trunc(wordCount);

  if (truncatedCount < PREVIEW_WORD_COUNT_MIN) {
    return PREVIEW_WORD_COUNT_MIN;
  }

  if (truncatedCount > PREVIEW_WORD_COUNT_MAX) {
    return PREVIEW_WORD_COUNT_MAX;
  }

  return truncatedCount;
}

/**
 * Parse a word-count field. Empty is zero. Anything other than digits is ignored.
 *
 * @param rawValue - The input's current text
 * @returns A clamped count, or null when the text is not a whole number
 */
export function previewWordCountFromInput(rawValue: string): number | null {

  const trimmedValue: string = rawValue.trim();

  if (trimmedValue === "") {
    return PREVIEW_WORD_COUNT_MIN;
  }

  if (!/^\d+$/.test(trimmedValue)) {
    return null;
  }

  const parsedCount: number = clampPreviewWordCount(Number(trimmedValue));

  return parsedCount;
}

/**
 * Return the stored count for one element, or the default when it has none.
 *
 * @param wordCounts - Preview-only counts keyed by element id
 * @param elementId - Text element whose input is showing
 * @returns A clamped word count
 */
export function wordCountForElement(
  wordCounts: Record<string, number>,
  elementId: string,
): number {

  const storedCount: number | undefined = wordCounts[elementId];

  if (storedCount === undefined) {
    return DEFAULT_PREVIEW_WORD_COUNT;
  }

  const clampedCount: number = clampPreviewWordCount(storedCount);

  return clampedCount;
}

/**
 * Build lorem ipsum of exactly ``wordCount`` words, after clamping.
 *
 * The sequence is the standard paragraph. Word 70 is ``Lorem`` again.
 * Zero words is an empty string.
 *
 * @param wordCount - How many words the text element should show
 * @returns Space-separated lorem ipsum
 */
export function loremIpsumWords(wordCount: number): string {

  const clampedCount: number = clampPreviewWordCount(wordCount);

  if (clampedCount === 0) {
    return "";
  }

  const words: string[] = [];

  for (let index: number = 0; index < clampedCount; index += 1) {
    const word: string = LOREM_IPSUM_WORDS[index % LOREM_IPSUM_WORDS.length];
    words.push(word);
  }

  const previewText: string = words.join(" ");

  return previewText;
}

/**
 * Text elements only, top then middle then bottom, and sort order inside a band.
 *
 * @param elements - Frame elements in any order
 * @returns Text elements in the order the frame draws them
 */
export function textElementsInFrameOrder<ElementType extends FrameOrderedElement>(
  elements: readonly ElementType[],
): ElementType[] {

  const bandRank: Record<SkeletonElementBand, number> = {
    top: 0,
    middle: 1,
    bottom: 2,
  };
  const textElements: ElementType[] = elements.filter(
    (element: ElementType): boolean => element.content_kind === "text",
  );
  const orderedElements: ElementType[] = [...textElements].sort(
    (left: ElementType, right: ElementType): number => {

      const bandDelta: number = bandRank[left.band] - bandRank[right.band];

      if (bandDelta !== 0) {
        return bandDelta;
      }

      const leftSort: number = left.sort_order ?? 0;
      const rightSort: number = right.sort_order ?? 0;

      return leftSort - rightSort;
    },
  );

  return orderedElements;
}
