import type {
  ThemeElementBand,
  ThemeElementReadResponse,
  ThemeReadResponse,
  UnitElementTextReadResponse,
  UnitReadResponse,
} from "../api/types";

const BAND_RANK: Record<ThemeElementBand, number> = {
  top: 0,
  middle: 1,
  bottom: 2,
};

/**
 * True when the unit form should ask for an image.
 *
 * @param theme - The source's theme
 * @returns True for a picture background or any image element
 */
export function themeRequiresImage(theme: ThemeReadResponse): boolean {

  if (theme.background_kind === "picture") {
    return true;
  }

  const hasImageElement: boolean = theme.elements.some(
    (element: ThemeElementReadResponse): boolean => element.content_kind === "image",
  );

  return hasImageElement;
}

/**
 * Text elements in the same order the frame draws them.
 *
 * @param elements - Elements on the source's theme
 * @returns Text elements, band then sort order
 */
export function orderedTextElements(
  elements: readonly ThemeElementReadResponse[],
): ThemeElementReadResponse[] {

  const textElements: ThemeElementReadResponse[] = elements.filter(
    (element: ThemeElementReadResponse): boolean => element.content_kind === "text",
  );
  const orderedElements: ThemeElementReadResponse[] = [...textElements].sort(
    (left: ThemeElementReadResponse, right: ThemeElementReadResponse): number => {
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
 * @param textElements - Every text element on the theme, in frame order
 * @returns The label shown beside the input
 */
export function labelForTextElement(
  element: ThemeElementReadResponse,
  textElements: readonly ThemeElementReadResponse[],
): string {

  const elementName: string = displayName(element);
  const sameNameCount: number = textElements.filter(
    (otherElement: ThemeElementReadResponse): boolean => (
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

function displayName(element: ThemeElementReadResponse): string {

  const trimmedName: string = element.name.trim();

  if (trimmedName === "") {
    return "Text";
  }

  return trimmedName;
}

/**
 * One stored string per text element. Missing rows stay blank.
 *
 * @param theme - The source's theme
 * @param unit - The unit being edited, or null for a new unit
 * @returns Element id to the current value
 */
export function textDraftsForTheme(
  theme: ThemeReadResponse,
  unit: UnitReadResponse | null,
): Record<string, string> {

  const shownTexts: UnitElementTextReadResponse[] = unit === null
    ? []
    : unit.text_status === "draft"
      ? unit.draft_texts
      : unit.texts;
  const storedValues: Map<string, string> = new Map(
    shownTexts.map((elementText): [string, string] => [
      elementText.theme_element_id,
      elementText.value,
    ]),
  );
  const drafts: Record<string, string> = {};

  for (const element of orderedTextElements(theme.elements)) {
    drafts[element.id] = storedValues.get(element.id) ?? "";
  }

  return drafts;
}
