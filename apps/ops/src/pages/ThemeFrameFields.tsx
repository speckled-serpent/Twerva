import type { ReactElement } from "react";

import type {
  BackgroundKind,
  ThemeGradient,
  ThemePatchRequest,
  ThemeReadResponse,
  ThemeStatus,
} from "../api/types";
import { ThemeAssetAlbumField } from "./ThemeAssetAlbumField";
import {
  gradientDefaultsIfEmpty,
  gradientProblem,
  normalizeHexColor,
  offsetFromPercentInput,
  percentTextFromOffset,
  type GradientStopDraft,
} from "./themeColors";

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

            onDraftChange(frameDraftForKind(frameDraft, nextKind));
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
            onBlur={(blurEvent): void => {
              onDraftChange({
                ...frameDraft,
                backgroundColor: normalizeHexColor(blurEvent.currentTarget.value),
              });
            }}
            placeholder="#F6F1E8"
            spellCheck={false}
          />
        </label>
      ) : null}
      {frameDraft.backgroundKind === "color" ? (
        <p className="field-hint">
          3 or 6 hex digits, with or without #. Blank clears the color.
        </p>
      ) : null}
      {frameDraft.backgroundKind === "gradient" ? (
        <ThemeGradientFields frameDraft={frameDraft} onDraftChange={onDraftChange} />
      ) : null}
      {frameDraft.backgroundKind === "picture" ? (
        <ThemeAssetAlbumField
          label="Background image"
          assetRef={frameDraft.backgroundAssetRef}
          disabled={disabled}
          onAssetRefChange={(nextAssetRef: string): void => {
            onDraftChange({
              ...frameDraft,
              backgroundAssetRef: nextAssetRef,
            });
          }}
        />
      ) : null}
      {frameDraft.backgroundKind === "texture" ? (
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
      {frameDraft.backgroundKind === "texture" ? (
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
  const unsortedStops: ThemeGradientStopDraft[] = storedGradient === null
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
  const gradientStops: ThemeGradientStopDraft[] = [...unsortedStops].sort(
    (leftStop: ThemeGradientStopDraft, rightStop: ThemeGradientStopDraft): number => {

      return Number(leftStop.offset) - Number(rightStop.offset);
    },
  );
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
    themePatchRequest.background_color = normalizeHexColor(frameDraft.backgroundColor);

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

  const offsets: number[] = frameDraft.gradientStops.map(
    (stopDraft: ThemeGradientStopDraft): number => Number(stopDraft.offset),
  );
  const angleNumber: number = Number(frameDraft.gradientAngle);
  const sliderAngle: number = Number.isFinite(angleNumber)
    ? Math.min(360, Math.max(0, angleNumber))
    : 0;

  return (
    <>
      <div className="slider-field">
        <label className="slider-number-label">
          Angle
          <input
            className="slider-number"
            type="number"
            min={0}
            max={360}
            step={1}
            value={frameDraft.gradientAngle}
            onChange={(changeEvent): void => {
              onDraftChange({ ...frameDraft, gradientAngle: changeEvent.target.value });
            }}
          />
        </label>
        <input
          className="slider-range"
          type="range"
          min={0}
          max={360}
          step={1}
          value={sliderAngle}
          aria-label="Gradient angle"
          onChange={(changeEvent): void => {
            onDraftChange({ ...frameDraft, gradientAngle: changeEvent.target.value });
          }}
        />
      </div>
      <p className="field-hint">0 points up. 90 points right. 180 points down.</p>
      <p className="field-hint">
        An offset is where that color sits along the gradient, from 0% at the
        start to 100% at the end.
      </p>
      {frameDraft.gradientStops.map(
        (stopDraft: ThemeGradientStopDraft, stopIndex: number): ReactElement => {
          const previousOffset: number = stopIndex === 0 ? 0 : offsets[stopIndex - 1];
          const followingOffset: number = stopIndex === frameDraft.gradientStops.length - 1
            ? 1
            : offsets[stopIndex + 1];
          const rawMin: number = (Number.isFinite(previousOffset) ? previousOffset : 0) * 100;
          const rawMax: number = (Number.isFinite(followingOffset) ? followingOffset : 1) * 100;
          const neighborMin: number = Math.max(0, Math.min(rawMin, 100));
          const neighborMax: number = Math.max(neighborMin, Math.min(rawMax, 100));
          const storedPercent: number = Number(stopDraft.offset) * 100;
          const sliderPercent: number = Number.isFinite(storedPercent)
            ? Math.min(neighborMax, Math.max(neighborMin, storedPercent))
            : neighborMin;

          return (
            <div className="gradient-stop" key={stopIndex}>
              <div className="slider-field">
                <label className="slider-number-label">
                  Stop {stopIndex + 1}
                  <input
                    className="slider-number"
                    type="number"
                    min={0}
                    max={100}
                    step={1}
                    value={percentTextFromOffset(stopDraft.offset)}
                    aria-label={`Stop ${stopIndex + 1} offset percent`}
                    onChange={(changeEvent): void => {
                      const nextOffset: string = offsetFromPercentInput(
                        offsets,
                        stopIndex,
                        changeEvent.target.value,
                      );
                      const nextStops: ThemeGradientStopDraft[] = replaceStop(
                        frameDraft.gradientStops,
                        stopIndex,
                        { ...stopDraft, offset: nextOffset },
                      );

                      onDraftChange({ ...frameDraft, gradientStops: nextStops });
                    }}
                  />
                </label>
                <input
                  className="slider-range"
                  type="range"
                  min={neighborMin}
                  max={neighborMax}
                  step={1}
                  value={sliderPercent}
                  aria-label={`Stop ${stopIndex + 1} offset`}
                  onChange={(changeEvent): void => {
                    const nextOffset: string = offsetFromPercentInput(
                      offsets,
                      stopIndex,
                      changeEvent.target.value,
                    );
                    const nextStops: ThemeGradientStopDraft[] = replaceStop(
                      frameDraft.gradientStops,
                      stopIndex,
                      { ...stopDraft, offset: nextOffset },
                    );

                    onDraftChange({ ...frameDraft, gradientStops: nextStops });
                  }}
                />
              </div>
              <label>
                Stop {stopIndex + 1} color
                <input
                  value={stopDraft.color}
                  onChange={(changeEvent): void => {
                    const nextStops: ThemeGradientStopDraft[] = replaceStop(
                      frameDraft.gradientStops,
                      stopIndex,
                      { ...stopDraft, color: changeEvent.target.value },
                    );

                    onDraftChange({ ...frameDraft, gradientStops: nextStops });
                  }}
                  onBlur={(blurEvent): void => {
                    const nextStops: ThemeGradientStopDraft[] = replaceStop(
                      frameDraft.gradientStops,
                      stopIndex,
                      { ...stopDraft, color: normalizeHexColor(blurEvent.currentTarget.value) },
                    );

                    onDraftChange({ ...frameDraft, gradientStops: nextStops });
                  }}
                  placeholder="#4A4A4A"
                  spellCheck={false}
                />
              </label>
              <div className="button-row">
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
            </div>
          );
        },
      )}
      <div className="button-row">
        <button
          type="button"
          onClick={(): void => {
            const nextStops: ThemeGradientStopDraft[] = [
              ...frameDraft.gradientStops,
              { offset: "1", color: "" },
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

  const problem: string | null = gradientProblem(
    frameDraft.gradientAngle,
    frameDraft.gradientStops,
  );

  if (problem !== null) {
    throw new Error(problem);
  }

  const stops: ThemeGradient["stops"] = frameDraft.gradientStops.map(
    (stopDraft: ThemeGradientStopDraft): ThemeGradient["stops"][number] => {

      return {
        offset: Number(stopDraft.offset),
        color: normalizeHexColor(stopDraft.color),
      };
    },
  );
  const gradient: ThemeGradient = {
    angle_deg: Number(frameDraft.gradientAngle),
    stops,
  };

  return gradient;
}

/**
 * Return the frame error the preview should show, or null when the draft can render.
 *
 * @param frameDraft - Current frame fields
 * @returns The gradient or spacing sentence, or null
 */
export function frameDraftError(frameDraft: ThemeFrameDraft): string | null {

  try {
    themePatchFromFrameDraft(frameDraft);

    return null;
  } catch (caughtError: unknown) {
    const message: string = caughtError instanceof Error
      ? caughtError.message
      : String(caughtError);

    return message;
  }
}

function frameDraftForKind(
  frameDraft: ThemeFrameDraft,
  nextKind: BackgroundKind,
): ThemeFrameDraft {

  const nextDraft: ThemeFrameDraft = { ...frameDraft, backgroundKind: nextKind };

  if (nextKind !== "gradient") {
    return nextDraft;
  }

  const defaults: { angle: string; stops: GradientStopDraft[] } | null = gradientDefaultsIfEmpty(
    frameDraft.gradientAngle,
    frameDraft.gradientStops,
  );

  if (defaults === null) {
    return nextDraft;
  }

  const filledDraft: ThemeFrameDraft = {
    ...nextDraft,
    gradientAngle: defaults.angle,
    gradientStops: defaults.stops,
  };

  return filledDraft;
}

function replaceStop(
  stops: ThemeGradientStopDraft[],
  stopIndex: number,
  nextStop: ThemeGradientStopDraft,
): ThemeGradientStopDraft[] {

  const nextStops: ThemeGradientStopDraft[] = stops.map(
    (currentStop: ThemeGradientStopDraft, currentIndex: number): ThemeGradientStopDraft => {

      if (currentIndex !== stopIndex) {
        return currentStop;
      }

      return nextStop;
    },
  );

  return nextStops;
}

function parseWholeNumber(rawValue: string): number | null {

  const trimmedValue: string = rawValue.trim();

  if (!/^-?\d+$/.test(trimmedValue)) {
    return null;
  }

  const parsedValue: number = Number(trimmedValue);

  return parsedValue;
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
