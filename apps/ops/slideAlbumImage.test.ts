import assert from "node:assert/strict";

import type {
  AlbumImageReadResponse,
  SkeletonElementReadResponse,
  SkeletonReadResponse,
  SlideReadResponse,
  SlideWriteRequest,
} from "./src/api/types.ts";
import {
  SLIDE_ALBUM_EMPTY_COPY,
  SLIDE_ALBUM_MISSING_COPY,
  SLIDE_IMAGE_REQUIRED_COPY,
  albumImagesInPositionOrder,
  imageChoiceWriteRequest,
  newPictureSlideWriteRequest,
  savedSlideAlbumImageId,
  slideImageRequiredError,
  slideTextSaveRequest,
} from "./src/pages/slideAlbumImage.ts";

const titleElement: SkeletonElementReadResponse = {
  id: "title-bottom",
  skeleton_id: "skeleton-1",
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

const pictureSkeleton: SkeletonReadResponse = {
  id: "skeleton-1",
  name: "Harbor",
  slug: "harbor",
  advertisement_type: "carousel",
  template_key: null,
  status: "draft",
  page_margin: 96,
  element_gap: 0,
  element_margin: 0,
  background_kind: "picture",
  background_color: null,
  background_gradient: null,
  background_asset_ref: "theme-defaults/ocean-waves.jpg",
  elements: [titleElement],
  created_at: "2026-10-15T00:00:00Z",
  updated_at: "2026-10-15T00:00:00Z",
  created_by: null,
};

assert.match(SLIDE_ALBUM_EMPTY_COPY, /This album has no images yet/);
assert.match(SLIDE_ALBUM_EMPTY_COPY, /Content/);
assert.match(SLIDE_ALBUM_MISSING_COPY, /No album is attached/);
assert.match(SLIDE_ALBUM_MISSING_COPY, /Content/);
assert.equal(SLIDE_IMAGE_REQUIRED_COPY, "This skeleton needs an image on the slide.");

assert.equal(slideImageRequiredError(false, null), null);
assert.equal(slideImageRequiredError(true, "lamp"), null);
assert.equal(slideImageRequiredError(true, null), SLIDE_IMAGE_REQUIRED_COPY);

const later: AlbumImageReadResponse = albumImage("later", 2);
const first: AlbumImageReadResponse = albumImage("first", 0);
const shared: AlbumImageReadResponse = albumImage("shared", 1);
const orderedIds: string[] = albumImagesInPositionOrder([later, shared, first]).map(
  (image: AlbumImageReadResponse): string => image.id,
);

assert.deepEqual(orderedIds, ["first", "shared", "later"]);
assert.equal(
  albumImagesInPositionOrder([shared, shared]).length,
  2,
);

const textSave: SlideWriteRequest = slideTextSaveRequest(
  "Lamp",
  [{ skeleton_element_id: "title-bottom", value: "Edited in the form" }],
  ["other-slide"],
);

assert.equal(Object.hasOwn(textSave, "album_image_id"), false);
assert.equal(textSave.name, "Lamp");

const created: SlideWriteRequest = newPictureSlideWriteRequest(
  "Lamp",
  [{ skeleton_element_id: "title-bottom", value: "Warm light" }],
  [],
  "shared",
);

assert.equal(created.album_image_id, "shared");
assert.equal(Object.hasOwn(created, "images"), false);
assert.equal(Object.hasOwn(created, "file"), false);
assert.equal(Object.hasOwn(created, "url"), false);

const liveSlide: SlideReadResponse = slideWith("live", "Stored title", "Warm light", "shared");
const choice: SlideWriteRequest = imageChoiceWriteRequest(liveSlide, pictureSkeleton, "first");

assert.equal(choice.album_image_id, "first");
assert.equal(choice.name, "Stored title");
assert.deepEqual(choice.texts, [
  { skeleton_element_id: "title-bottom", value: "Warm light" },
]);
assert.deepEqual(choice.excluded_slide_ids, ["other-slide"]);
assert.equal(Object.hasOwn(choice, "images"), false);

const draftSlide: SlideReadResponse = slideWith("draft", "Stored title", "Live text", "shared");
draftSlide.draft_texts = [
  { skeleton_element_id: "title-bottom", value: "Draft text" },
];
const draftChoice: SlideWriteRequest = imageChoiceWriteRequest(
  draftSlide,
  pictureSkeleton,
  "later",
);

assert.equal(draftChoice.texts[0]?.value, "Draft text");
assert.equal(savedSlideAlbumImageId(null), null);
assert.equal(savedSlideAlbumImageId(liveSlide), "shared");
assert.equal(savedSlideAlbumImageId({ ...liveSlide, images: [] }), null);

function albumImage(id: string, position: number): AlbumImageReadResponse {

  const image: AlbumImageReadResponse = {
    id,
    position,
    relative_path: `albums/${id}.jpg`,
    media_type: "jpeg",
    byte_size: 1200,
    width: 1080,
    height: 1920,
    alt_text: id,
    license: "owned",
    source: "Desk",
    license_note: "",
    intake: "upload",
    thumbnail_path: null,
  };

  return image;
}

function slideWith(
  textStatus: SlideReadResponse["text_status"],
  name: string,
  textValue: string,
  albumImageId: string,
): SlideReadResponse {

  const slide: SlideReadResponse = {
    id: "slide-1",
    position: 0,
    name,
    text_status: textStatus,
    texts: [{ skeleton_element_id: "title-bottom", value: textValue }],
    draft_texts: [],
    excluded_slide_ids: ["other-slide"],
    images: [albumImage(albumImageId, 1)],
  };

  return slide;
}
