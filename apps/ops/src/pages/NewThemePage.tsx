import { useEffect, useRef, useState, type FormEvent, type ReactElement } from "react";

import {
  createTheme,
  createThemeElement,
  deleteThemeElement,
  fetchThemeById,
  patchTheme,
  patchThemeElement,
} from "../api/client";
import type {
  AdvertisementType,
  ThemeElementCreateRequest,
  ThemeElementReadResponse,
  ThemeReadResponse,
} from "../api/types";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import { useCanWriteOps } from "../session/OpsSessionContext";
import {
  ThemeElementEditor,
  previewElementStateFromElements,
  themeElementCreateRequestFromElement,
  type ThemePreviewDraftElement,
  type ThemePreviewElementState,
} from "./ThemeElementEditor";
import { ThemeAutosaveStatus } from "./ThemeAutosaveStatus";
import { ThemeLivePreview } from "./ThemeLivePreview";
import {
  ThemeFrameFields,
  emptyThemeFrameDraft,
  type ThemeFrameDraft,
} from "./ThemeFrameFields";
import {
  THEME_AUTOSAVE_DELAY_MS,
  formatThemeAutosaveError,
  leaveAfterAutosave,
} from "./themeAutosave";
import {
  emptyNewThemePersistState,
  newThemeSnapshotFingerprint,
  newThemeSnapshotReadiness,
  persistNewThemeSnapshot,
  type NewThemePersistClients,
  type NewThemePersistState,
  type NewThemeSnapshot,
  type StagedElementSync,
} from "./themeElementSync";
import { useThemeAutosave } from "./useThemeAutosave";

export interface NewThemePageProps {
  onCreated: (createdTheme: ThemeReadResponse) => void;
  onCancel: () => void;
}

const LOCAL_THEME_ID: string = "local-create-theme";

/**
 * Create Theme tab.
 *
 * Nothing is stored until the name is filled in and the frame is valid.
 * After a short pause the theme is created, and later edits to the frame
 * and elements save on their own. The name is fixed once that first save
 * starts, because the theme patch API does not rename a theme.
 *
 * @param props - Called when the theme first exists, and when the operator leaves
 * @returns The create form
 */
