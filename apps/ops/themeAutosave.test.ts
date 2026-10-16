import assert from "node:assert/strict";

import type {
  ThemeElementCreateRequest,
  ThemeElementReadResponse,
  ThemeReadResponse,
} from "./src/api/types.ts";
import { emptyThemeFrameDraft } from "./src/pages/themeFrameDraft.ts";
import {
  combineAutosaveStates,
  createThemeAutosaveController,
  type AutosaveReadiness,
  type ThemeAutosaveController,
  type ThemeAutosaveState,
} from "./src/pages/themeAutosave.ts";
import {
  emptyNewThemePersistState,
  newThemeSnapshotReadiness,
  pairOrderedIds,
  persistNewThemeSnapshot,
  planThemeElementSync,
  type NewThemePersistClients,
  type NewThemePersistState,
  type StagedElementSync,
} from "./src/pages/themeElementSync.ts";

interface ManualTimer {
  delayMs: number;
  callback: () => void | Promise<void>;
  cancelled: boolean;
}

interface ManualClock {
  scheduleTimer: (callback: () => void | Promise<void>, delayMs: number) => () => void;
  fireNext: () => Promise<void>;
  pendingCount: () => number;
}

function manualClock(): ManualClock {

  const queue: ManualTimer[] = [];
  const clock: ManualClock = {
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
  };

  return clock;
}

function deferred(): {
  promise: Promise<void>;
  resolve: () => void;
  reject: (error: unknown) => void;
} {

  let resolvePromise: () => void = (): void => {
    return;
  };
  let rejectPromise: (error: unknown) => void = (): void => {
    return;
  };
  const promise: Promise<void> = new Promise((resolve: () => void, reject: (error: unknown) => void): void => {
    resolvePromise = resolve;
    rejectPromise = reject;
  });

  return {
    promise,
    resolve: resolvePromise,
    reject: rejectPromise,
  };
}

function readyController(
  save: (value: string) => Promise<void>,
  clock: ManualClock,
  readiness: (value: string) => AutosaveReadiness = (): AutosaveReadiness => ({ kind: "ready" }),
): ThemeAutosaveController<string> {

  return createThemeAutosaveController<string>({
    delayMs: 700,
    readiness,
    fingerprint: (value: string): string => value,
    save,
    formatError: (error: unknown): string => {
      return error instanceof Error ? error.message : String(error);
    },
    scheduleTimer: clock.scheduleTimer,
  });
}

async function testDebounceKeepsTheLatestValue(): Promise<void> {

  const clock: ManualClock = manualClock();
  const saved: string[] = [];
  const controller: ThemeAutosaveController<string> = readyController(
    async (value: string): Promise<void> => {
      saved.push(value);
    },
    clock,
  );

  controller.schedule("a");
  controller.schedule("ab");
  controller.schedule("abc");
  assert.equal(clock.pendingCount(), 1);
  await clock.fireNext();
  assert.deepEqual(saved, ["abc"]);
  assert.equal(controller.getState().phase, "saved");
  assert.equal(controller.getState().message, "Saved");
}

async function testInvalidValueDoesNotSaveOrRetry(): Promise<void> {

  const clock: ManualClock = manualClock();
  const saved: string[] = [];
  const controller: ThemeAutosaveController<string> = readyController(
    async (value: string): Promise<void> => {
      saved.push(value);
    },
    clock,
    (value: string): AutosaveReadiness => {

      if (value.includes("x")) {
        return { kind: "invalid", message: "Name is required." };
      }

      return { kind: "ready" };
    },
  );

  controller.schedule("x");
  controller.schedule("xx");
  assert.equal(clock.pendingCount(), 0);
  assert.equal(saved.length, 0);
  assert.equal(controller.getState().phase, "error");
  assert.equal(controller.getState().canRetry, false);
  assert.equal(controller.isDirty(), true);
  controller.schedule("ok");
  await clock.fireNext();
  assert.deepEqual(saved, ["ok"]);
}

