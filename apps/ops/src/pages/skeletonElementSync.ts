import type {
  SkeletonCreateRequest,
  SkeletonElementBand,
  SkeletonElementCreateRequest,
  SkeletonElementPatchRequest,
  SkeletonElementReadResponse,
  SkeletonPatchRequest,
  SkeletonReadResponse,
} from "../api/types.ts";
import type { AutosaveReadiness } from "./skeletonAutosave.ts";
import {
  frameDraftError,
  skeletonPatchFromFrameDraft,
  type SkeletonFrameDraft,
} from "./skeletonFrameDraft.ts";

export interface StagedElementSync {
  localId: string;
  band: SkeletonElementBand;
  sortOrder: number;
  payloadKey: string;
  request: SkeletonElementCreateRequest;
}

export interface SkeletonElementSyncPlan {
  deleteServerIds: string[];
  patches: { serverId: string; request: SkeletonElementPatchRequest }[];
  creates: { localId: string; request: SkeletonElementCreateRequest }[];
}

export interface NewSkeletonSnapshot {
  name: string;
  frame: SkeletonFrameDraft;
  elements: SkeletonElementReadResponse[];
}

export interface NewSkeletonPersistState {
  skeletonId: string | null;
  localToServerId: Map<string, string>;
  serverElements: SkeletonElementReadResponse[];
  savedFrameFingerprint: string | null;
}

export interface NewSkeletonPersistClients {
  describeElement: (element: SkeletonElementReadResponse) => StagedElementSync;
  createSkeleton: (request: SkeletonCreateRequest) => Promise<SkeletonReadResponse>;
  patchSkeleton: (skeletonId: string, patch: SkeletonPatchRequest) => Promise<SkeletonReadResponse>;
  createElement: (
    skeletonId: string,
    request: SkeletonElementCreateRequest,
  ) => Promise<SkeletonElementReadResponse>;
  patchElement: (
    skeletonId: string,
    elementId: string,
    patch: SkeletonElementPatchRequest,
  ) => Promise<SkeletonElementReadResponse>;
  deleteElement: (skeletonId: string, elementId: string) => Promise<void>;
  fetchSkeleton: (skeletonId: string) => Promise<SkeletonReadResponse>;
}

const BAND_RANK: Record<SkeletonElementBand, number> = {
  top: 0,
  middle: 1,
  bottom: 2,
};

/**
 * Return a persist record for a skeleton that has not been created yet.
 *
 * @returns Empty id map and no server elements
 */
export function emptyNewSkeletonPersistState(): NewSkeletonPersistState {

  const state: NewSkeletonPersistState = {
    skeletonId: null,
    localToServerId: new Map(),
    serverElements: [],
    savedFrameFingerprint: null,
  };

  return state;
}

/**
 * Decide whether a new-skeleton snapshot can be written.
 *
 * A blank name waits. An invalid frame or element surfaces the message
 * and does not start a request. After the skeleton exists, a blank name is
 * not a reason to wait because the name field is locked.
 *
 * @param snapshot - Name, frame, and staged elements
 * @param elementError - First element draft error, or null
 * @param skeletonExists - Whether the create request has already succeeded
 * @returns Skip, invalid, or ready
 */
