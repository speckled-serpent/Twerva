import type {
  BackgroundKind,
  SkeletonGradient,
  SkeletonPatchRequest,
  SkeletonReadResponse,
} from "../api/types.ts";
import { gradientProblem, normalizeHexColor } from "./skeletonColors.ts";

export interface SkeletonGradientStopDraft {
  offset: string;
  color: string;
}

export interface SkeletonFrameDraft {
  backgroundKind: BackgroundKind;
  backgroundColor: string;
  gradientAngle: string;
  gradientStops: SkeletonGradientStopDraft[];
  backgroundAssetRef: string;
  pageMargin: string;
  elementGap: string;
  elementMargin: string;
}

/**
 * Return the name-only defaults: paper color, spacing 96 / 0 / 0.
 *
 * @returns A frame draft that matches a name-only create
 */
export function emptySkeletonFrameDraft(): SkeletonFrameDraft {

  const frameDraft: SkeletonFrameDraft = {
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
 * Return the frame draft for a stored skeleton.
 *
 * @param skeleton - Skeleton loaded from the API
 * @returns Editable frame fields
 */
export function frameDraftFromSkeleton(skeleton: SkeletonReadResponse): SkeletonFrameDraft {

  const storedGradient: SkeletonGradient | null = skeleton.background_gradient;
  const unsortedStops: SkeletonGradientStopDraft[] = storedGradient === null
    ? [
        { offset: "0", color: "" },
        { offset: "1", color: "" },
      ]
    : storedGradient.stops.map((stop: SkeletonGradient["stops"][number]): SkeletonGradientStopDraft => {

        const stopDraft: SkeletonGradientStopDraft = {
          offset: String(stop.offset),
          color: stop.color,
        };

        return stopDraft;
      });
  const gradientStops: SkeletonGradientStopDraft[] = [...unsortedStops].sort(
    (leftStop: SkeletonGradientStopDraft, rightStop: SkeletonGradientStopDraft): number => {

      return Number(leftStop.offset) - Number(rightStop.offset);
    },
  );
  const frameDraft: SkeletonFrameDraft = {
    backgroundKind: skeleton.background_kind,
    backgroundColor: skeleton.background_color ?? "",
    gradientAngle: storedGradient === null ? "" : String(storedGradient.angle_deg),
    gradientStops,
    backgroundAssetRef: skeleton.background_asset_ref ?? "",
    pageMargin: String(skeleton.page_margin),
    elementGap: String(skeleton.element_gap),
    elementMargin: String(skeleton.element_margin),
  };

  return frameDraft;
}

/**
 * Build the frame payload for create or patch.
 *
 * @param frameDraft - Current frame fields
 * @returns Spacing and the payload for the selected kind
 */
export function skeletonPatchFromFrameDraft(frameDraft: SkeletonFrameDraft): SkeletonPatchRequest {

  const pageMargin: number | null = parseWholeNumber(frameDraft.pageMargin);
  const elementGap: number | null = parseWholeNumber(frameDraft.elementGap);
  const elementMargin: number | null = parseWholeNumber(frameDraft.elementMargin);

  if (pageMargin === null || elementGap === null || elementMargin === null) {
    throw new Error(
      "Page margin, element gap, and element margin must be whole numbers.",
    );
  }

  const skeletonPatchRequest: SkeletonPatchRequest = {
    background_kind: frameDraft.backgroundKind,
    page_margin: pageMargin,
    element_gap: elementGap,
    element_margin: elementMargin,
  };

  if (frameDraft.backgroundKind === "color") {
    skeletonPatchRequest.background_color = normalizeHexColor(frameDraft.backgroundColor);

    return skeletonPatchRequest;
  }

  if (frameDraft.backgroundKind === "gradient") {
    skeletonPatchRequest.background_gradient = gradientFromDraft(frameDraft);

    return skeletonPatchRequest;
  }

  skeletonPatchRequest.background_asset_ref = frameDraft.backgroundAssetRef;

  return skeletonPatchRequest;
}

/**
 * Return the frame error the preview should show, or null when the draft can render.
 *
 * @param frameDraft - Current frame fields
 * @returns The gradient or spacing sentence, or null
 */
export function frameDraftError(frameDraft: SkeletonFrameDraft): string | null {

  try {
    skeletonPatchFromFrameDraft(frameDraft);

    return null;
  } catch (caughtError: unknown) {
    const message: string = caughtError instanceof Error
      ? caughtError.message
      : String(caughtError);

    return message;
  }
}

function gradientFromDraft(frameDraft: SkeletonFrameDraft): SkeletonGradient | null {

  const problem: string | null = gradientProblem(
    frameDraft.gradientAngle,
    frameDraft.gradientStops,
  );

  if (problem !== null) {
    throw new Error(problem);
  }

  const stops: SkeletonGradient["stops"] = frameDraft.gradientStops.map(
    (stopDraft: SkeletonGradientStopDraft): SkeletonGradient["stops"][number] => {

      return {
        offset: Number(stopDraft.offset),
        color: normalizeHexColor(stopDraft.color),
      };
    },
  );
  const gradient: SkeletonGradient = {
    angle_deg: Number(frameDraft.gradientAngle),
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
