import { useEffect, useState, type FormEvent, type ReactElement } from "react";

import { fetchThemeById, listThemes, patchTheme } from "../api/client";
import type {
  BackgroundKind,
  ThemeGradient,
  ThemePatchRequest,
  ThemeReadResponse,
  ThemeStatus,
} from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import { useCanWriteOps } from "../session/OpsSessionContext";
import { ThemeElementEditor } from "./ThemeElementEditor";
import {
  advertisementTypeLabel,
  formatThemeTemplateKey,
  formatThemeTimestamp,
} from "./themeDisplay";

export interface ThemesPageProps {
  statusMessage: string;
}

/**
 * Themes tab: list saved themes. Selecting a row opens the frame and elements.
 *
 * @param props - Banner shown after create
 * @returns The Themes list or detail
 */
export function ThemesPage({ statusMessage }: ThemesPageProps): ReactElement {

  const [themes, setThemes] = useState<ThemeReadResponse[]>([]);
  const [openedThemeId, setOpenedThemeId] = useState<string | null>(null);
  const [selectedTheme, setSelectedTheme] = useState<ThemeReadResponse | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadList = async (): Promise<void> => {

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

    void loadList();

    return (): void => {
      isCancelled = true;
    };
  }, []);

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    if (openedThemeId === null) {
      setSelectedTheme(null);

      return (): void => {
        isCancelled = true;
      };
    }

    const loadDetail = async (): Promise<void> => {

      try {
        const loadedTheme: ThemeReadResponse = await fetchThemeById(openedThemeId);

        if (isCancelled) {
          return;
        }

        setSelectedTheme(loadedTheme);
        setLoadError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setSelectedTheme(null);
        setLoadError(caughtError);
      }
    };

    void loadDetail();

    return (): void => {
      isCancelled = true;
    };
  }, [openedThemeId]);

  if (openedThemeId !== null) {
    return (
      <ThemeDetailView
        selectedTheme={selectedTheme}
        loadError={loadError}
        statusMessage={statusMessage}
        onBack={(): void => {
          setOpenedThemeId(null);
        }}
        onThemeSaved={(updatedTheme: ThemeReadResponse): void => {
          setSelectedTheme(updatedTheme);
          setThemes((currentThemes: ThemeReadResponse[]): ThemeReadResponse[] => {
            const nextThemes: ThemeReadResponse[] = currentThemes.map(
              (theme: ThemeReadResponse): ThemeReadResponse => {

                if (theme.id !== updatedTheme.id) {
                  return theme;
                }

                return updatedTheme;
              },
            );

            return nextThemes;
          });
        }}
      />
    );
  }

  return (
    <ThemeListView
      themes={themes}
      loadError={loadError}
      statusMessage={statusMessage}
      onSelectTheme={(themeId: string): void => {
        setOpenedThemeId(themeId);
      }}
    />
  );
}

interface ThemeListViewProps {
  themes: ThemeReadResponse[];
  loadError: unknown;
  statusMessage: string;
  onSelectTheme: (themeId: string) => void;
}

