import type {
  SkeletonElementBand,
  SkeletonElementReadResponse,
  SkeletonReadResponse,
  SlideElementTextReadResponse,
  SlideReadResponse,
} from "../api/types";

const BAND_RANK: Record<SkeletonElementBand, number> = {
  top: 0,
  middle: 1,
  bottom: 2,
};

/**
 * True when the slide form should ask for an image.
 *
 * @param skeleton - The carousel's skeleton
 * @returns True for a picture background or any image element
 */
export function skeletonRequiresImage(skeleton: SkeletonReadResponse): boolean {

  if (skeleton.background_kind === "picture") {
    return true;
  }

  const hasImageElement: boolean = skeleton.elements.some(
    (element: SkeletonElementReadResponse): boolean => element.content_kind === "image",
  );

  return hasImageElement;
}

/**
 * Text elements in the same order the frame draws them.
 *
 * @param elements - Elements on the carousel's skeleton
 * @returns Text elements, band then sort order
 */
export function orderedTextElements(
  elements: readonly SkeletonElementReadResponse[],
): SkeletonElementReadResponse[] {

  const textElements: SkeletonElementReadResponse[] = elements.filter(
    (element: SkeletonElementReadResponse): boolean => element.content_kind === "text",
  );
  const orderedElements: SkeletonElementReadResponse[] = [...textElements].sort(
    (left: SkeletonElementReadResponse, right: SkeletonElementReadResponse): number => {
      const bandDifference: number = BAND_RANK[left.band] - BAND_RANK[right.band];

      if (bandDifference !== 0) {
        return bandDifference;
      }

      return left.sort_order - right.sort_order;
    },
  );

  return orderedElements;
}

/**
 * Label for one text input. The element's name is the label.
 *
 * A repeated name adds the band and sort order.
 *
 * @param element - The text element this input edits
 * @param textElements - Every text element on the skeleton, in frame order
 * @returns The label shown beside the input
 */
export function labelForTextElement(
  element: SkeletonElementReadResponse,
  textElements: readonly SkeletonElementReadResponse[],
): string {

  const elementName: string = displayName(element);
  const sameNameCount: number = textElements.filter(
    (otherElement: SkeletonElementReadResponse): boolean => (
      displayName(otherElement) === elementName
    ),
  ).length;

  if (sameNameCount < 2) {
    return elementName;
  }

  const bandName: string = element.band;
  const bandLabel: string = bandName.slice(0, 1).toUpperCase() + bandName.slice(1);

  return `${elementName} (${bandLabel}, ${element.sort_order})`;
}

function displayName(element: SkeletonElementReadResponse): string {

  const trimmedName: string = element.name.trim();

  if (trimmedName === "") {
    return "Text";
  }

  return trimmedName;
}

/**
 * One stored string per text element. Missing rows stay blank.
 *
 * @param skeleton - The carousel's skeleton
 * @param slide - The slide being edited, or null for a new slide
 * @returns Element id to the current value
 */
export function textDraftsForSkeleton(
  skeleton: SkeletonReadResponse,
  slide: SlideReadResponse | null,
): Record<string, string> {

  const shownTexts: SlideElementTextReadResponse[] = slide === null
    ? []
    : slide.text_status === "draft"
      ? slide.draft_texts
      : slide.texts;
  const storedValues: Map<string, string> = new Map(
    shownTexts.map((elementText): [string, string] => [
      elementText.skeleton_element_id,
      elementText.value,
    ]),
  );
  const drafts: Record<string, string> = {};

  for (const element of orderedTextElements(skeleton.elements)) {
    drafts[element.id] = storedValues.get(element.id) ?? "";
  }

  return drafts;
}