export function newSkeletonSnapshotReadiness(
  snapshot: NewSkeletonSnapshot,
  elementError: string | null,
  skeletonExists: boolean,
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

  if (!skeletonExists && snapshot.name.trim() === "") {
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
export function newSkeletonSnapshotFingerprint(
  snapshot: NewSkeletonSnapshot,
  describeElement: (element: SkeletonElementReadResponse) => StagedElementSync,
): string {

  const orderedKeys: string[] = orderStaged(snapshot.elements.map(describeElement))
    .map((staged: StagedElementSync): string => staged.payloadKey);
  const fingerprint: string = JSON.stringify({
    name: snapshot.name.trim(),
    frame: skeletonPatchFromFrameDraft(snapshot.frame),
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
      "Created skeleton element count does not match the elements that were sent.",
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
export function planSkeletonElementSync(
  localElements: readonly StagedElementSync[],
  localToServerId: ReadonlyMap<string, string>,
  serverElements: readonly StagedElementSync[],
): SkeletonElementSyncPlan {

  const serverById: Map<string, StagedElementSync> = new Map(
    serverElements.map((staged: StagedElementSync): [string, StagedElementSync] => {
      return [staged.localId, staged];
    }),
  );
  const liveServerIds: Set<string> = new Set();
  const patches: { serverId: string; request: SkeletonElementPatchRequest }[] = [];
  const creates: { localId: string; request: SkeletonElementCreateRequest }[] = [];

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
  const plan: SkeletonElementSyncPlan = {
    deleteServerIds,
    patches,
    creates,
  };

  return plan;
}

/**
 * Create the skeleton on the first call, then patch the frame and sync elements.
 *
 * The checkpoint runs as soon as the skeleton id exists so a later failure
 * retries the sync instead of creating a second skeleton.
 *
 * @param snapshot - Latest name, frame, and elements
 * @param state - Id map from the previous successful checkpoint
 * @param clients - API calls and the element payload description
 * @param onCheckpoint - Called whenever the id map should be remembered
 * @returns The checkpoint to use for the next save
 */
export async function persistNewSkeletonSnapshot(
  snapshot: NewSkeletonSnapshot,
  state: NewSkeletonPersistState,
  clients: NewSkeletonPersistClients,
  onCheckpoint: (nextState: NewSkeletonPersistState) => void,
): Promise<NewSkeletonPersistState> {

  const stagedLocal: StagedElementSync[] = snapshot.elements.map(clients.describeElement);

  if (state.skeletonId === null) {
    const createdSkeleton: SkeletonReadResponse = await clients.createSkeleton(
      skeletonCreateRequestFromSnapshot(snapshot, stagedLocal),
    );
    const sentIds: string[] = orderStaged(stagedLocal).map(
      (staged: StagedElementSync): string => staged.localId,
    );
    const serverStaged: StagedElementSync[] = createdSkeleton.elements.map(clients.describeElement);
    const serverIds: string[] = orderStaged(serverStaged).map(
      (staged: StagedElementSync): string => staged.localId,
    );
    let localToServerId: Map<string, string> = new Map();

    try {
      localToServerId = pairOrderedIds(sentIds, serverIds);
    } catch (caughtError: unknown) {
      const failedPairState: NewSkeletonPersistState = {
        skeletonId: createdSkeleton.id,
        localToServerId,
        serverElements: createdSkeleton.elements,
        savedFrameFingerprint: JSON.stringify(skeletonPatchFromFrameDraft(snapshot.frame)),
      };
      onCheckpoint(failedPairState);

      throw caughtError;
    }

    const createdState: NewSkeletonPersistState = {
      skeletonId: createdSkeleton.id,
      localToServerId,
      serverElements: createdSkeleton.elements,
      savedFrameFingerprint: JSON.stringify(skeletonPatchFromFrameDraft(snapshot.frame)),
    };
    onCheckpoint(createdState);

    return createdState;
  }

  const skeletonId: string = state.skeletonId;
  let nextState: NewSkeletonPersistState = {
    skeletonId,
    localToServerId: new Map(state.localToServerId),
    serverElements: state.serverElements,
    savedFrameFingerprint: state.savedFrameFingerprint,
  };
  const frameKey: string = JSON.stringify(skeletonPatchFromFrameDraft(snapshot.frame));

  if (frameKey !== nextState.savedFrameFingerprint) {
    const patchedSkeleton: SkeletonReadResponse = await clients.patchSkeleton(
      skeletonId,
      skeletonPatchFromFrameDraft(snapshot.frame),
    );
    nextState = {
      ...nextState,
      serverElements: patchedSkeleton.elements,
      savedFrameFingerprint: frameKey,
    };
    onCheckpoint(nextState);
  }

  const serverStaged: StagedElementSync[] = nextState.serverElements.map(clients.describeElement);
  const plan: SkeletonElementSyncPlan = planSkeletonElementSync(
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
    await clients.deleteElement(skeletonId, serverId);
  }

  for (const patch of plan.patches) {
    await clients.patchElement(skeletonId, patch.serverId, patch.request);
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
    const createdElement: SkeletonElementReadResponse = await clients.createElement(
      skeletonId,
      create.request,
    );
    nextMap.set(create.localId, createdElement.id);
  }

  nextState = {
    ...nextState,
    localToServerId: nextMap,
  };
  onCheckpoint(nextState);

  const reloadedSkeleton: SkeletonReadResponse = await clients.fetchSkeleton(skeletonId);
  nextState = {
    ...nextState,
    serverElements: reloadedSkeleton.elements,
  };
  onCheckpoint(nextState);

  return nextState;
}

/**
 * Order staged elements the same way the skeleton API reads them back.
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

function skeletonCreateRequestFromSnapshot(
  snapshot: NewSkeletonSnapshot,
  stagedElements: readonly StagedElementSync[],
): SkeletonCreateRequest {

  const framePatch: SkeletonPatchRequest = skeletonPatchFromFrameDraft(snapshot.frame);
  const elements: SkeletonElementCreateRequest[] = orderStaged(stagedElements).map(
    (staged: StagedElementSync): SkeletonElementCreateRequest => {
      const request: SkeletonElementCreateRequest = { ...staged.request };

      delete request.sort_order;

      return request;
    },
  );
  const skeletonCreateRequest: SkeletonCreateRequest = {
    name: snapshot.name.trim(),
    advertisement_type: "carousel",
    page_margin: framePatch.page_margin ?? undefined,
    element_gap: framePatch.element_gap ?? undefined,
    element_margin: framePatch.element_margin ?? undefined,
    background_kind: framePatch.background_kind ?? undefined,
    background_color: framePatch.background_color,
    background_gradient: framePatch.background_gradient,
    background_asset_ref: framePatch.background_asset_ref,
    elements,
  };

  return skeletonCreateRequest;
}