function ThemeListView({
  themes,
  loadError,
  statusMessage,
  onSelectTheme,
}: ThemeListViewProps): ReactElement {

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>Themes</h1>
          <p className="lede">
            Visual styling for carousels. Open a row for the saved record.
            Create lives on Create Theme.
          </p>
        </div>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}

      {loadError !== null ? null : themes.length === 0 ? (
        <p>No themes yet. Use Create Theme to save a carousel theme.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Advertisement type</th>
              <th>Created</th>
              <th>View</th>
            </tr>
          </thead>
          <tbody>
            {themes.map((theme: ThemeReadResponse): ReactElement => (
              <tr
                key={theme.id}
                className="clickable-row"
                onClick={(): void => {
                  onSelectTheme(theme.id);
                }}
              >
                <td>{theme.name}</td>
                <td>{advertisementTypeLabel(theme.advertisement_type)}</td>
                <td className="mono">{formatThemeTimestamp(theme.created_at)}</td>
                <td>
                  <button
                    type="button"
                    onClick={(clickEvent): void => {
                      clickEvent.stopPropagation();
                      onSelectTheme(theme.id);
                    }}
                  >
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

interface ThemeDetailViewProps {
  selectedTheme: ThemeReadResponse | null;
  loadError: unknown;
  statusMessage: string;
  onBack: () => void;
  onThemeSaved: (updatedTheme: ThemeReadResponse) => void;
}

interface ThemeGradientStopDraft {
  offset: string;
  color: string;
}

interface ThemeFrameDraft {
  status: ThemeStatus;
  backgroundKind: BackgroundKind;
  backgroundColor: string;
  gradientAngle: string;
  gradientStops: ThemeGradientStopDraft[];
  backgroundAssetRef: string;
  pageMargin: string;
  elementGap: string;
  elementMargin: string;
}

const BACKGROUND_KIND_OPTIONS: { value: BackgroundKind; label: string }[] = [
  { value: "color", label: "Color" },
  { value: "gradient", label: "Gradient" },
  { value: "picture", label: "Picture" },
  { value: "texture", label: "Texture" },
];

function ThemeDetailView({
  selectedTheme,
  loadError,
  statusMessage,
  onBack,
  onThemeSaved,
}: ThemeDetailViewProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [editedDraft, setEditedDraft] = useState<ThemeFrameDraft | null>(null);
  const [editedForKey, setEditedForKey] = useState<string | null>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [isBusy, setIsBusy] = useState<boolean>(false);
  const [saveMessage, setSaveMessage] = useState<string>("");
  const [saveMessageKey, setSaveMessageKey] = useState<string | null>(null);
  const themeKey: string | null = themeFrameKey(selectedTheme);
  const frameDraft: ThemeFrameDraft | null = frameDraftForTheme(
    selectedTheme,
    themeKey,
    editedDraft,
    editedForKey,
  );
  const visibleSaveMessage: string = saveMessageKey === themeKey ? saveMessage : "";
  const fieldsDisabled: boolean = !canWrite || isBusy;

  const rememberDraft = (nextDraft: ThemeFrameDraft): void => {

    if (themeKey === null) {
      return;
    }

    setEditedForKey(themeKey);
    setEditedDraft(nextDraft);
    setActionError(null);
  };

  const handleSaveFrame = async (formEvent: FormEvent): Promise<void> => {

    formEvent.preventDefault();

    if (!canWrite || selectedTheme === null || frameDraft === null) {
      return;
    }

    setIsBusy(true);
    setActionError(null);
    setSaveMessage("");

    try {
      const themePatchRequest: ThemePatchRequest = themePatchFromFrameDraft(frameDraft);
      await patchTheme(selectedTheme.id, themePatchRequest);
      const reloadedTheme: ThemeReadResponse = await fetchThemeById(selectedTheme.id);
      const reloadedKey: string | null = themeFrameKey(reloadedTheme);

      onThemeSaved(reloadedTheme);
      setEditedDraft(null);
      setEditedForKey(null);
      setSaveMessage("Frame saved.");
      setSaveMessageKey(reloadedKey);
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
          <h1>{selectedTheme === null ? "Theme" : selectedTheme.name}</h1>
          <p className="lede">
            Draft or Live, background, spacing, and full-width elements.
          </p>
        </div>
        <button type="button" onClick={onBack}>
          Back to list
        </button>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      <ErrorBanner error={actionError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}
      {visibleSaveMessage !== "" ? (
        <p className="status-banner">{visibleSaveMessage}</p>
      ) : null}

      {selectedTheme === null || frameDraft === null ? (
        loadError === null ? <p>Loading theme…</p> : null
      ) : (
        <>
          <dl className="campaign-detail-list">
            <dt>Name</dt>
            <dd>{selectedTheme.name}</dd>
            <dt>Slug</dt>
            <dd className="mono">{selectedTheme.slug}</dd>
            <dt>Advertisement type</dt>
            <dd>{advertisementTypeLabel(selectedTheme.advertisement_type)}</dd>
            <dt>Template</dt>
            <dd className="mono">{formatThemeTemplateKey(selectedTheme.template_key)}</dd>
            <dt>Created</dt>
            <dd className="mono">{formatThemeTimestamp(selectedTheme.created_at)}</dd>
            <dt>Updated</dt>
            <dd className="mono">{formatThemeTimestamp(selectedTheme.updated_at)}</dd>
          </dl>

          <form
            className="stack-form campaign-form"
            onSubmit={(formEvent: FormEvent): void => {
              void handleSaveFrame(formEvent);
            }}
          >
            <fieldset className="form-fieldset" disabled={fieldsDisabled}>
              <legend>Frame</legend>
              <label>
                Status
                <select
                  value={frameDraft.status}
                  onChange={(changeEvent): void => {
                    const nextStatus: string = changeEvent.target.value;

                    if (!isThemeStatus(nextStatus)) {
                      return;
                    }

                    rememberDraft({ ...frameDraft, status: nextStatus });
                  }}
                >
                  <option value="draft">Draft</option>
                  <option value="live">Live</option>
                </select>
              </label>
              <label>
                Background
                <select
                  value={frameDraft.backgroundKind}
                  onChange={(changeEvent): void => {
                    const nextKind: string = changeEvent.target.value;

                    if (!isBackgroundKind(nextKind)) {
                      return;
                    }

                    rememberDraft({ ...frameDraft, backgroundKind: nextKind });
                  }}
                >
                  {BACKGROUND_KIND_OPTIONS.map(
                    (option: { value: BackgroundKind; label: string }): ReactElement => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ),
                  )}
                </select>
              </label>
              {frameDraft.backgroundKind === "color" ? (
                <label>
                  Background color
                  <input
                    value={frameDraft.backgroundColor}
                    onChange={(changeEvent): void => {
                      rememberDraft({
                        ...frameDraft,
                        backgroundColor: changeEvent.target.value,
                      });
                    }}
                    placeholder="#F6F1E8"
                    spellCheck={false}
                  />
                </label>
              ) : null}
              {frameDraft.backgroundKind === "color" ? (
                <p className="field-hint"># plus six hex digits. Blank clears the color.</p>
              ) : null}
              {frameDraft.backgroundKind === "gradient" ? (
                <ThemeGradientFields
                  frameDraft={frameDraft}
                  onDraftChange={rememberDraft}
                />
              ) : null}
              {frameDraft.backgroundKind === "picture" || frameDraft.backgroundKind === "texture" ? (
                <label>
                  Background asset ref
                  <input
                    value={frameDraft.backgroundAssetRef}
                    onChange={(changeEvent): void => {
                      rememberDraft({
                        ...frameDraft,
                        backgroundAssetRef: changeEvent.target.value,
                      });
                    }}
                    placeholder="backgrounds/paper.png"
                    spellCheck={false}
                  />
                </label>
              ) : null}
              {frameDraft.backgroundKind === "picture" || frameDraft.backgroundKind === "texture" ? (
                <p className="field-hint">
                  Relative path ending in .svg, .png, .jpg, or .jpeg. No file upload.
                </p>
              ) : null}
              <label>
                Page margin
                <input
                  type="number"
                  min={0}
                  step={1}
                  value={frameDraft.pageMargin}
                  onChange={(changeEvent): void => {
                    rememberDraft({ ...frameDraft, pageMargin: changeEvent.target.value });
                  }}
                />
              </label>
              <label>
                Element gap
                <input
                  type="number"
                  min={0}
                  step={1}
                  value={frameDraft.elementGap}
                  onChange={(changeEvent): void => {
                    rememberDraft({ ...frameDraft, elementGap: changeEvent.target.value });
                  }}
                />
              </label>
              <label>
                Element margin
                <input
                  type="number"
                  min={0}
                  step={1}
                  value={frameDraft.elementMargin}
                  onChange={(changeEvent): void => {
                    rememberDraft({
                      ...frameDraft,
                      elementMargin: changeEvent.target.value,
                    });
                  }}
                />
              </label>
            </fieldset>
            <div className="button-row">
              <button type="submit" disabled={fieldsDisabled}>
                {isBusy ? "Saving…" : "Save frame"}
              </button>
            </div>
          </form>
          <ThemeElementEditor
            theme={selectedTheme}
            onThemeUpdated={onThemeSaved}
          />
        </>
      )}
    </section>
  );
}

interface ThemeGradientFieldsProps {
  frameDraft: ThemeFrameDraft;
  onDraftChange: (nextDraft: ThemeFrameDraft) => void;
}

function ThemeGradientFields({
  frameDraft,
  onDraftChange,
}: ThemeGradientFieldsProps): ReactElement {

  return (
    <>
      <label>
        Gradient angle
        <input
          type="number"
          min={0}
          max={360}
          step="any"
          value={frameDraft.gradientAngle}
          onChange={(changeEvent): void => {
            onDraftChange({ ...frameDraft, gradientAngle: changeEvent.target.value });
          }}
        />
      </label>
      <p className="field-hint">
        Degrees from 0 through 360. Blank leaves the gradient empty. 0 points up.
        90 points right.
      </p>
      {frameDraft.gradientStops.map(
        (stopDraft: ThemeGradientStopDraft, stopIndex: number): ReactElement => (
          <div className="inline-add-row" key={stopIndex}>
            <label>
              Stop {stopIndex + 1} offset
              <input
                type="number"
                min={0}
                max={1}
                step="any"
                value={stopDraft.offset}
                onChange={(changeEvent): void => {
                  const nextStops: ThemeGradientStopDraft[] = frameDraft.gradientStops.map(
                    (currentStop: ThemeGradientStopDraft, currentIndex: number): ThemeGradientStopDraft => {

                      if (currentIndex !== stopIndex) {
                        return currentStop;
                      }

                      return { ...currentStop, offset: changeEvent.target.value };
                    },
                  );

                  onDraftChange({ ...frameDraft, gradientStops: nextStops });
                }}
              />
            </label>
            <label>
              Stop {stopIndex + 1} color
              <input
                value={stopDraft.color}
                onChange={(changeEvent): void => {
                  const nextStops: ThemeGradientStopDraft[] = frameDraft.gradientStops.map(
                    (currentStop: ThemeGradientStopDraft, currentIndex: number): ThemeGradientStopDraft => {

                      if (currentIndex !== stopIndex) {
                        return currentStop;
                      }

                      return { ...currentStop, color: changeEvent.target.value };
                    },
                  );

                  onDraftChange({ ...frameDraft, gradientStops: nextStops });
                }}
                placeholder="#112233"
                spellCheck={false}
              />
            </label>
            <button
              type="button"
              onClick={(): void => {
                const nextStops: ThemeGradientStopDraft[] = [];

                frameDraft.gradientStops.forEach(
                  (currentStop: ThemeGradientStopDraft, currentIndex: number): void => {

                    if (currentIndex === stopIndex) {
                      return;
                    }

                    nextStops.push(currentStop);
                  },
                );

                onDraftChange({ ...frameDraft, gradientStops: nextStops });
              }}
            >
              Remove stop
            </button>
          </div>
        ),
      )}
      <div className="button-row">
        <button
          type="button"
          onClick={(): void => {
            const nextStops: ThemeGradientStopDraft[] = [
              ...frameDraft.gradientStops,
              { offset: "", color: "" },
            ];

            onDraftChange({ ...frameDraft, gradientStops: nextStops });
          }}
        >
          Add stop
        </button>
      </div>
    </>
  );
}

function themeFrameKey(theme: ThemeReadResponse | null): string | null {

  if (theme === null) {
    return null;
  }

  const frameKey: string = `${theme.id}:${theme.updated_at}`;

  return frameKey;
}

function frameDraftForTheme(
  theme: ThemeReadResponse | null,
  themeKey: string | null,
  editedDraft: ThemeFrameDraft | null,
  editedForKey: string | null,
): ThemeFrameDraft | null {

  if (theme === null) {
    return null;
  }

  if (editedDraft !== null && editedForKey === themeKey) {
    return editedDraft;
  }

  const frameDraft: ThemeFrameDraft = frameDraftFromTheme(theme);

  return frameDraft;
}

function frameDraftFromTheme(theme: ThemeReadResponse): ThemeFrameDraft {

  const storedGradient: ThemeGradient | null = theme.background_gradient;
  const gradientStops: ThemeGradientStopDraft[] = storedGradient === null
    ? [
        { offset: "0", color: "" },
        { offset: "1", color: "" },
      ]
    : storedGradient.stops.map((stop: ThemeGradient["stops"][number]): ThemeGradientStopDraft => {

        const stopDraft: ThemeGradientStopDraft = {
          offset: String(stop.offset),
          color: stop.color,
        };

        return stopDraft;
      });
  const frameDraft: ThemeFrameDraft = {
    status: theme.status,
    backgroundKind: theme.background_kind,
    backgroundColor: theme.background_color ?? "",
    gradientAngle: storedGradient === null ? "" : String(storedGradient.angle_deg),
    gradientStops,
    backgroundAssetRef: theme.background_asset_ref ?? "",
    pageMargin: String(theme.page_margin),
    elementGap: String(theme.element_gap),
    elementMargin: String(theme.element_margin),
  };

  return frameDraft;
}

function themePatchFromFrameDraft(frameDraft: ThemeFrameDraft): ThemePatchRequest {

  const pageMargin: number | null = parseWholeNumber(frameDraft.pageMargin);
  const elementGap: number | null = parseWholeNumber(frameDraft.elementGap);
  const elementMargin: number | null = parseWholeNumber(frameDraft.elementMargin);

  if (pageMargin === null || elementGap === null || elementMargin === null) {
    throw new Error(
      "Page margin, element gap, and element margin must be whole numbers.",
    );
  }

  const themePatchRequest: ThemePatchRequest = {
    status: frameDraft.status,
    background_kind: frameDraft.backgroundKind,
    page_margin: pageMargin,
    element_gap: elementGap,
    element_margin: elementMargin,
  };

  if (frameDraft.backgroundKind === "color") {
    themePatchRequest.background_color = frameDraft.backgroundColor;

    return themePatchRequest;
  }

  if (frameDraft.backgroundKind === "gradient") {
    themePatchRequest.background_gradient = gradientFromDraft(frameDraft);

    return themePatchRequest;
  }

  themePatchRequest.background_asset_ref = frameDraft.backgroundAssetRef;

  return themePatchRequest;
}

function gradientFromDraft(frameDraft: ThemeFrameDraft): ThemeGradient | null {

  const trimmedAngle: string = frameDraft.gradientAngle.trim();

  if (trimmedAngle === "") {
    return null;
  }

  if (!isDecimalText(trimmedAngle)) {
    throw new Error("Gradient angle must be a number.");
  }

  const stops: ThemeGradient["stops"] = frameDraft.gradientStops.map(
    (stopDraft: ThemeGradientStopDraft): ThemeGradient["stops"][number] => {

      const trimmedOffset: string = stopDraft.offset.trim();

      if (!isDecimalText(trimmedOffset)) {
        throw new Error("Each gradient stop offset must be a number.");
      }

      return {
        offset: Number(trimmedOffset),
        color: stopDraft.color.trim(),
      };
    },
  );
  const gradient: ThemeGradient = {
    angle_deg: Number(trimmedAngle),
    stops,
  };

  return gradient;
}

function parseWholeNumber(rawValue: string): number | null {

  const trimmedValue: string = rawValue.trim();

  if (!/^-?\d+$/.test(trimmedValue)) {
    return null;
  }

  const parsedValue: number = Number(trimmedValue);

  return parsedValue;
}

function isDecimalText(rawValue: string): boolean {

  return /^-?\d+(\.\d+)?$/.test(rawValue);
}

function isThemeStatus(value: string): value is ThemeStatus {

  return value === "draft" || value === "live";
}

function isBackgroundKind(value: string): value is BackgroundKind {

  return (
    value === "picture"
    || value === "color"
    || value === "gradient"
    || value === "texture"
  );
}