async function testServerErrorDoesNotRepeatUntilRetry(): Promise<void> {

  const clock: ManualClock = manualClock();
  let attempts: number = 0;
  const controller: ThemeAutosaveController<string> = readyController(
    async (): Promise<void> => {
      attempts += 1;

      if (attempts === 1) {
        throw new Error("Theme could not be updated.");
      }
    },
    clock,
  );

  controller.schedule("paper");
  await clock.fireNext();
  assert.equal(attempts, 1);
  assert.equal(controller.getState().phase, "error");
  assert.equal(controller.getState().canRetry, true);
  assert.equal(controller.getState().message, "Theme could not be updated.");
  controller.schedule("paper");
  assert.equal(clock.pendingCount(), 0);
  assert.equal(attempts, 1);
  await controller.retry();
  assert.equal(attempts, 2);
  assert.equal(controller.getState().phase, "saved");
}

async function testInFlightSaveDoesNotOverwriteANewerEdit(): Promise<void> {

  const clock: ManualClock = manualClock();
  const saved: string[] = [];
  const gate: ReturnType<typeof deferred> = deferred();
  let calls: number = 0;
  let inFlight: number = 0;
  let maxInFlight: number = 0;
  const controller: ThemeAutosaveController<string> = readyController(
    async (value: string): Promise<void> => {
      calls += 1;
      inFlight += 1;
      maxInFlight = Math.max(maxInFlight, inFlight);

      if (calls === 1) {
        await gate.promise;
      }

      saved.push(value);
      inFlight -= 1;
    },
    clock,
  );

  controller.schedule("first");
  const firstFlush: Promise<void> = clock.fireNext();
  controller.schedule("second");
  assert.equal(controller.getState().phase, "pending");
  gate.resolve();
  await firstFlush;
  assert.deepEqual(saved, ["first", "second"]);
  assert.equal(maxInFlight, 1);
  assert.equal(controller.getState().phase, "saved");
  assert.equal(controller.isDirty(), false);
}

async function testNoteSavedSkipsTheBaseline(): Promise<void> {

  const clock: ManualClock = manualClock();
  const saved: string[] = [];
  const controller: ThemeAutosaveController<string> = readyController(
    async (value: string): Promise<void> => {
      saved.push(value);
    },
    clock,
  );

  controller.noteSaved("baseline");
  controller.schedule("baseline");
  assert.equal(clock.pendingCount(), 0);
  assert.equal(controller.getState().phase, "idle");
  controller.schedule("edited");
  await clock.fireNext();
  assert.deepEqual(saved, ["edited"]);
}

async function testSkipDoesNotSave(): Promise<void> {

  const clock: ManualClock = manualClock();
  const saved: string[] = [];
  const controller: ThemeAutosaveController<string> = readyController(
    async (value: string): Promise<void> => {
      saved.push(value);
    },
    clock,
    (value: string): AutosaveReadiness => {

      if (value === "") {
        return { kind: "skip" };
      }

      return { kind: "ready" };
    },
  );

  controller.schedule("");
  assert.equal(clock.pendingCount(), 0);
  assert.equal(controller.isDirty(), false);
  assert.equal(saved.length, 0);
}

async function testFlushBypassesTheDelay(): Promise<void> {

  const clock: ManualClock = manualClock();
  const saved: string[] = [];
  const controller: ThemeAutosaveController<string> = readyController(
    async (value: string): Promise<void> => {
      saved.push(value);
    },
    clock,
  );

  controller.schedule("now");
  assert.equal(clock.pendingCount(), 1);
  await controller.flush();
  assert.deepEqual(saved, ["now"]);
  assert.equal(clock.pendingCount(), 0);
}

function testCombinePrefersTheError(): void {

  const states: ThemeAutosaveState[] = [
    { phase: "saved", message: "Saved", canRetry: false },
    { phase: "saving", message: "Saving…", canRetry: false },
    { phase: "error", message: "Name is required.", canRetry: false },
    { phase: "error", message: "Theme could not be updated.", canRetry: true },
  ];
  const combined: ThemeAutosaveState = combineAutosaveStates(states);

  assert.equal(combined.phase, "error");
  assert.equal(combined.canRetry, true);
  assert.match(combined.message, /Name is required/);
  assert.match(combined.message, /could not be updated/);
  assert.equal(
    combineAutosaveStates([
      { phase: "pending", message: "Saving…", canRetry: false },
      { phase: "saved", message: "Saved", canRetry: false },
    ]).phase,
    "saving",
  );
  assert.equal(combineAutosaveStates([]).phase, "idle");
}

