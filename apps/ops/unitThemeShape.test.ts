import assert from "node:assert/strict";

import type { ThemeElementReadResponse, ThemeReadResponse } from "./src/api/types.ts";
import {
  labelForTextElement,
  orderedTextElements,
  textDraftsForTheme,
  themeRequiresImage,
} from "./src/pages/unitThemeShape.ts";

const titleElement: ThemeElementReadResponse = {
  id: "title-bottom",
  theme_id: "theme-1",
  band: "bottom",
  sort_order: 0,
  content_kind: "text",
  name: "Title",
  rectangle_color: null,
  rectangle_opacity: 100,
  rectangle_radius: 0,
  text_source: "title",
  font_family: "DejaVu Sans",
  font_size: 64,
  font_color: "#112233",
  bold: false,
  italic: false,
  underline: false,
  strikethrough: false,
  font_weight: null,
  alignment: "left",
  image_asset_ref: null,
  created_at: "2026-10-15T00:00:00Z",
  updated_at: "2026-10-15T00:00:00Z",
};

const headingElement: ThemeElementReadResponse = {
  ...titleElement,
  id: "heading-top",
  band: "top",
  name: "Interest heading",
  text_source: "interest_heading",
};

const secondTitle: ThemeElementReadResponse = {
  ...titleElement,
  id: "title-middle",
  band: "middle",
  sort_order: 1,
};

const imageElement: ThemeElementReadResponse = {
  ...titleElement,
  id: "image-middle",
  band: "middle",
  content_kind: "image",
  name: "Image",
  text_source: null,
  image_asset_ref: "theme-defaults/ocean-waves.jpg",
};

function themeWith(
  backgroundKind: ThemeReadResponse["background_kind"],
  elements: ThemeElementReadResponse[],
): ThemeReadResponse {

  const theme: ThemeReadResponse = {
    id: "theme-1",
    name: "Harbor",
    slug: "harbor",
    advertisement_type: "carousel",
    template_key: null,
    status: "draft",
    page_margin: 96,
    element_gap: 0,
    element_margin: 0,
    background_kind: backgroundKind,
    background_color: "#F6F1E8",
    background_gradient: null,
    background_asset_ref: null,
    elements,
    created_at: "2026-10-15T00:00:00Z",
    updated_at: "2026-10-15T00:00:00Z",
    created_by: null,
  };

  return theme;
}

assert.equal(themeRequiresImage(themeWith("color", [titleElement])), false);
assert.equal(themeRequiresImage(themeWith("picture", [titleElement])), true);
assert.equal(themeRequiresImage(themeWith("color", [titleElement, imageElement])), true);

const orderedIds: string[] = orderedTextElements([
  titleElement,
  imageElement,
  headingElement,
]).map((element: ThemeElementReadResponse): string => element.id);
assert.deepEqual(orderedIds, ["heading-top", "title-bottom"]);

const textElements: ThemeElementReadResponse[] = [headingElement, titleElement, secondTitle];
assert.equal(labelForTextElement(headingElement, textElements), "Interest heading");
assert.equal(labelForTextElement(titleElement, textElements), "Title (Bottom, 0)");
assert.equal(labelForTextElement(secondTitle, textElements), "Title (Middle, 1)");

const subjectElement: ThemeElementReadResponse = {
  ...titleElement,
  id: "subject-top",
  name: "Subject",
};
assert.equal(labelForTextElement(subjectElement, [subjectElement]), "Subject");

const drafts: Record<string, string> = textDraftsForTheme(
  themeWith("color", [titleElement, headingElement]),
  {
    id: "unit-1",
    position: 0,
    name: "Harbor",
    text_status: "live",
    texts: [{ theme_element_id: "title-bottom", value: "Fog" }],
    draft_texts: [],
    excluded_unit_ids: [],
    images: [],
  },
);
assert.equal(drafts["heading-top"], "");
assert.equal(drafts["title-bottom"], "Fog");

const draftValues: Record<string, string> = textDraftsForTheme(
  themeWith("color", [titleElement]),
  {
    id: "unit-1",
    position: 0,
    name: "Harbor",
    text_status: "draft",
    texts: [{ theme_element_id: "title-bottom", value: "Fog" }],
    draft_texts: [{ theme_element_id: "title-bottom", value: "Draft fog" }],
    excluded_unit_ids: [],
    images: [],
  },
);
assert.equal(draftValues["title-bottom"], "Draft fog");
