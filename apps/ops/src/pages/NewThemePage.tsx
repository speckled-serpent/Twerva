import { useState, type FormEvent, type ReactElement } from "react";

import { createTheme } from "../api/client";
import type { AdvertisementType, ThemeReadResponse } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import { useCanWriteOps } from "../session/OpsSessionContext";

export interface NewThemePageProps {
  onCreated: (createdTheme: ThemeReadResponse) => void;
  onCancel: () => void;
}

/**
 * Create Theme tab: save a carousel theme name. Does not render slides.
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
  const [actionError, setActionError] = useState<unknown>(null);
  const [isBusy, setIsBusy] = useState<boolean>(false);
  const trimmedThemeName: string = themeName.trim();
  const canCreate: boolean = canWrite && !isBusy && trimmedThemeName !== "";

  const handleCreateTheme = async (formEvent: FormEvent): Promise<void> => {

    formEvent.preventDefault();

    if (trimmedThemeName === "") {
      setActionError(new Error("Theme name is required."));

      return;
    }

    setIsBusy(true);
    setActionError(null);

    try {
      const createdTheme: ThemeReadResponse = await createTheme({
        name: trimmedThemeName,
        advertisement_type: advertisementType,
      });

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
            Save a carousel theme. This form stores the name and advertisement
            type. Short video and visual editors come later.
          </p>
        </div>
        <button type="button" onClick={onCancel}>
          Back to Themes
        </button>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={actionError} />

      <form
        className="stack-form campaign-form"
        onSubmit={(formEvent: FormEvent): void => {
          void handleCreateTheme(formEvent);
        }}
      >
        <label>
          Theme name
          <input
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

        {canWrite && !isBusy && trimmedThemeName === "" ? (
          <p className="field-hint">Add a theme name before creating.</p>
        ) : null}
        <div className="button-row">
          <button type="submit" disabled={!canCreate}>
            {isBusy ? "Saving…" : "Create Theme"}
          </button>
          <button type="button" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </form>
    </section>
  );
}
