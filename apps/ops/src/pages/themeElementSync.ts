import type {
  ThemeCreateRequest,
  ThemeElementBand,
  ThemeElementCreateRequest,
  ThemeElementPatchRequest,
  ThemeElementReadResponse,
  ThemePatchRequest,
  ThemeReadResponse,
} from "../api/types.ts";
import type { AutosaveReadiness } from "./themeAutosave.ts";
import {
  frameDraftError,
  themePatchFromFrameDraft,
  type ThemeFrameDraft,
} from "./themeFrameDraft.ts";

export interface StagedElementSync {
  localId: string;
  band: ThemeElementBand;
  sortOrder: number;
  payloadKey: string;
  request: ThemeElementCreateRequest;
}

export interface ThemeElementSyncPlan {
  deleteServerIds: string[];
  patches: { serverId: string; request: ThemeElementPatchRequest }[];
  creates: { localId: string; request: ThemeElementCreateRequest }[];
}

export interface NewThemeSnapshot {
  name: string;
  frame: ThemeFrameDraft;
  elements: ThemeElementReadResponse[];
}

export interface NewThemePersistState {
  themeId: string | null;
  localToServerId: Map<string, string>;
  serverElements: ThemeElementReadResponse[];
  savedFrameFingerprint: string | null;
}

export interface NewThemePersistClients {
  describeElement: (element: ThemeElementReadResponse) => StagedElementSync;
  createTheme: (request: ThemeCreateRequest) => Promise<ThemeReadResponse>;
  patchTheme: (themeId: string, patch: ThemePatchRequest) => Promise<ThemeReadResponse>;
  createElement: (
    themeId: string,
    request: ThemeElementCreateRequest,
  ) => Promise<ThemeElementReadResponse>;
  patchElement: (
    themeId: string,
    elementId: string,
    patch: ThemeElementPatchRequest,
  ) => Promise<ThemeElementReadResponse>;
  deleteElement: (themeId: string, elementId: string) => Promise<void>;
  fetchTheme: (themeId: string) => Promise<ThemeReadResponse>;
}

const BAND_RANK: Record<ThemeElementBand, number> = {
  top: 0,
  middle: 1,
  bottom: 2,
};

/**
 * Return a persist record for a theme that has not been created yet.
 *
 * @returns Empty id map and no server elements
 */
export function emptyNewThemePersistState(): NewThemePersistState {

  const state: NewThemePersistState = {
    themeId: null,
    localToServerId: new Map(),
    serverElements: [],
    savedFrameFingerprint: null,
  };

  return state;
}

/**
 * Decide whether a new-theme snapshot can be written.
 *
 * A blank name waits. An invalid frame or element surfaces the message
 * and does not start a request. After the theme exists, a blank name is
 * not a reason to wait because the name field is locked.
 *
 * @param snapshot - Name, frame, and staged elements
 * @param elementError - First element draft error, or null
 * @param themeExists - Whether the create request has already succeeded
 * @returns Skip, invalid, or ready
 */
export function newThemeSnapshotReadiness(
  snapshot: NewThemeSnapshot,
  elementError: string | null,
  themeExists: boolean,
): AutosaveReadiness {

  const frameError: string | null = frameDraftError(snapshot.frame);

  if (frameError !== null) {
    const invalidFrame: AutosaveReadiness = { kind: "invalid", message: frameError };

    return invalidFrame;
  }

  if (elementError !== null && elementError !== "") {
    const invalidElement: AutosaveReadiness = { kind: "invalid", message: elementError };

    return invalidElement;
  }

  if (!themeExists && snapshot.name.trim() === "") {
    const waitingForName: AutosaveReadiness = { kind: "skip" };

    return waitingForName;
  }

  const ready: AutosaveReadiness = { kind: "ready" };

  return ready;
}

/**
 * Stable identity for one snapshot. Equal fingerprints are not written again.
 *
 * @param snapshot - Name, frame, and staged elements
 * @param describeElement - Payload key for one element
 * @returns A string that changes when the saved fields change
 */
export function newThemeSnapshotFingerprint(
  snapshot: NewThemeSnapshot,
  describeElement: (element: ThemeElementReadResponse) => StagedElementSync,
): string {

  const orderedKeys: string[] = orderStaged(snapshot.elements.map(describeElement))
    .map((staged: StagedElementSync): string => staged.payloadKey);
  const fingerprint: string = JSON.stringify({
    name: snapshot.name.trim(),
    frame: themePatchFromFrameDraft(snapshot.frame),
    elements: orderedKeys,
  });

  return fingerprint;
}

