export interface GradientStopDraft {
  offset: string;
  color: string;
}

export const GRADIENT_NEEDS_SECOND_COLOR: string = "Can't draw gradient: add a second color";
export const GRADIENT_OFFSET_RANGE: string = "Stop offsets must be between 0% and 100%";
export const GRADIENT_ANGLE_RANGE: string = "Angle must be 0-360";

export const DEFAULT_GRADIENT_ANGLE: string = "180";
export const DEFAULT_GRADIENT_STOPS: GradientStopDraft[] = [
  { offset: "0", color: "#4A4A4A" },
  { offset: "1", color: "#BDBDBD" },
];

const HEX_BODY_PATTERN: RegExp = /^[0-9A-Fa-f]+$/;
const STORED_HEX_PATTERN: RegExp = /^#[0-9A-F]{6}$/;

/**
 * Turn 3- or 6-digit hex into `#RRGGBB`. A blank stays blank.
 *
 * A leading `#` is optional. Values that are not hex are returned trimmed
 * so the caller can still name the problem.
 *
 * @param rawValue - What the operator typed
 * @returns `#RRGGBB`, `""`, or the trimmed original
 */
export function normalizeHexColor(rawValue: string): string {

  const trimmedValue: string = rawValue.trim();

  if (trimmedValue === "") {
    return "";
  }

  const hexBody: string = trimmedValue.startsWith("#")
    ? trimmedValue.slice(1)
    : trimmedValue;

  if (!HEX_BODY_PATTERN.test(hexBody)) {
    return trimmedValue;
  }

  if (hexBody.length === 3) {
    const expandedBody: string = hexBody
      .split("")
      .map((character: string): string => character + character)
      .join("");

    return `#${expandedBody.toUpperCase()}`;
  }

  if (hexBody.length === 6) {
    return `#${hexBody.toUpperCase()}`;
  }

  return trimmedValue;
}

/**
 * Return the gradient sentence for this draft, or null when it can be drawn.
 *
 * @param angleText - Angle field, degrees
 * @param stops - Stop drafts. `offset` is 0 through 1
 * @returns The same sentence the preview API returns
 */
export function gradientProblem(
  angleText: string,
  stops: GradientStopDraft[],
): string | null {

  const trimmedAngle: string = angleText.trim();
  const angleValue: number = Number(trimmedAngle);

  if (trimmedAngle === "" || !Number.isFinite(angleValue) || angleValue < 0 || angleValue > 360) {
    return GRADIENT_ANGLE_RANGE;
  }

  if (stops.length < 2) {
    return GRADIENT_NEEDS_SECOND_COLOR;
  }

  for (let stopIndex: number = 0; stopIndex < stops.length; stopIndex += 1) {
    const stopDraft: GradientStopDraft = stops[stopIndex];
    const trimmedOffset: string = stopDraft.offset.trim();
    const offsetValue: number = Number(trimmedOffset);

    if (
      trimmedOffset === ""
      || !Number.isFinite(offsetValue)
      || offsetValue < 0
      || offsetValue > 1
    ) {
      return GRADIENT_OFFSET_RANGE;
    }

    const storedColor: string = normalizeHexColor(stopDraft.color);

    if (!STORED_HEX_PATTERN.test(storedColor)) {
      return `Stop ${stopIndex + 1} color isn't a valid hex color`;
    }
  }

  return null;
}

/**
 * Keep one stop between its neighbors. The list is not reordered.
 *
 * @param offsets - Current offsets, already in order
 * @param index - Stop being moved
 * @param nextOffset - Requested offset before the neighbor limit
 * @returns The offset to store
 */
export function clampStopOffset(
  offsets: number[],
  index: number,
  nextOffset: number,
): number {

  const lowerNeighbor: number = index <= 0 ? 0 : offsets[index - 1];
  const upperNeighbor: number = index >= offsets.length - 1 ? 1 : offsets[index + 1];
  const lowerBound: number = Math.max(0, lowerNeighbor);
  const upperBound: number = Math.min(1, upperNeighbor);
  const clampedOffset: number = Math.min(upperBound, Math.max(lowerBound, nextOffset));

  return clampedOffset;
}

/**
 * Fill the default gradient when the draft has no angle and no stop colors.
 *
 * @param angleText - Current angle field
 * @param stops - Current stops
 * @returns The default pair, or null when the operator already edited the gradient
 */
export function gradientDefaultsIfEmpty(
  angleText: string,
  stops: GradientStopDraft[],
): { angle: string; stops: GradientStopDraft[] } | null {

  const hasAngle: boolean = angleText.trim() !== "";
  const hasColor: boolean = stops.some(
    (stopDraft: GradientStopDraft): boolean => stopDraft.color.trim() !== "",
  );

  if (hasAngle || hasColor) {
    return null;
  }

  const defaults: { angle: string; stops: GradientStopDraft[] } = {
    angle: DEFAULT_GRADIENT_ANGLE,
    stops: DEFAULT_GRADIENT_STOPS.map((stopDraft: GradientStopDraft): GradientStopDraft => {
      return { offset: stopDraft.offset, color: stopDraft.color };
    }),
  };

  return defaults;
}

/**
 * Show an API offset (0 through 1) as a percent string.
 *
 * @param offsetText - Stored offset
 * @returns Percent text for the number box
 */
export function percentTextFromOffset(offsetText: string): string {

  const trimmedOffset: string = offsetText.trim();

  if (trimmedOffset === "") {
    return "";
  }

  const offsetValue: number = Number(trimmedOffset);

  if (!Number.isFinite(offsetValue)) {
    return trimmedOffset;
  }

  const percentValue: number = Math.round(offsetValue * 1000) / 10;

  return String(percentValue);
}

/**
 * Store a percent the operator typed. Values outside 0–100 stay out of range
 * so the form can name that problem. Values inside the range clamp to the
 * neighboring stops.
 *
 * @param offsets - Current offsets
 * @param index - Stop being edited
 * @param percentText - Number box text
 * @returns Offset text to store (0 through 1, or outside when the percent is)
 */
export function offsetFromPercentInput(
  offsets: number[],
  index: number,
  percentText: string,
): string {

  const trimmedPercent: string = percentText.trim();

  if (trimmedPercent === "") {
    return "";
  }

  const percentValue: number = Number(trimmedPercent);

  if (!Number.isFinite(percentValue)) {
    return trimmedPercent;
  }

  if (percentValue < 0 || percentValue > 100) {
    return String(percentValue / 100);
  }

  const clampedOffset: number = clampStopOffset(offsets, index, percentValue / 100);

  return String(clampedOffset);
}
