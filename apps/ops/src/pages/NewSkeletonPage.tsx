import { useEffect, useRef, useState, type FormEvent, type ReactElement } from "react";

import {
  createSkeleton,
  createSkeletonElement,
  deleteSkeletonElement,
  fetchSkeletonById,
  patchSkeleton,
  patchSkeletonElement,
} from "../api/client";
import type {
  AdvertisementType,
  SkeletonElementCreateRequest,
  SkeletonElementReadResponse,
  SkeletonReadResponse,
} from "../api/types";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import { useCanWriteOps } from "../session/OpsSessionContext";
import {
  SkeletonElementEditor,
  previewElementStateFromElements,
  skeletonElementCreateRequestFromElement,
  type SkeletonPreviewDraftElement,
  type SkeletonPreviewElementState,
} from "./SkeletonElementEditor";
import { SkeletonAutosaveStatus } from "./SkeletonAutosaveStatus";
import { SkeletonLivePreview } from "./SkeletonLivePreview";
import {
  SkeletonFrameFields,
  emptySkeletonFrameDraft,
  type SkeletonFrameDraft,
} from "./SkeletonFrameFields";
import {
  SKELETON_AUTOSAVE_DELAY_MS,
  formatSkeletonAutosaveError,
  leaveAfterAutosave,
} from "./skeletonAutosave";
import {
  emptyNewSkeletonPersistState,
  newSkeletonSnapshotFingerprint,
  newSkeletonSnapshotReadiness,
  persistNewSkeletonSnapshot,
  type NewSkeletonPersistClients,
  type NewSkeletonPersistState,
  type NewSkeletonSnapshot,
  type StagedElementSync,
} from "./skeletonElementSync";
import { useSkeletonAutosave } from "./useSkeletonAutosave";

export interface NewSkeletonPageProps {
  onCreated: (createdSkeleton: SkeletonReadResponse) => void;
  onCancel: () => void;
}

const LOCAL_SKELETON_ID: string = "local-create-skeleton";

/**
 * Create Skeleton tab.
 *
 * Nothing is stored until the name is filled in and the frame is valid.
 * After a short pause the skeleton is created, and later edits to the frame
 * and elements save on their own. The name is fixed once that first save
 * starts, because the skeleton patch API does not rename a skeleton.
 *
 * @param props - Called when the skeleton first exists, and when the operator leaves
 * @returns The create form
 */
