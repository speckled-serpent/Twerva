import type { ArtifactSlide } from "../api/types";

/**
 * Coerce `artifact.slides` JSON into typed slide objects.
 *
 * @param slides - Raw slides list from the API
 * @returns Slides that have at least role and text
 */
export function readArtifactSlides(slides: ArtifactSlide[] | unknown[] | null): ArtifactSlide[] {

  if (!Array.isArray(slides)) {
    return [];
  }

  const parsedSlides: ArtifactSlide[] = [];

  for (const slide of slides) {

    if (slide === null || typeof slide !== "object") {
      continue;
    }

    const slideRecord: Record<string, unknown> = slide as Record<string, unknown>;
    const roleValue: unknown = slideRecord.role;
    const textValue: unknown = slideRecord.text;
    const assetReferenceValue: unknown = slideRecord.asset_ref;

    if (typeof roleValue !== "string" || typeof textValue !== "string") {
      continue;
    }

    const parsedSlide: ArtifactSlide = {
      role: roleValue,
      text: textValue,
      asset_ref: typeof assetReferenceValue === "string" ? assetReferenceValue : null,
    };

    parsedSlides.push(parsedSlide);
  }

  return parsedSlides;
}
