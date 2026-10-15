import { useEffect, useState, type FormEvent, type ReactElement } from "react";

import { createAlbum, listThemes } from "../api/client";
import type { SourceReadResponse, ThemeReadResponse } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import { useCanWriteOps } from "../session/OpsSessionContext";
import { createSourceFieldError } from "./createSource";

export interface NewSourcePageProps {
  onCreated: (createdSource: SourceReadResponse) => void;
  onCancel: () => void;
}

/**
 * Create Source tab: a name and a required theme, then open the source.
 *
 * @param props - Success and cancel navigation callbacks
 * @returns The create-source form
 */
export function NewSourcePage({ onCreated, onCancel }: NewSourcePageProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [sourceName, setSourceName] = useState<string>("");
  const [themeId, setThemeId] = useState<string>("");
  const [themes, setThemes] = useState<ThemeReadResponse[]>([]);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [saveError, setSaveError] = useState<unknown>(null);
  const [isSaving, setIsSaving] = useState<boolean>(false);

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadThemes = async (): Promise<void> => {

      try {
        const loadedThemes: ThemeReadResponse[] = await listThemes();

        if (isCancelled) {
          return;
        }

        setThemes(loadedThemes);
        setLoadError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setLoadError(caughtError);
      }
    };

    if (canWrite) {
      void loadThemes();
    }

    return (): void => {
      isCancelled = true;
    };
  }, [canWrite]);

  const handleCreate = async (submitEvent: FormEvent<HTMLFormElement>): Promise<void> => {
    submitEvent.preventDefault();

    if (!canWrite || isSaving) {
      return;
    }

    const fieldError: string | null = createSourceFieldError(sourceName, themeId);

    if (fieldError !== null) {
      setSaveError(new Error(fieldError));

      return;
    }

    setIsSaving(true);
    setSaveError(null);

    try {
      const createdSource: SourceReadResponse = await createAlbum({
        name: sourceName.trim(),
        theme_id: themeId,
      });

      onCreated(createdSource);
    } catch (caughtError: unknown) {
      setSaveError(caughtError);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>Create Source</h1>
          <p className="lede">
            A source needs a name and a theme. After this, it opens so you can add units.
          </p>
        </div>
        <button type="button" onClick={onCancel}>
          Back to Sources
        </button>
      </div>
      <ReadOnlyNotice />
      {canWrite ? (
        <form
          id="create-source-form"
          className="stack-form"
          onSubmit={(submitEvent: FormEvent<HTMLFormElement>): void => {
            void handleCreate(submitEvent);
          }}
        >
          <ErrorBanner error={loadError} />
          <label>
            Name
            <input
              id="create-source-name"
              value={sourceName}
              onChange={(changeEvent): void => {
                setSourceName(changeEvent.target.value);
              }}
            />
          </label>
          <label>
            Theme
            <select
              id="create-source-theme"
              value={themeId}
              onChange={(changeEvent): void => {
                setThemeId(changeEvent.target.value);
              }}
            >
              <option value="">Choose a theme</option>
              {themes.map((theme: ThemeReadResponse): ReactElement => (
                <option key={theme.id} value={theme.id}>
                  {theme.name}
                </option>
              ))}
            </select>
          </label>
          <p className="field-hint">The theme is required. Units stay in the simple editor for now.</p>
          <ErrorBanner error={saveError} />
          <div className="button-row">
            <button id="create-source-submit" type="submit" disabled={isSaving || themes.length === 0}>
              {isSaving ? "Creating…" : "Create source"}
            </button>
            <button type="button" onClick={onCancel} disabled={isSaving}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <p>Creating a source is an admin action.</p>
      )}
    </section>
  );
}
