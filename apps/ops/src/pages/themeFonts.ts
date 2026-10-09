export interface ThemeFontFamily {
  family_id: string;
  name: string;
  category: string;
}

export interface FontCategory {
  id: string;
  label: string;
}

export const DEFAULT_FONT_FAMILY: string = "Source Sans 3";

export const UNKNOWN_FONT_FAMILY_NOTE: string =
  "This family isn't bundled. The preview uses the fallback face.";

export const FONT_CATEGORIES: FontCategory[] = [
  { id: "sans", label: "Sans" },
  { id: "serif", label: "Serif" },
  { id: "display", label: "Display" },
  { id: "mono", label: "Mono" },
  { id: "handwritten", label: "Handwritten" },
];

/**
 * Keep families whose name or category contains the query.
 *
 * @param families - Catalog from the font-families API
 * @param query - Operator search text. Blank returns the full list
 * @returns Families in the original order
 */
export function filterFontFamilies(
  families: ThemeFontFamily[],
  query: string,
): ThemeFontFamily[] {

  const needle: string = query.trim().toLowerCase();

  if (needle === "") {
    return families;
  }

  const matches: ThemeFontFamily[] = families.filter(
    (family: ThemeFontFamily): boolean => {
      const nameMatches: boolean = family.name.toLowerCase().includes(needle);
      const categoryMatches: boolean = family.category.toLowerCase().includes(needle);

      return nameMatches || categoryMatches;
    },
  );

  return matches;
}

/**
 * True when the stored name is one of the bundled families.
 *
 * @param families - Catalog from the font-families API
 * @param fontFamily - Stored family, including names from older themes
 * @returns Whether the dropdown can select this name without a fallback note
 */
export function fontFamilyIsBundled(
  families: ThemeFontFamily[],
  fontFamily: string,
): boolean {

  const trimmedFamily: string = fontFamily.trim();
  const isBundled: boolean = families.some(
    (family: ThemeFontFamily): boolean => family.name === trimmedFamily,
  );

  return isBundled;
}