export function NewThemePage({ onCreated, onCancel }: NewThemePageProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [themeName, setThemeName] = useState<string>("");
  const [advertisementType, setAdvertisementType] = useState<AdvertisementType>(
    "carousel",
  );
  const [frameDraft, setFrameDraft] = useState<ThemeFrameDraft>(emptyThemeFrameDraft());
  const [localElements, setLocalElements] = useState<ThemeElementReadResponse[]>([]);
  const [previewReport, setPreviewReport] = useState<ThemePreviewElementState | null>(null);
  const [elementValidationMessage, setElementValidationMessage] = useState<string | null>(null);
  const [persistedThemeId, setPersistedThemeId] = useState<string | null>(null);
  const persistStateRef = useRef<NewThemePersistState>(emptyNewThemePersistState());
  const elementValidationRef = useRef<string | null>(null);
  const announcedRef = useRef<boolean>(false);
  const onCreatedRef = useRef(onCreated);
  elementValidationRef.current = elementValidationMessage;
  onCreatedRef.current = onCreated;
  const savedPreview: ThemePreviewElementState = previewElementStateFromElements(localElements);
  const activePreview: ThemePreviewElementState = previewReport ?? savedPreview;
  const localTheme: ThemeReadResponse = localThemeRecord(localElements);
  const autosave = useThemeAutosave<NewThemeSnapshot>({
    delayMs: THEME_AUTOSAVE_DELAY_MS,
    readiness: (snapshot: NewThemeSnapshot) => {
      return newThemeSnapshotReadiness(
        snapshot,
        elementValidationRef.current,
        persistStateRef.current.themeId !== null,
      );
    },
    fingerprint: (snapshot: NewThemeSnapshot): string => {
      return newThemeSnapshotFingerprint(snapshot, describeThemeElement);
    },
    save: async (snapshot: NewThemeSnapshot): Promise<void> => {
      const nextState: NewThemePersistState = await persistNewThemeSnapshot(
        snapshot,
        persistStateRef.current,
        themePersistClients,
        (checkpoint: NewThemePersistState): void => {
          persistStateRef.current = checkpoint;

          if (checkpoint.themeId !== null) {
            setPersistedThemeId(checkpoint.themeId);
          }
        },
      );
      persistStateRef.current = nextState;

      if (nextState.themeId === null || announcedRef.current) {
        return;
      }

      announcedRef.current = true;
      setThemeName(snapshot.name.trim());
      onCreatedRef.current(createdThemeNotice(snapshot.name, nextState.themeId));
    },
    formatError: formatThemeAutosaveError,
  });
  const nameLocked: boolean = !canWrite
    || persistedThemeId !== null
    || autosave.state.phase === "saving";

  useEffect((): void => {

    if (!canWrite) {
      return;
    }

    autosave.schedule({
      name: themeName,
      frame: frameDraft,
      elements: localElements,
    });
  }, [
    autosave.schedule,
    canWrite,
    elementValidationMessage,
    frameDraft,
    localElements,
    themeName,
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
          <h1>{persistedThemeId === null ? "Create theme" : themeName.trim()}</h1>
          <p className="lede">
            Add a name. The theme is created when you pause, then frame and
            element edits save on their own. Defaults stay paper color, spacing
            96 / 0 / 0, and no elements.
          </p>
          <ThemeAutosaveStatus
            state={autosave.state}
            onRetry={(): void => {
              void autosave.retry();
            }}
          />
        </div>
        <button type="button" onClick={handleBack}>
          Back to Themes
        </button>
      </div>
      <ReadOnlyNotice />

      <div className="theme-editor-layout">
        <div className="theme-editor-main">
      <form
        className="stack-form campaign-form"
        onSubmit={(formEvent: FormEvent): void => {
          formEvent.preventDefault();
          void autosave.flush();
        }}
      >
        <label>
          Theme name
          <input
            id="create-theme-name"
            value={themeName}
            onChange={(changeEvent): void => {
              setThemeName(changeEvent.target.value);
            }}
            required
            disabled={nameLocked}
          />
        </label>
        {persistedThemeId === null ? (
          <p className="field-hint">
            The name is saved with the theme and stays as it is after that.
          </p>
        ) : (
          <p className="field-hint">This name is saved with the theme.</p>
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
        <ThemeFrameFields
          frameDraft={frameDraft}
          onDraftChange={setFrameDraft}
          disabled={!canWrite}
        />
      </form>

      <ThemeElementEditor
        theme={localTheme}
        onThemeUpdated={(): void => {
          return;
        }}
        onLocalElementsChange={setLocalElements}
        onValidationMessageChange={setElementValidationMessage}
        onPreviewElementsChange={(
          elements: ThemePreviewDraftElement[] | null,
          draftError: string | null,
        ): void => {
          setPreviewReport({ elements, draftError });
        }}
      />
        </div>
        <ThemeLivePreview
          frameDraft={frameDraft}
          elements={activePreview.elements}
          draftError={activePreview.draftError}
        />
      </div>
    </section>
  );
}

const themePersistClients: NewThemePersistClients = {
  describeElement: describeThemeElement,
  createTheme,
  patchTheme,
  createElement: createThemeElement,
  patchElement: patchThemeElement,
  deleteElement: deleteThemeElement,
  fetchTheme: fetchThemeById,
};

function describeThemeElement(element: ThemeElementReadResponse): StagedElementSync {

  const request: ThemeElementCreateRequest = {
    ...themeElementCreateRequestFromElement(element),
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

function createdThemeNotice(themeName: string, themeId: string): ThemeReadResponse {

  const theme: ThemeReadResponse = {
    ...localThemeRecord([]),
    id: themeId,
    name: themeName.trim(),
  };

  return theme;
}

function localThemeRecord(elements: ThemeElementReadResponse[]): ThemeReadResponse {

  const theme: ThemeReadResponse = {
    id: LOCAL_THEME_ID,
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

  return theme;
}
