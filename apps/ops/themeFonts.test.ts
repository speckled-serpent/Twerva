import assert from "node:assert/strict";

import {
  DEFAULT_FONT_FAMILY,
  filterFontFamilies,
  fontFamilyIsBundled,
  type ThemeFontFamily,
} from "./src/pages/themeFonts.ts";

const families: ThemeFontFamily[] = [
  { family_id: "source-sans-3", name: "Source Sans 3", category: "sans" },
  { family_id: "playfair-display", name: "Playfair Display", category: "display" },
  { family_id: "pacifico", name: "Pacifico", category: "handwritten" },
];

assert.equal(DEFAULT_FONT_FAMILY, "Source Sans 3");
assert.equal(filterFontFamilies(families, "").length, 3);
assert.deepEqual(
  filterFontFamilies(families, "play").map((family: ThemeFontFamily): string => family.name),
  ["Playfair Display"],
);
assert.deepEqual(
  filterFontFamilies(families, "HAND").map((family: ThemeFontFamily): string => family.name),
  ["Pacifico"],
);
assert.equal(fontFamilyIsBundled(families, "Source Sans 3"), true);
assert.equal(fontFamilyIsBundled(families, "DejaVu Sans"), false);
