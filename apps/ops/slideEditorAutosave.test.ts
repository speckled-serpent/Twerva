import assert from "node:assert/strict";

import type { SlideWriteRequest } from "./src/api/types.ts";
import { CAROUSEL_LABEL_ERROR } from "./src/pages/carouselLabel.ts";
import { SLIDE_IMAGE_REQUIRED_COPY } from "./src/pages/slideAlbumImage.ts";
import {
  NEW_PICTURE_SLIDE_AUTOSAVE_HINT,
  NEW_SLIDE_AUTOSAVE_HINT,
  SLIDE_AUTOSAVE_HINT,
  SLIDE_NAME_REQUIRED_ERROR,
  slideAutosaveWriteRequest,
  slideEditorFingerprint,
  slideEditorReadiness,
  slideImageChoiceWriteRequest,
  type SlideFieldDraft,
} from "./src/pages/slideEditorAutosave.ts";
import {
  SKELETON_AUTOSAVE_DELAY_MS,
  createSkeletonAutosaveController,
  type SkeletonAutosaveController,
} from "./src/pages/skeletonAutosave.ts";

assert.equal(SKELETON_AUTOSAVE_DELAY_MS, 700);
assert.equal(SLIDE_NAME_REQUIRED_ERROR, CAROUSEL_LABEL_ERROR);
assert.equal(SLIDE_NAME_REQUIRED_ERROR, "Name is required.");
assert.match(SLIDE_AUTOSAVE_HINT, /save on their own/);
assert.match(NEW_SLIDE_AUTOSAVE_HINT, /Nothing is saved before that/);
assert.match(NEW_PICTURE_SLIDE_AUTOSAVE_HINT, /image is chosen/);

const text = (value: string): SlideFieldDraft["texts"] => [
  { skeleton_element_id: "title-bottom", value },
];

function draft(overrides: Partial<SlideFieldDraft> = {}): SlideFieldDraft {

  const fieldDraft: SlideFieldDraft = {
    slideId: "slide-1",
    needsImage: true,
    skeletonReady: true,
    name: "Lamp",
    texts: text("Warm light"),
    excludedSlideIds: ["other-slide"],
    albumImageId: "shared",
    ...overrides,
  };

  return fieldDraft;
}

const blankExisting = slideEditorReadiness(draft({ name: "   " }));
assert.equal(blankExisting.kind, "invalid");

if (blankExisting.kind === "invalid") {
  assert.equal(blankExisting.message, SLIDE_NAME_REQUIRED_ERROR);
}

assert.equal(slideEditorReadiness(draft({ skeletonReady: false, name: "" })).kind, "skip");
assert.equal(
  slideEditorReadiness(draft({
    slideId: null,
    name: "",
    texts: text(""),
    excludedSlideIds: [],
    albumImageId: null,
    needsImage: false,
  })).kind,
  "skip",
);
assert.equal(
  slideEditorReadiness(draft({
    slideId: null,
    name: "",
    texts: text("Started"),
    excludedSlideIds: [],
    albumImageId: null,
    needsImage: false,
  })).kind,
  "invalid",
);

const missingImage = slideEditorReadiness(draft({
  slideId: null,
  needsImage: true,
  albumImageId: null,
  excludedSlideIds: [],
}));
assert.equal(missingImage.kind, "invalid");

if (missingImage.kind === "invalid") {
  assert.equal(missingImage.message, SLIDE_IMAGE_REQUIRED_COPY);
}

assert.equal(
  slideEditorReadiness(draft({ slideId: null, needsImage: true, albumImageId: "shared" })).kind,
  "ready",
);
assert.equal(
  slideEditorReadiness(draft({
    slideId: null,
    needsImage: false,
    albumImageId: null,
    excludedSlideIds: [],
  })).kind,
  "ready",
);
assert.equal(slideEditorReadiness(draft()).kind, "ready");
assert.equal(
  slideEditorReadiness(draft({ needsImage: true, albumImageId: null })).kind,
  "invalid",
);

const imageBeforeName = slideEditorReadiness(draft({
  slideId: null,
  name: "",
  texts: text(""),
  excludedSlideIds: [],
  albumImageId: "shared",
}));
assert.equal(imageBeforeName.kind, "invalid");

