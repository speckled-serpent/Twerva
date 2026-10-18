import assert from "node:assert/strict";

import {
  albumImageFilePath,
  albumImageImportPath,
  albumImageItemPath,
  albumImagesPath,
  albumImageThumbnailPath,
} from "./src/api/albumImagePaths.ts";
import type {
  AlbumImageReadResponse,
  AlbumPatchRequest,
  AlbumReadResponse,
  SlideImageLicense,
} from "./src/api/types.ts";
import {
  ALBUM_NAME_ERROR,
  albumDraftFingerprint,
  albumDraftReadiness,
  albumImageFileIntakeError,
  albumImageLicensePatch,
  albumImageUrlIntakeError,
  draftFromAlbum,
  moveAlbumImage,
  patchFromDraft,
  slideImageLicenseFromSelect,
  withAlbumImagePatch,
  type AlbumDraft,
  type AlbumImageDraft,
} from "./src/pages/albumImages.ts";
import {
  SKELETON_AUTOSAVE_DELAY_MS,
  createSkeletonAutosaveController,
  formatSkeletonAutosaveError,
  type AutosaveReadiness,
  type SkeletonAutosaveController,
} from "./src/pages/skeletonAutosave.ts";
import {
  SLIDE_IMAGE_NOTE_ERROR,
  SLIDE_IMAGE_SOURCE_ERROR,
  SLIDE_IMAGE_TYPE_ERROR,
  SLIDE_IMAGE_URL_ERROR,
  SLIDE_IMAGE_URL_SCHEME_ERROR,
} from "./src/pages/slideImageDraft.ts";

assert.equal(SKELETON_AUTOSAVE_DELAY_MS, 700);
assert.equal(albumImagesPath("album-1"), "/api/v1/albums/album-1/images");
assert.equal(albumImageImportPath("album-1"), "/api/v1/albums/album-1/images/import");
assert.equal(albumImageItemPath("album-1", "img-a"), "/api/v1/albums/album-1/images/img-a");
assert.equal(albumImageFilePath("album-1", "img-a"), "/api/v1/albums/album-1/images/img-a/file");
assert.equal(
  albumImageThumbnailPath("album-1", "img-a"),
  "/api/v1/albums/album-1/images/img-a/thumbnail",
);
assert.equal(slideImageLicenseFromSelect("licensed"), "licensed");
assert.equal(slideImageLicenseFromSelect("nope"), null);

const stored: AlbumReadResponse = albumWithImages([
  imageRow("img-b", 1, "owned", "Studio", "ignored when not licensed"),
  imageRow("img-a", 0, "cc0", "Author", ""),
]);
const draft: AlbumDraft = draftFromAlbum(stored);
const firstImage: AlbumImageDraft = requiredImage(draft, 0);
const secondImage: AlbumImageDraft = requiredImage(draft, 1);
assert.deepEqual(draft.images.map(imageId), ["img-a", "img-b"]);
assert.equal(secondImage.licenseNote, "");
assert.equal(draft.name, "Harbor");

const licensedImages: AlbumImageDraft[] = withAlbumImagePatch(
  draft.images,
  firstImage.id,
  albumImageLicensePatch(firstImage, "licensed"),
);
const licensedDraft: AlbumDraft = { name: draft.name, images: licensedImages };
const licensedReadiness: AutosaveReadiness = albumDraftReadiness(licensedDraft);
assert.equal(licensedReadiness.kind, "invalid");

if (licensedReadiness.kind === "invalid") {
  assert.equal(licensedReadiness.message, SLIDE_IMAGE_NOTE_ERROR);
}

const notedImages: AlbumImageDraft[] = withAlbumImagePatch(licensedImages, firstImage.id, {
  licenseNote: "Grant 2026",
});
const notedDraft: AlbumDraft = { name: draft.name, images: notedImages };
assert.deepEqual(albumDraftReadiness(notedDraft), { kind: "ready" });
assert.notEqual(albumDraftFingerprint(draft), albumDraftFingerprint(notedDraft));
const notedPatch: AlbumPatchRequest = patchFromDraft(notedDraft);
assert.equal(notedPatch.images[0]?.license, "licensed");
assert.equal(notedPatch.images[0]?.license_note, "Grant 2026");

const notedFirst: AlbumImageDraft = requiredImage(notedDraft, 0);
const clearedImages: AlbumImageDraft[] = withAlbumImagePatch(
  notedImages,
  notedFirst.id,
  albumImageLicensePatch(notedFirst, "owned"),
);
const clearedDraft: AlbumDraft = { name: draft.name, images: clearedImages };
assert.equal(requiredImage(clearedDraft, 0).license, "owned");
assert.equal(requiredImage(clearedDraft, 0).licenseNote, "");
assert.equal(patchFromDraft(clearedDraft).images[0]?.license_note, "");

