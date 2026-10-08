import { useState, type FormEvent, type ReactElement } from "react";

import { createTheme } from "../api/client";
import type {
  AdvertisementType,
  ThemeCreateRequest,
  ThemeElementReadResponse,
  ThemePatchRequest,
  ThemeReadResponse,
} from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import { useCanWriteOps } from "../session/OpsSessionContext";
import {
  ThemeElementEditor,
  themeElementCreateRequestsInBandOrder,
} from "./ThemeElementEditor";
import {
  ThemeFrameFields,
  emptyThemeFrameDraft,
  themePatchFromFrameDraft,
  type ThemeFrameDraft,
} from "./ThemeFrameFields";

export interface NewThemePageProps {
  onCreated: (createdTheme: ThemeReadResponse) => void;
  onCancel: () => void;
}

const LOCAL_THEME_ID: string = "local-create-theme";

/**
 * Create Theme tab: preset the frame and elements, then save them together.
 *
 * @param props - Success and cancel navigation callbacks
 * @returns The Create Theme form
 */
export function NewThemePage({ onCreated, onCancel }: NewThemePageProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [themeName, setThemeName] = useState<string>("");
  const [advertisementType, setAdvertisementType] = useState<AdvertisementType>(
    "carousel",
  );
  const [frameDraft, setFrameDraft] = useState<ThemeFrameDraft>(emptyThemeFrameDraft());
  const [localElements, setLocalElements] = useState<ThemeElementReadResponse[]>([]);
  const [actionError, setActionError] = useState<unknown>(null);
  const [isBusy, setIsBusy] = useState<boolean>(false);
  const trimmedThemeName: string = themeName.trim();
  const canCreate: boolean = canWrite && !isBusy && trimmedThemeName !== "";
  const localTheme: ThemeReadResponse = localThemeRecord(localElements);

  const handleCreateTheme = async (formEvent: FormEvent): Promise<void> => {

    formEvent.preventDefault();

    if (trimmedThemeName === "") {
      setActionError(new Error("Theme name is required."));

      return;
    }

    setIsBusy(true);
    setActionError(null);

    try {
      const framePatch: ThemePatchRequest = themePatchFromFrameDraft(frameDraft);
      const themeCreateRequest: ThemeCreateRequest = {
        name: trimmedThemeName,
        advertisement_type: advertisementType,
        status: framePatch.status ?? undefined,
        page_margin: framePatch.page_margin ?? undefined,
        element_gap: framePatch.element_gap ?? undefined,
        element_margin: framePatch.element_margin ?? undefined,
        background_kind: framePatch.background_kind ?? undefined,
        background_color: framePatch.background_color,
        background_gradient: framePatch.background_gradient,
        background_asset_ref: framePatch.background_asset_ref,
        elements: themeElementCreateRequestsInBandOrder(localElements),
      };
      const createdTheme: ThemeReadResponse = await createTheme(themeCreateRequest);

      onCreated(createdTheme);
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>Create Theme</h1>
          <p className="lede">
            Set the name, frame, and elements, then create the theme in one save.
            Defaults stay Draft, paper color, spacing 96 / 0 / 0, and no elements.
          </p>
        </div>
        <button type="button" onClick={onCancel}>
          Back to Themes
        </button>
      </div>
      <ReadOnlyNotice />

      <form
        id="create-theme-form"
        className="stack-form campaign-form"
        onSubmit={(formEvent: FormEvent): void => {
          void handleCreateTheme(formEvent);
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
            disabled={!canWrite || isBusy}
          />
        </label>

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
          disabled={!canWrite || isBusy}
        />
      </form>

      <ThemeElementEditor
        theme={localTheme}
        onThemeUpdated={(): void => {
          return;
        }}
        onLocalElementsChange={setLocalElements}
      />

      {canWrite && !isBusy && trimmedThemeName === "" ? (
        <p className="field-hint">Add a theme name before creating.</p>
      ) : null}
      <ErrorBanner error={actionError} />
      <div className="button-row">
        <button type="submit" form="create-theme-form" disabled={!canCreate}>
          {isBusy ? "Saving…" : "Create Theme"}
        </button>
        <button type="button" onClick={onCancel} disabled={isBusy}>
          Cancel
        </button>
      </div>
    </section>
  );
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