if (imageBeforeName.kind === "invalid") {
  assert.equal(imageBeforeName.message, SLIDE_NAME_REQUIRED_ERROR);
}

assert.equal(
  slideEditorFingerprint(draft({ name: " Harbor " })),
  slideEditorFingerprint(draft({ name: "Harbor" })),
);
assert.notEqual(
  slideEditorFingerprint(draft({ texts: text("Warm light") })),
  slideEditorFingerprint(draft({ texts: text("Edited") })),
);
assert.equal(
  slideEditorFingerprint(draft({ excludedSlideIds: ["b", "a"] })),
  slideEditorFingerprint(draft({ excludedSlideIds: ["a", "b"] })),
);
assert.notEqual(
  slideEditorFingerprint(draft({ excludedSlideIds: ["a"] })),
  slideEditorFingerprint(draft({ excludedSlideIds: ["a", "b"] })),
);
assert.equal(
  slideEditorFingerprint(draft({ albumImageId: "shared" })),
  slideEditorFingerprint(draft({ albumImageId: "other" })),
);
assert.equal(
  slideEditorFingerprint(draft({ slideId: null, albumImageId: "shared" })),
  slideEditorFingerprint(draft({ slideId: "slide-1", albumImageId: "other" })),
);

const existingSave: SlideWriteRequest = slideAutosaveWriteRequest(draft({
  name: " Harbor ",
  texts: text("Edited in the form"),
  albumImageId: "shared",
}));

assert.equal(existingSave.name, "Harbor");
assert.deepEqual(existingSave.texts, text("Edited in the form"));
assert.deepEqual(existingSave.excluded_slide_ids, ["other-slide"]);
assert.equal(Object.hasOwn(existingSave, "album_image_id"), false);

const createdPicture: SlideWriteRequest = slideAutosaveWriteRequest(draft({
  slideId: null,
  name: "Lamp",
  texts: text("Warm light"),
  excludedSlideIds: [],
  albumImageId: "shared",
}));

assert.equal(createdPicture.album_image_id, "shared");
assert.equal(Object.hasOwn(createdPicture, "file"), false);
assert.equal(Object.hasOwn(createdPicture, "url"), false);

const createdColor: SlideWriteRequest = slideAutosaveWriteRequest(draft({
  slideId: null,
  needsImage: false,
  albumImageId: "shared",
  excludedSlideIds: [],
}));

assert.equal(Object.hasOwn(createdColor, "album_image_id"), false);

const imageChoice: SlideWriteRequest = slideImageChoiceWriteRequest(
  draft({ name: "Harbor", texts: text("Edited in the form") }),
  "first",
);

assert.equal(imageChoice.album_image_id, "first");
assert.equal(imageChoice.name, "Harbor");
assert.deepEqual(imageChoice.texts, text("Edited in the form"));
assert.equal(imageChoice.album_image_id === "shared", false);

interface ManualTimer {
  delayMs: number;
  callback: () => void | Promise<void>;
  cancelled: boolean;
}

function manualClock(): {
  scheduleTimer: (callback: () => void | Promise<void>, delayMs: number) => () => void;
  fireNext: () => Promise<void>;
  pendingCount: () => number;
  delays: () => number[];
} {

  const queue: ManualTimer[] = [];
  const clock = {
    scheduleTimer: (
      callback: () => void | Promise<void>,
      delayMs: number,
    ): (() => void) => {
      const timer: ManualTimer = {
        delayMs,
        callback,
        cancelled: false,
      };
      queue.push(timer);

      return (): void => {
        timer.cancelled = true;
      };
    },
    fireNext: async (): Promise<void> => {

      while (queue.length > 0) {
        const timer: ManualTimer | undefined = queue.shift();

        if (timer === undefined || timer.cancelled) {
          continue;
        }

        await timer.callback();

        return;
      }
    },
    pendingCount: (): number => {
      return queue.filter((timer: ManualTimer): boolean => !timer.cancelled).length;
    },
    delays: (): number[] => {
      return queue
        .filter((timer: ManualTimer): boolean => !timer.cancelled)
        .map((timer: ManualTimer): number => timer.delayMs);
    },
  };

  return clock;
}