const moved: AlbumImageDraft[] | null = moveAlbumImage(draft.images, 0, 1);
assert.ok(moved !== null);

if (moved !== null) {
  assert.deepEqual(patchFromDraft({ name: draft.name, images: moved }).images.map(imageId), [
    "img-b",
    "img-a",
  ]);
}

assert.equal(moveAlbumImage(draft.images, 0, -1), null);
const blankName: AutosaveReadiness = albumDraftReadiness({ name: "  ", images: draft.images });
assert.equal(blankName.kind, "invalid");

if (blankName.kind === "invalid") {
  assert.equal(blankName.message, ALBUM_NAME_ERROR);
}

const blankSource: AlbumImageDraft[] = withAlbumImagePatch(draft.images, firstImage.id, {
  source: " ",
});
assert.equal(albumDraftReadiness({ name: draft.name, images: blankSource }).kind, "invalid");
assert.equal(albumImageFileIntakeError("lamp.gif", "Author", "cc0", ""), SLIDE_IMAGE_TYPE_ERROR);
assert.equal(albumImageFileIntakeError("lamp.png", " ", "cc0", ""), SLIDE_IMAGE_SOURCE_ERROR);
assert.equal(
  albumImageFileIntakeError("lamp.png", "Author", "licensed", ""),
  SLIDE_IMAGE_NOTE_ERROR,
);
assert.equal(albumImageFileIntakeError("lamp.png", "Author", "cc0", ""), null);
assert.equal(albumImageUrlIntakeError("", "Author", "cc0", ""), SLIDE_IMAGE_URL_ERROR);
assert.equal(
  albumImageUrlIntakeError("ftp://images.example/lamp.jpg", "Author", "cc0", ""),
  SLIDE_IMAGE_URL_SCHEME_ERROR,
);

let pending: (() => void | Promise<void>) | null = null;
const savedBodies: AlbumDraft[] = [];
const delays: number[] = [];
const controller: SkeletonAutosaveController<AlbumDraft> = createSkeletonAutosaveController({
  delayMs: SKELETON_AUTOSAVE_DELAY_MS,
  readiness: albumDraftReadiness,
  fingerprint: albumDraftFingerprint,
  save: async (value: AlbumDraft): Promise<void> => {
    savedBodies.push(value);
  },
  formatError: formatSkeletonAutosaveError,
  scheduleTimer: (callback: () => void | Promise<void>, delayMs: number): (() => void) => {
    delays.push(delayMs);
    pending = callback;

    return (): void => {
      pending = null;
    };
  },
});
controller.noteSaved(draft);
controller.schedule(licensedDraft);
assert.equal(savedBodies.length, 0);
assert.equal(delays.length, 0);
assert.equal(controller.getState().message, SLIDE_IMAGE_NOTE_ERROR);

controller.schedule(notedDraft);
assert.equal(savedBodies.length, 0);
assert.deepEqual(delays, [700]);
assert.equal(controller.getState().phase, "pending");

if (pending === null) {
  throw new Error("License edit did not schedule a save.");
}

await pending();
assert.equal(savedBodies.length, 1);
assert.equal(savedBodies[0]?.images[0]?.license, "licensed");
assert.equal(controller.getState().phase, "saved");
assert.equal(controller.getState().message, "Saved");

const afterUpload: AlbumReadResponse = albumWithImages([
  ...stored.images,
  imageRow("img-c", 2, "cc0", "Author", ""),
]);
const firstCarouselImages: string[] = draftFromAlbum(afterUpload).images.map(imageId);
const secondCarouselImages: string[] = draftFromAlbum(afterUpload).images.map(imageId);
assert.deepEqual(firstCarouselImages, ["img-a", "img-b", "img-c"]);
assert.deepEqual(secondCarouselImages, firstCarouselImages);

function imageId(image: { id: string }): string {

  return image.id;
}

function requiredImage(value: AlbumDraft, index: number): AlbumImageDraft {

  const image: AlbumImageDraft | undefined = value.images[index];

  if (image === undefined) {
    throw new Error(`Missing image at ${index}.`);
  }

  return image;
}

function albumWithImages(images: AlbumImageReadResponse[]): AlbumReadResponse {

  return {
    id: "album-1",
    name: "Harbor",
    slug: "harbor",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    images,
  };
}

function imageRow(
  id: string,
  position: number,
  license: SlideImageLicense,
  source: string,
  licenseNote: string,
): AlbumImageReadResponse {

  return {
    id,
    position,
    relative_path: `${id}.jpg`,
    media_type: "jpeg",
    byte_size: 12,
    width: 10,
    height: 10,
    alt_text: "",
    license,
    source,
    license_note: licenseNote,
    intake: "upload",
    thumbnail_path: null,
  };
}
