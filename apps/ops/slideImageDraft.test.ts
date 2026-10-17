import assert from "node:assert/strict";

import {
  SLIDE_IMAGE_NOTE_ERROR,
  SLIDE_IMAGE_SOURCE_ERROR,
  SLIDE_IMAGE_TYPE_ERROR,
  SLIDE_IMAGE_URL_ERROR,
  SLIDE_IMAGE_URL_SCHEME_ERROR,
  firstSlideImageDraftError,
  slideImageDraftError,
} from "./src/pages/slideImageDraft.ts";

const pngDraft = {
  kind: "file" as const,
  fileName: "lamp.PNG",
  url: "",
  imageSource: "Desk photo",
  imageLicense: "owned" as const,
  licenseNote: "",
};

assert.equal(slideImageDraftError(pngDraft), null);
assert.equal(
  slideImageDraftError({ ...pngDraft, fileName: "lamp.gif" }),
  SLIDE_IMAGE_TYPE_ERROR,
);
assert.equal(
  slideImageDraftError({ ...pngDraft, fileName: null }),
  SLIDE_IMAGE_TYPE_ERROR,
);
assert.equal(
  slideImageDraftError({ ...pngDraft, fileName: "scan.jpeg", imageSource: "  " }),
  SLIDE_IMAGE_SOURCE_ERROR,
);
assert.equal(
  slideImageDraftError({
    ...pngDraft,
    imageLicense: "licensed",
    licenseNote: "  ",
  }),
  SLIDE_IMAGE_NOTE_ERROR,
);
assert.equal(
  slideImageDraftError({
    ...pngDraft,
    imageLicense: "licensed",
    licenseNote: "Invoice 12",
  }),
  null,
);

assert.equal(
  slideImageDraftError({
    kind: "url",
    fileName: null,
    url: "  ",
    imageSource: "https://example.com/plate.png",
    imageLicense: "cc0",
    licenseNote: "",
  }),
  SLIDE_IMAGE_URL_ERROR,
);
assert.equal(
  slideImageDraftError({
    kind: "url",
    fileName: null,
    url: "ftp://example.com/plate.png",
    imageSource: "ftp://example.com/plate.png",
    imageLicense: "cc0",
    licenseNote: "",
  }),
  SLIDE_IMAGE_URL_SCHEME_ERROR,
);
assert.equal(
  slideImageDraftError({
    kind: "url",
    fileName: null,
    url: "https://example.com/plate.png",
    imageSource: "https://example.com/plate.png",
    imageLicense: "cc0",
    licenseNote: "",
  }),
  null,
);

assert.equal(
  firstSlideImageDraftError([
    pngDraft,
    { ...pngDraft, fileName: "second.jpg", imageSource: "" },
  ]),
  SLIDE_IMAGE_SOURCE_ERROR,
);
assert.equal(firstSlideImageDraftError([pngDraft]), null);