function staged(localId: string, name: string, sortOrder: number): StagedElementSync {

  const request: ThemeElementCreateRequest = {
    name,
    band: "top",
    content_kind: "text",
    sort_order: sortOrder,
  };
  const element: StagedElementSync = {
    localId,
    band: "top",
    sortOrder,
    payloadKey: `${name}:${sortOrder}`,
    request,
  };

  return element;
}

function testPlanSync(): void {

  const plan = planThemeElementSync(
    [staged("local-a", "Title", 0), staged("local-c", "New", 1)],
    new Map([["local-a", "server-a"], ["local-b", "server-b"]]),
    [staged("server-a", "Old", 0), staged("server-b", "Gone", 1)],
  );

  assert.deepEqual(plan.deleteServerIds, ["server-b"]);
  assert.equal(plan.patches.length, 1);
  assert.equal(plan.patches[0]?.serverId, "server-a");
  assert.equal(plan.creates.length, 1);
  assert.equal(plan.creates[0]?.localId, "local-c");

  const unchanged = planThemeElementSync(
    [staged("local-a", "Title", 0)],
    new Map([["local-a", "server-a"]]),
    [staged("server-a", "Title", 0)],
  );

  assert.equal(unchanged.deleteServerIds.length, 0);
  assert.equal(unchanged.patches.length, 0);
  assert.equal(unchanged.creates.length, 0);
}

function testPairOrderedIds(): void {

  const pairs: Map<string, string> = pairOrderedIds(["local-a", "local-b"], ["server-a", "server-b"]);

  assert.equal(pairs.get("local-a"), "server-a");
  assert.equal(pairs.get("local-b"), "server-b");
  assert.throws(
    (): void => {
      pairOrderedIds(["local-a"], []);
    },
    /does not match/,
  );
}

function testNewThemeReadiness(): void {

  const snapshot = {
    name: "  ",
    frame: emptyThemeFrameDraft(),
    elements: [],
  };

  assert.equal(newThemeSnapshotReadiness(snapshot, null, false).kind, "skip");
  assert.equal(newThemeSnapshotReadiness({ ...snapshot, name: "Paper" }, null, false).kind, "ready");
  assert.equal(
    newThemeSnapshotReadiness({ ...snapshot, name: "Paper" }, "Name is required.", false).kind,
    "invalid",
  );
  const badFrame = emptyThemeFrameDraft();
  badFrame.pageMargin = "nope";
  assert.equal(
    newThemeSnapshotReadiness({ ...snapshot, name: "Paper", frame: badFrame }, null, false).kind,
    "invalid",
  );
}

function elementRecord(id: string, name: string, sortOrder: number): ThemeElementReadResponse {

  const element: ThemeElementReadResponse = {
    id,
    theme_id: "theme-1",
    band: "top",
    sort_order: sortOrder,
    content_kind: "text",
    name,
    rectangle_color: null,
    rectangle_opacity: 100,
    rectangle_radius: 0,
    text_source: "title",
    font_family: "Source Serif 4",
    font_size: 64,
    font_color: "#112233",
    bold: false,
    italic: false,
    underline: false,
    strikethrough: false,
    font_weight: null,
    alignment: "left",
    image_asset_ref: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };

  return element;
}

function themeRecord(
  id: string,
  name: string,
  elements: ThemeElementReadResponse[],
): ThemeReadResponse {

  const theme: ThemeReadResponse = {
    id,
    name,
    slug: "paper",
    advertisement_type: "carousel",
    template_key: null,
    status: "draft",
    page_margin: 96,
    element_gap: 0,
    element_margin: 0,
    background_kind: "color",
    background_color: "#F6F1E8",
    background_gradient: null,
    background_asset_ref: null,
    elements,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    created_by: null,
  };

  return theme;
}