function controller(
  save: (value: SlideFieldDraft) => Promise<void>,
  clock: ReturnType<typeof manualClock>,
): SkeletonAutosaveController<SlideFieldDraft> {

  return createSkeletonAutosaveController<SlideFieldDraft>({
    delayMs: SKELETON_AUTOSAVE_DELAY_MS,
    readiness: slideEditorReadiness,
    fingerprint: slideEditorFingerprint,
    save,
    formatError: (error: unknown): string => {
      return error instanceof Error ? error.message : String(error);
    },
    scheduleTimer: clock.scheduleTimer,
  });
}

async function testTextEditSavesAfterTheDelayWithoutTheImage(): Promise<void> {

  const clock = manualClock();
  const saved: SlideWriteRequest[] = [];
  const saver: SkeletonAutosaveController<SlideFieldDraft> = controller(
    async (value: SlideFieldDraft): Promise<void> => {
      saved.push(slideAutosaveWriteRequest(value));
    },
    clock,
  );
  const stored: SlideFieldDraft = draft();

  saver.noteSaved(stored);
  saver.schedule(stored);
  assert.equal(clock.pendingCount(), 0);
  saver.schedule(draft({ texts: text("a") }));
  saver.schedule(draft({ texts: text("ab") }));
  assert.deepEqual(clock.delays(), [700]);
  await clock.fireNext();
  assert.equal(saved.length, 1);
  assert.equal(saved[0]?.texts[0]?.value, "ab");
  assert.equal(Object.hasOwn(saved[0], "album_image_id"), false);
  assert.equal(saver.getState().phase, "saved");
  assert.equal(saver.getState().message, "Saved");
}

async function testBlankNameDoesNotSave(): Promise<void> {

  const clock = manualClock();
  const saved: SlideFieldDraft[] = [];
  const saver: SkeletonAutosaveController<SlideFieldDraft> = controller(
    async (value: SlideFieldDraft): Promise<void> => {
      saved.push(value);
    },
    clock,
  );

  saver.noteSaved(draft());
  saver.schedule(draft({ name: "   " }));
  assert.equal(clock.pendingCount(), 0);
  assert.equal(saved.length, 0);
  assert.equal(saver.getState().phase, "error");
  assert.equal(saver.getState().message, SLIDE_NAME_REQUIRED_ERROR);
  assert.equal(saver.getState().canRetry, false);
  assert.equal(saver.isDirty(), true);
}

async function testNewPictureSlideKeepsTheLatestImage(): Promise<void> {

  const clock = manualClock();
  const saved: SlideWriteRequest[] = [];
  const saver: SkeletonAutosaveController<SlideFieldDraft> = controller(
    async (value: SlideFieldDraft): Promise<void> => {
      saved.push(slideAutosaveWriteRequest(value));
    },
    clock,
  );
  const started: SlideFieldDraft = draft({
    slideId: null,
    excludedSlideIds: [],
    albumImageId: "img-a",
  });

  saver.schedule(started);
  saver.schedule({ ...started, albumImageId: "img-b" });
  assert.deepEqual(clock.delays(), [700]);
  await clock.fireNext();
  assert.equal(saved.length, 1);
  assert.equal(saved[0]?.album_image_id, "img-b");
  assert.equal(saved[0]?.name, "Lamp");
}

async function testUntouchedNewSlideDoesNotSave(): Promise<void> {

  const clock = manualClock();
  let calls: number = 0;
  const saver: SkeletonAutosaveController<SlideFieldDraft> = controller(
    async (): Promise<void> => {
      calls += 1;
    },
    clock,
  );

  saver.schedule(draft({
    slideId: null,
    needsImage: true,
    name: "",
    texts: text(""),
    excludedSlideIds: [],
    albumImageId: null,
  }));
  assert.equal(clock.pendingCount(), 0);
  assert.equal(calls, 0);
  assert.equal(saver.getState().phase, "idle");
  assert.equal(saver.isDirty(), false);
}

async function main(): Promise<void> {

  await testTextEditSavesAfterTheDelayWithoutTheImage();
  await testBlankNameDoesNotSave();
  await testNewPictureSlideKeepsTheLatestImage();
  await testUntouchedNewSlideDoesNotSave();
}

main().catch((error: unknown): void => {
  console.error(error);
  process.exit(1);
});
