import assert from "node:assert/strict";

import {
  UNIT_IMAGE_NOTE_ERROR,
  UNIT_IMAGE_SOURCE_ERROR,
  UNIT_IMAGE_TYPE_ERROR,
  UNIT_IMAGE_URL_ERROR,
  UNIT_IMAGE_URL_SCHEME_ERROR,
  firstUnitImageDraftError,
  unitImageDraftError,
} from "./src/pages/unitImageDraft.ts";

const pngDraft = {
  kind: "file" as const,
  fileName: "lamp.PNG",
  url: "",
  imageSource: "Desk photo",
  imageLicense: "owned" as const,
  licenseNote: "",
};

assert.equal(unitImageDraftError(pngDraft), null);
assert.equal(
  unitImageDraftError({ ...pngDraft, fileName: "lamp.gif" }),
  UNIT_IMAGE_TYPE_ERROR,
);
assert.equal(
  unitImageDraftError({ ...pngDraft, fileName: null }),
  UNIT_IMAGE_TYPE_ERROR,
);
assert.equal(
  unitImageDraftError({ ...pngDraft, fileName: "scan.jpeg", imageSource: "  " }),
  UNIT_IMAGE_SOURCE_ERROR,
);
assert.equal(
  unitImageDraftError({
    ...pngDraft,
    imageLicense: "licensed",
    licenseNote: "  ",
  }),
  UNIT_IMAGE_NOTE_ERROR,
);
assert.equal(
  unitImageDraftError({
    ...pngDraft,
    imageLicense: "licensed",
    licenseNote: "Invoice 12",
  }),
  null,
);

assert.equal(
  unitImageDraftError({
    kind: "url",
    fileName: null,
    url: "  ",
    imageSource: "https://example.com/plate.png",
    imageLicense: "cc0",
    licenseNote: "",
  }),
  UNIT_IMAGE_URL_ERROR,
);
assert.equal(
  unitImageDraftError({
    kind: "url",
    fileName: null,
    url: "ftp://example.com/plate.png",
    imageSource: "ftp://example.com/plate.png",
    imageLicense: "cc0",
    licenseNote: "",
  }),
  UNIT_IMAGE_URL_SCHEME_ERROR,
);
assert.equal(
  unitImageDraftError({
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
  firstUnitImageDraftError([
    pngDraft,
    { ...pngDraft, fileName: "second.jpg", imageSource: "" },
  ]),
  UNIT_IMAGE_SOURCE_ERROR,
);
assert.equal(firstUnitImageDraftError([pngDraft]), null);
