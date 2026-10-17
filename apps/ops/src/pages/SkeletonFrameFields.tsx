import type { ReactElement } from "react";

import type { BackgroundKind } from "../api/types";
import { SkeletonAssetAlbumField } from "./SkeletonAssetAlbumField";
import {
  gradientDefaultsIfEmpty,
  normalizeHexColor,
  offsetFromPercentInput,
  percentTextFromOffset,
  type GradientStopDraft,
} from "./skeletonColors";
import type { SkeletonFrameDraft, SkeletonGradientStopDraft } from "./skeletonFrameDraft";

export {
  emptySkeletonFrameDraft,
  frameDraftError,
  frameDraftFromSkeleton,
  skeletonPatchFromFrameDraft,
} from "./skeletonFrameDraft";
export type { SkeletonFrameDraft, SkeletonGradientStopDraft } from "./skeletonFrameDraft";

export interface SkeletonFrameFieldsProps {
  frameDraft: SkeletonFrameDraft;
  onDraftChange: (nextDraft: SkeletonFrameDraft) => void;
  disabled: boolean;
}

const BACKGROUND_KIND_OPTIONS: { value: BackgroundKind; label: string }[] = [
  { value: "color", label: "Color" },
  { value: "gradient", label: "Gradient" },
  { value: "picture", label: "Picture" },
];

/**
 * Background and margin controls shared by Create Skeleton and the open skeleton.
 *
 * @param props - Current draft, change handler, and disabled flag
 * @returns The background fieldset and the margins fieldset
 */
export function SkeletonFrameFields({
  frameDraft,
  onDraftChange,
  disabled,
}: SkeletonFrameFieldsProps): ReactElement {

  return (
    <>
    <fieldset className="form-fieldset" disabled={disabled}>
      <legend>Background</legend>
      <label>
        Type
        <select
          aria-label="Background type"
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
        <SkeletonGradientFields frameDraft={frameDraft} onDraftChange={onDraftChange} />
      ) : null}
      {frameDraft.backgroundKind === "picture" ? (
        <SkeletonAssetAlbumField
          idPrefix="background-image"
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
    </fieldset>
    <fieldset className="form-fieldset" disabled={disabled}>
      <legend>Margins</legend>
      <div className="margin-row">
        <label>
          Page margin
          <input
            className="margin-input"
            type="number"
            min={0}
            step={1}
            aria-label="Page margin"
            value={frameDraft.pageMargin}
            onChange={(changeEvent): void => {
              onDraftChange({ ...frameDraft, pageMargin: changeEvent.target.value });
            }}
          />
        </label>
        <label>
          Element gap
          <input
            className="margin-input"
            type="number"
            min={0}
            step={1}
            aria-label="Element gap"
            value={frameDraft.elementGap}
            onChange={(changeEvent): void => {
              onDraftChange({ ...frameDraft, elementGap: changeEvent.target.value });
            }}
          />
        </label>
        <label>
          Element margin
          <input
            className="margin-input"
            type="number"
            min={0}
            step={1}
            aria-label="Element margin"
            value={frameDraft.elementMargin}
            onChange={(changeEvent): void => {
              onDraftChange({ ...frameDraft, elementMargin: changeEvent.target.value });
            }}
          />
        </label>
      </div>
    </fieldset>
    </>
  );
}

interface SkeletonGradientFieldsProps {
  frameDraft: SkeletonFrameDraft;
  onDraftChange: (nextDraft: SkeletonFrameDraft) => void;
}

function SkeletonGradientFields({
  frameDraft,
  onDraftChange,
}: SkeletonGradientFieldsProps): ReactElement {

  const offsets: number[] = frameDraft.gradientStops.map(
    (stopDraft: SkeletonGradientStopDraft): number => Number(stopDraft.offset),
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
        (stopDraft: SkeletonGradientStopDraft, stopIndex: number): ReactElement => {
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
                      const nextStops: SkeletonGradientStopDraft[] = replaceStop(
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
                    const nextStops: SkeletonGradientStopDraft[] = replaceStop(
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
                    const nextStops: SkeletonGradientStopDraft[] = replaceStop(
                      frameDraft.gradientStops,
                      stopIndex,
                      { ...stopDraft, color: changeEvent.target.value },
                    );

                    onDraftChange({ ...frameDraft, gradientStops: nextStops });
                  }}
                  onBlur={(blurEvent): void => {
                    const nextStops: SkeletonGradientStopDraft[] = replaceStop(
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
                    const nextStops: SkeletonGradientStopDraft[] = [];

                    frameDraft.gradientStops.forEach(
                      (currentStop: SkeletonGradientStopDraft, currentIndex: number): void => {

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
            const nextStops: SkeletonGradientStopDraft[] = [
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

function frameDraftForKind(
  frameDraft: SkeletonFrameDraft,
  nextKind: BackgroundKind,
): SkeletonFrameDraft {

  const nextDraft: SkeletonFrameDraft = { ...frameDraft, backgroundKind: nextKind };

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

  const filledDraft: SkeletonFrameDraft = {
    ...nextDraft,
    gradientAngle: defaults.angle,
    gradientStops: defaults.stops,
  };

  return filledDraft;
}

function replaceStop(
  stops: SkeletonGradientStopDraft[],
  stopIndex: number,
  nextStop: SkeletonGradientStopDraft,
): SkeletonGradientStopDraft[] {

  const nextStops: SkeletonGradientStopDraft[] = stops.map(
    (currentStop: SkeletonGradientStopDraft, currentIndex: number): SkeletonGradientStopDraft => {

      if (currentIndex !== stopIndex) {
        return currentStop;
      }

      return nextStop;
    },
  );

  return nextStops;
}

function isBackgroundKind(value: string): value is BackgroundKind {

  return (
    value === "picture"
    || value === "color"
    || value === "gradient"
  );
}