/**
 * Pair created rows with the local rows that were sent, in band order.
 *
 * @param localIdsInSendOrder - Local ids in the order posted
 * @param serverIdsInReadOrder - Server ids in band then sort order
 * @returns Local id to server id
 */
export function pairOrderedIds(
  localIdsInSendOrder: readonly string[],
  serverIdsInReadOrder: readonly string[],
): Map<string, string> {

  if (localIdsInSendOrder.length !== serverIdsInReadOrder.length) {
    throw new Error(
      "Created theme element count does not match the elements that were sent.",
    );
  }

  const localToServerId: Map<string, string> = new Map();

  localIdsInSendOrder.forEach((localId: string, index: number): void => {
    const serverId: string | undefined = serverIdsInReadOrder[index];

    if (serverId === undefined) {
      return;
    }

    localToServerId.set(localId, serverId);
  });

  return localToServerId;
}

/**
 * Plan creates, patches, and deletes so the server matches the staged elements.
 *
 * @param localElements - Elements currently on the form
 * @param localToServerId - Ids assigned by earlier creates
 * @param serverElements - Elements last known to be stored, described the same way
 * @returns Writes to run, in delete / patch / create order
 */
export function planThemeElementSync(
  localElements: readonly StagedElementSync[],
  localToServerId: ReadonlyMap<string, string>,
  serverElements: readonly StagedElementSync[],
): ThemeElementSyncPlan {

  const serverById: Map<string, StagedElementSync> = new Map(
    serverElements.map((staged: StagedElementSync): [string, StagedElementSync] => {
      return [staged.localId, staged];
    }),
  );
  const liveServerIds: Set<string> = new Set();
  const patches: { serverId: string; request: ThemeElementPatchRequest }[] = [];
  const creates: { localId: string; request: ThemeElementCreateRequest }[] = [];

  localElements.forEach((localElement: StagedElementSync): void => {
    const serverId: string | undefined = localToServerId.get(localElement.localId);
    const serverElement: StagedElementSync | undefined = serverId === undefined
      ? undefined
      : serverById.get(serverId);

    if (serverId === undefined || serverElement === undefined) {
      creates.push({
        localId: localElement.localId,
        request: localElement.request,
      });

      return;
    }

    liveServerIds.add(serverId);

    if (localElement.payloadKey !== serverElement.payloadKey) {
      patches.push({
        serverId,
        request: localElement.request,
      });
    }
  });

  const deleteServerIds: string[] = serverElements
    .map((staged: StagedElementSync): string => staged.localId)
    .filter((serverId: string): boolean => !liveServerIds.has(serverId));
  const plan: ThemeElementSyncPlan = {
    deleteServerIds,
    patches,
    creates,
  };

  return plan;
}

/**
 * Create the theme on the first call, then patch the frame and sync elements.
 *
 * The checkpoint runs as soon as the theme id exists so a later failure
 * retries the sync instead of creating a second theme.
 *
 * @param snapshot - Latest name, frame, and elements
 * @param state - Id map from the previous successful checkpoint
 * @param clients - API calls and the element payload description
 * @param onCheckpoint - Called whenever the id map should be remembered
 * @returns The checkpoint to use for the next save
 */
