import type {
  BackgroundKind,
  ThemeGradient,
  ThemePatchRequest,
  ThemeReadResponse,
} from "../api/types.ts";
import { gradientProblem, normalizeHexColor } from "./themeColors.ts";

export interface ThemeGradientStopDraft {
  offset: string;
  color: string;
}

export interface ThemeFrameDraft {
  backgroundKind: BackgroundKind;
  backgroundColor: string;
  gradientAngle: string;
  gradientStops: ThemeGradientStopDraft[];
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
export function emptyThemeFrameDraft(): ThemeFrameDraft {

  const frameDraft: ThemeFrameDraft = {
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
 * @returns Spacing and the payload for the selected kind
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

function parseWholeNumber(rawValue: string): number | null {

  const trimmedValue: string = rawValue.trim();

  if (!/^-?\d+$/.test(trimmedValue)) {
    return null;
  }

  const parsedValue: number = Number(trimmedValue);

  return parsedValue;
}
