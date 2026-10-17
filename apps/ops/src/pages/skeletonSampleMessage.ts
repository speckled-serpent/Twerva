import type { SkeletonElementBand, SkeletonSampleOverlap, SkeletonSampleResponse } from "../api/types";

const BAND_LABELS: Record<SkeletonElementBand, string> = {
  top: "Top",
  middle: "Middle",
  bottom: "Bottom",
};

/**
 * Banner text for a blocked sample or live preview.
 *
 * @param sample - Preview response, including overlaps
 * @returns The reason a reader can scan, with band names for overlap
 */
export function sampleBlockMessage(sample: SkeletonSampleResponse): string {

  if (sample.block_reason === "overlap") {
    const pairText: string = overlapPairText(sample.overlaps);
    const namedPairs: string = pairText !== "" ? pairText : (sample.detail ?? "");

    return joinBlockMessage("overlap", namedPairs);
  }

  if (sample.block_reason === "missing_asset") {

    return joinBlockMessage("missing asset", sample.detail ?? "");
  }

  if (sample.block_reason === "measure_error") {
    const detailText: string = (sample.detail ?? "").trim();

    if (detailText !== "") {
      return detailText;
    }

    return "Blocked: measure error.";
  }

  return "Blocked preview.";
}

function overlapPairText(overlaps: SkeletonSampleOverlap[]): string {

  const pairLabels: string[] = overlaps.map((overlap: SkeletonSampleOverlap): string => {

    return `${BAND_LABELS[overlap.band_a]} overlaps ${BAND_LABELS[overlap.band_b]}`;
  });

  return pairLabels.join(" ");
}

function joinBlockMessage(reasonLabel: string, detailText: string): string {

  const trimmedDetail: string = detailText.trim();

  if (trimmedDetail === "") {
    return `Blocked: ${reasonLabel}.`;
  }

  return `Blocked: ${reasonLabel}. ${trimmedDetail}`;
}