async function testPersistCreatesOnceThenPatches(): Promise<void> {

  const creates: string[] = [];
  const patches: number[] = [];
  const elementPatches: string[] = [];
  let serverElements: ThemeElementReadResponse[] = [];
  const clients: NewThemePersistClients = {
    describeElement: (element: ThemeElementReadResponse): StagedElementSync => {
      return staged(element.id, element.name, element.sort_order);
    },
    createTheme: async (request): Promise<ThemeReadResponse> => {
      creates.push(request.name);
      serverElements = (request.elements ?? []).map(
        (element: ThemeElementCreateRequest, index: number): ThemeElementReadResponse => {
          return elementRecord(`server-${index}`, element.name, index);
        },
      );

      return themeRecord("theme-1", request.name, serverElements);
    },
    patchTheme: async (_themeId, patch): Promise<ThemeReadResponse> => {
      patches.push(patch.page_margin ?? -1);

      return themeRecord("theme-1", "Paper", serverElements);
    },
    createElement: async (_themeId, request): Promise<ThemeElementReadResponse> => {
      const created: ThemeElementReadResponse = elementRecord(
        "server-new",
        request.name,
        request.sort_order ?? 0,
      );
      serverElements = [...serverElements, created];

      return created;
    },
    patchElement: async (_themeId, elementId, patch): Promise<ThemeElementReadResponse> => {
      elementPatches.push(`${elementId}:${patch.name ?? ""}`);
      serverElements = serverElements.map((element: ThemeElementReadResponse): ThemeElementReadResponse => {

        if (element.id !== elementId) {
          return element;
        }

        return { ...element, name: patch.name ?? element.name };
      });

      return serverElements.find(
        (element: ThemeElementReadResponse): boolean => element.id === elementId,
      ) ?? elementRecord(elementId, patch.name ?? "", 0);
    },
    deleteElement: async (): Promise<void> => {
      return;
    },
    fetchTheme: async (): Promise<ThemeReadResponse> => {
      return themeRecord("theme-1", "Paper", serverElements);
    },
  };
  const localElement: ThemeElementReadResponse = elementRecord("local-a", "Title", 0);
  const snapshot = {
    name: "Paper",
    frame: emptyThemeFrameDraft(),
    elements: [localElement],
  };
  const checkpoints: NewThemePersistState[] = [];
  const created: NewThemePersistState = await persistNewThemeSnapshot(
    snapshot,
    emptyNewThemePersistState(),
    clients,
    (checkpoint: NewThemePersistState): void => {
      checkpoints.push(checkpoint);
    },
  );

  assert.deepEqual(creates, ["Paper"]);
  assert.equal(created.themeId, "theme-1");
  assert.equal(created.localToServerId.get("local-a"), "server-0");
  const widerFrame = emptyThemeFrameDraft();
  widerFrame.pageMargin = "120";
  const patched: NewThemePersistState = await persistNewThemeSnapshot(
    {
      ...snapshot,
      frame: widerFrame,
      elements: [{ ...localElement, name: "Headline" }],
    },
    created,
    clients,
    (checkpoint: NewThemePersistState): void => {
      checkpoints.push(checkpoint);
    },
  );

  assert.deepEqual(creates, ["Paper"]);
  assert.deepEqual(patches, [120]);
  assert.deepEqual(elementPatches, ["server-0:Headline"]);
  assert.equal(patched.themeId, "theme-1");
  assert.ok(checkpoints.length >= 2);
}

async function main(): Promise<void> {

  await testDebounceKeepsTheLatestValue();
  await testInvalidValueDoesNotSaveOrRetry();
  await testServerErrorDoesNotRepeatUntilRetry();
  await testInFlightSaveDoesNotOverwriteANewerEdit();
  await testNoteSavedSkipsTheBaseline();
  await testSkipDoesNotSave();
  await testFlushBypassesTheDelay();
  testCombinePrefersTheError();
  testPlanSync();
  testPairOrderedIds();
  testNewThemeReadiness();
  await testPersistCreatesOnceThenPatches();
}

main().catch((error: unknown): void => {
  console.error(error);
  process.exit(1);
});
