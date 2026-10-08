import type { ReactElement } from "react";

import type {
  BackgroundKind,
  ThemeGradient,
  ThemePatchRequest,
  ThemeReadResponse,
  ThemeStatus,
} from "../api/types";

export interface ThemeGradientStopDraft {
  offset: string;
  color: string;
}

export interface ThemeFrameDraft {
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

export interface ThemeFrameFieldsProps {
  frameDraft: ThemeFrameDraft;
  onDraftChange: (nextDraft: ThemeFrameDraft) => void;
  disabled: boolean;
}

const BACKGROUND_KIND_OPTIONS: { value: BackgroundKind; label: string }[] = [
  { value: "color", label: "Color" },
  { value: "gradient", label: "Gradient" },
  { value: "picture", label: "Picture" },
  { value: "texture", label: "Texture" },
];

/**
 * Frame controls shared by Create Theme and the open theme.
 *
 * @param props - Current draft, change handler, and disabled flag
 * @returns The frame fieldset
 */
export function ThemeFrameFields({
  frameDraft,
  onDraftChange,
  disabled,
}: ThemeFrameFieldsProps): ReactElement {

  return (
    <fieldset className="form-fieldset" disabled={disabled}>
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

            onDraftChange({ ...frameDraft, status: nextStatus });
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

            onDraftChange({ ...frameDraft, backgroundKind: nextKind });
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
              onDraftChange({
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
        <ThemeGradientFields frameDraft={frameDraft} onDraftChange={onDraftChange} />
      ) : null}
      {frameDraft.backgroundKind === "picture" || frameDraft.backgroundKind === "texture" ? (
        <label>
          Background asset ref
          <input
            value={frameDraft.backgroundAssetRef}
            onChange={(changeEvent): void => {
              onDraftChange({
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
            onDraftChange({ ...frameDraft, pageMargin: changeEvent.target.value });
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
            onDraftChange({ ...frameDraft, elementGap: changeEvent.target.value });
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
            onDraftChange({ ...frameDraft, elementMargin: changeEvent.target.value });
          }}
        />
      </label>
    </fieldset>
  );
}

/**
 * Return the name-only defaults: Draft, paper color, spacing 96 / 0 / 0.
 *
 * @returns A frame draft that matches a name-only create
 */
export function emptyThemeFrameDraft(): ThemeFrameDraft {

  const frameDraft: ThemeFrameDraft = {
    status: "draft",
    backgroundKind: "color",
    backgroundColor: "#F6F1E8",
    gradientAngle: "",
    gradientStops: [
      { offset: "0", color: "" },
      { offset: "1", color: "" },
    ],
    backgroundAssetRef: "",
    pageMargin: "96",
    elementGap: "0",
    elementMargin: "0",
  };

  return frameDraft;
}

/**
 * Return the frame draft for a stored theme.
 *
 * @param theme - Theme loaded from the API
 * @returns Editable frame fields
 */
export function frameDraftFromTheme(theme: ThemeReadResponse): ThemeFrameDraft {

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

/**
 * Build the frame payload for create or patch.
 *
 * @param frameDraft - Current frame fields
 * @returns Status, spacing, and the payload for the selected kind
 */
export function themePatchFromFrameDraft(frameDraft: ThemeFrameDraft): ThemePatchRequest {

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