export async function persistNewThemeSnapshot(
  snapshot: NewThemeSnapshot,
  state: NewThemePersistState,
  clients: NewThemePersistClients,
  onCheckpoint: (nextState: NewThemePersistState) => void,
): Promise<NewThemePersistState> {

  const stagedLocal: StagedElementSync[] = snapshot.elements.map(clients.describeElement);

  if (state.themeId === null) {
    const createdTheme: ThemeReadResponse = await clients.createTheme(
      themeCreateRequestFromSnapshot(snapshot, stagedLocal),
    );
    const sentIds: string[] = orderStaged(stagedLocal).map(
      (staged: StagedElementSync): string => staged.localId,
    );
    const serverStaged: StagedElementSync[] = createdTheme.elements.map(clients.describeElement);
    const serverIds: string[] = orderStaged(serverStaged).map(
      (staged: StagedElementSync): string => staged.localId,
    );
    let localToServerId: Map<string, string> = new Map();

    try {
      localToServerId = pairOrderedIds(sentIds, serverIds);
    } catch (caughtError: unknown) {
      const failedPairState: NewThemePersistState = {
        themeId: createdTheme.id,
        localToServerId,
        serverElements: createdTheme.elements,
        savedFrameFingerprint: JSON.stringify(themePatchFromFrameDraft(snapshot.frame)),
      };
      onCheckpoint(failedPairState);

      throw caughtError;
    }

    const createdState: NewThemePersistState = {
      themeId: createdTheme.id,
      localToServerId,
      serverElements: createdTheme.elements,
      savedFrameFingerprint: JSON.stringify(themePatchFromFrameDraft(snapshot.frame)),
    };
    onCheckpoint(createdState);

    return createdState;
  }

  const themeId: string = state.themeId;
  let nextState: NewThemePersistState = {
    themeId,
    localToServerId: new Map(state.localToServerId),
    serverElements: state.serverElements,
    savedFrameFingerprint: state.savedFrameFingerprint,
  };
  const frameKey: string = JSON.stringify(themePatchFromFrameDraft(snapshot.frame));

  if (frameKey !== nextState.savedFrameFingerprint) {
    const patchedTheme: ThemeReadResponse = await clients.patchTheme(
      themeId,
      themePatchFromFrameDraft(snapshot.frame),
    );
    nextState = {
      ...nextState,
      serverElements: patchedTheme.elements,
      savedFrameFingerprint: frameKey,
    };
    onCheckpoint(nextState);
  }

  const serverStaged: StagedElementSync[] = nextState.serverElements.map(clients.describeElement);
  const plan: ThemeElementSyncPlan = planThemeElementSync(
    stagedLocal,
    nextState.localToServerId,
    serverStaged,
  );
  const hasElementWrites: boolean = plan.deleteServerIds.length > 0
    || plan.patches.length > 0
    || plan.creates.length > 0;

  if (!hasElementWrites) {
    return nextState;
  }

  for (const serverId of plan.deleteServerIds) {
    await clients.deleteElement(themeId, serverId);
  }

  for (const patch of plan.patches) {
    await clients.patchElement(themeId, patch.serverId, patch.request);
  }

  const localIds: Set<string> = new Set(
    stagedLocal.map((staged: StagedElementSync): string => staged.localId),
  );
  const nextMap: Map<string, string> = new Map(nextState.localToServerId);

  Array.from(nextMap.keys()).forEach((localId: string): void => {

    if (!localIds.has(localId)) {
      nextMap.delete(localId);
    }
  });

  for (const create of plan.creates) {
    const createdElement: ThemeElementReadResponse = await clients.createElement(
      themeId,
      create.request,
    );
    nextMap.set(create.localId, createdElement.id);
  }

  nextState = {
    ...nextState,
    localToServerId: nextMap,
  };
  onCheckpoint(nextState);

  const reloadedTheme: ThemeReadResponse = await clients.fetchTheme(themeId);
  nextState = {
    ...nextState,
    serverElements: reloadedTheme.elements,
  };
  onCheckpoint(nextState);

  return nextState;
}

/**
 * Order staged elements the same way the theme API reads them back.
 *
 * @param elements - Unordered staged elements
 * @returns Top, then middle, then bottom, each by sort order
 */
export function orderStaged(
  elements: readonly StagedElementSync[],
): StagedElementSync[] {

  const ordered: StagedElementSync[] = [...elements].sort(
    (left: StagedElementSync, right: StagedElementSync): number => {

      if (left.band !== right.band) {
        return BAND_RANK[left.band] - BAND_RANK[right.band];
      }

      if (left.sortOrder !== right.sortOrder) {
        return left.sortOrder - right.sortOrder;
      }

      if (left.localId < right.localId) {
        return -1;
      }

      if (left.localId > right.localId) {
        return 1;
      }

      return 0;
    },
  );

  return ordered;
}

function themeCreateRequestFromSnapshot(
  snapshot: NewThemeSnapshot,
  stagedElements: readonly StagedElementSync[],
): ThemeCreateRequest {

  const framePatch: ThemePatchRequest = themePatchFromFrameDraft(snapshot.frame);
  const elements: ThemeElementCreateRequest[] = orderStaged(stagedElements).map(
    (staged: StagedElementSync): ThemeElementCreateRequest => {
      const request: ThemeElementCreateRequest = { ...staged.request };

      delete request.sort_order;

      return request;
    },
  );
  const themeCreateRequest: ThemeCreateRequest = {
    name: snapshot.name.trim(),
    advertisement_type: "carousel",
    status: framePatch.status ?? undefined,
    page_margin: framePatch.page_margin ?? undefined,
    element_gap: framePatch.element_gap ?? undefined,
    element_margin: framePatch.element_margin ?? undefined,
    background_kind: framePatch.background_kind ?? undefined,
    background_color: framePatch.background_color,
    background_gradient: framePatch.background_gradient,
    background_asset_ref: framePatch.background_asset_ref,
    elements,
  };

  return themeCreateRequest;
}