export function NewSkeletonPage({ onCreated, onCancel }: NewSkeletonPageProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [skeletonName, setSkeletonName] = useState<string>("");
  const [advertisementType, setAdvertisementType] = useState<AdvertisementType>(
    "carousel",
  );
  const [frameDraft, setFrameDraft] = useState<SkeletonFrameDraft>(emptySkeletonFrameDraft());
  const [localElements, setLocalElements] = useState<SkeletonElementReadResponse[]>([]);
  const [previewReport, setPreviewReport] = useState<SkeletonPreviewElementState | null>(null);
  const [elementValidationMessage, setElementValidationMessage] = useState<string | null>(null);
  const [persistedSkeletonId, setPersistedSkeletonId] = useState<string | null>(null);
  const persistStateRef = useRef<NewSkeletonPersistState>(emptyNewSkeletonPersistState());
  const elementValidationRef = useRef<string | null>(null);
  const announcedRef = useRef<boolean>(false);
  const onCreatedRef = useRef(onCreated);
  elementValidationRef.current = elementValidationMessage;
  onCreatedRef.current = onCreated;
  const savedPreview: SkeletonPreviewElementState = previewElementStateFromElements(localElements);
  const activePreview: SkeletonPreviewElementState = previewReport ?? savedPreview;
  const localSkeleton: SkeletonReadResponse = localSkeletonRecord(localElements);
  const autosave = useSkeletonAutosave<NewSkeletonSnapshot>({
    delayMs: SKELETON_AUTOSAVE_DELAY_MS,
    readiness: (snapshot: NewSkeletonSnapshot) => {
      return newSkeletonSnapshotReadiness(
        snapshot,
        elementValidationRef.current,
        persistStateRef.current.skeletonId !== null,
      );
    },
    fingerprint: (snapshot: NewSkeletonSnapshot): string => {
      return newSkeletonSnapshotFingerprint(snapshot, describeSkeletonElement);
    },
    save: async (snapshot: NewSkeletonSnapshot): Promise<void> => {
      const nextState: NewSkeletonPersistState = await persistNewSkeletonSnapshot(
        snapshot,
        persistStateRef.current,
        skeletonPersistClients,
        (checkpoint: NewSkeletonPersistState): void => {
          persistStateRef.current = checkpoint;

          if (checkpoint.skeletonId !== null) {
            setPersistedSkeletonId(checkpoint.skeletonId);
          }
        },
      );
      persistStateRef.current = nextState;

      if (nextState.skeletonId === null || announcedRef.current) {
        return;
      }

      announcedRef.current = true;
      setSkeletonName(snapshot.name.trim());
      onCreatedRef.current(createdSkeletonNotice(snapshot.name, nextState.skeletonId));
    },
    formatError: formatSkeletonAutosaveError,
  });
  const nameLocked: boolean = !canWrite
    || persistedSkeletonId !== null
    || autosave.state.phase === "saving";

  useEffect((): void => {

    if (!canWrite) {
      return;
    }

    autosave.schedule({
      name: skeletonName,
      frame: frameDraft,
      elements: localElements,
    });
  }, [
    autosave.schedule,
    canWrite,
    elementValidationMessage,
    frameDraft,
    localElements,
    skeletonName,
  ]);

  const handleBack = (): void => {
    void leaveAfterAutosave(
      autosave.flush,
      autosave.isDirty,
      onCancel,
    );
  };

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>{persistedSkeletonId === null ? "Create Skeleton" : skeletonName.trim()}</h1>
          <p className="lede">
            Add a name. The skeleton is created when you pause, then frame and
            element edits save on their own. Defaults stay paper color, spacing
            96 / 0 / 0, and no elements.
          </p>
          <SkeletonAutosaveStatus
            state={autosave.state}
            onRetry={(): void => {
              void autosave.retry();
            }}
          />
        </div>
        <button type="button" onClick={handleBack}>
          Back to Skeletons
        </button>
      </div>
      <ReadOnlyNotice />

      <div className="skeleton-editor-layout">
        <div className="skeleton-editor-main">
      <form
        className="stack-form campaign-form"
        onSubmit={(formEvent: FormEvent): void => {
          formEvent.preventDefault();
          void autosave.flush();
        }}
      >
        <label>
          Skeleton name
          <input
            id="create-skeleton-name"
            value={skeletonName}
            onChange={(changeEvent): void => {
              setSkeletonName(changeEvent.target.value);
            }}
            required
            disabled={nameLocked}
          />
        </label>
        {persistedSkeletonId === null ? (
          <p className="field-hint">
            The name is saved with the skeleton and stays as it is after that.
          </p>
        ) : (
          <p className="field-hint">This name is saved with the skeleton.</p>
        )}

        <label>
          Advertisement type
          <select
            value={advertisementType}
            onChange={(changeEvent): void => {
              setAdvertisementType(changeEvent.target.value as AdvertisementType);
            }}
            disabled
          >
            <option value="carousel">Carousel</option>
          </select>
        </label>
        <p className="field-hint">Carousel is the only advertisement type for now.</p>
        <SkeletonFrameFields
          frameDraft={frameDraft}
          onDraftChange={setFrameDraft}
          disabled={!canWrite}
        />
      </form>

      <SkeletonElementEditor
        skeleton={localSkeleton}
        onSkeletonUpdated={(): void => {
          return;
        }}
        onLocalElementsChange={setLocalElements}
        onValidationMessageChange={setElementValidationMessage}
        onPreviewElementsChange={(
          elements: SkeletonPreviewDraftElement[] | null,
          draftError: string | null,
        ): void => {
          setPreviewReport({ elements, draftError });
        }}
      />
        </div>
        <SkeletonLivePreview
          frameDraft={frameDraft}
          elements={activePreview.elements}
          draftError={activePreview.draftError}
        />
      </div>
    </section>
  );
}

const skeletonPersistClients: NewSkeletonPersistClients = {
  describeElement: describeSkeletonElement,
  createSkeleton,
  patchSkeleton,
  createElement: createSkeletonElement,
  patchElement: patchSkeletonElement,
  deleteElement: deleteSkeletonElement,
  fetchSkeleton: fetchSkeletonById,
};

function describeSkeletonElement(element: SkeletonElementReadResponse): StagedElementSync {

  const request: SkeletonElementCreateRequest = {
    ...skeletonElementCreateRequestFromElement(element),
    sort_order: element.sort_order,
  };
  const staged: StagedElementSync = {
    localId: element.id,
    band: element.band,
    sortOrder: element.sort_order,
    payloadKey: JSON.stringify(request),
    request,
  };

  return staged;
}

function createdSkeletonNotice(skeletonName: string, skeletonId: string): SkeletonReadResponse {

  const skeleton: SkeletonReadResponse = {
    ...localSkeletonRecord([]),
    id: skeletonId,
    name: skeletonName.trim(),
  };

  return skeleton;
}

function localSkeletonRecord(elements: SkeletonElementReadResponse[]): SkeletonReadResponse {

  const skeleton: SkeletonReadResponse = {
    id: LOCAL_SKELETON_ID,
    name: "",
    slug: "",
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
    created_at: "",
    updated_at: "",
    created_by: null,
  };

  return skeleton;
}
