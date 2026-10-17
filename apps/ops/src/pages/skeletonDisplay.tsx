import type { AdvertisementType } from "../api/types";

const ADVERTISEMENT_TYPE_LABELS: Record<AdvertisementType, string> = {
  carousel: "Carousel",
};

/**
 * Return the operator-facing label for a stored advertisement type.
 *
 * @param advertisementType - Stored advertisement type
 * @returns Carousel
 */
export function advertisementTypeLabel(advertisementType: AdvertisementType): string {

  const typeLabel: string = ADVERTISEMENT_TYPE_LABELS[advertisementType];

  return typeLabel;
}

/**
 * Format a skeleton timestamp as UTC `YYYY-MM-DD HH:MM:SS`.
 *
 * @param createdAt - ISO timestamp from the API
 * @returns Display string
 */
export function formatSkeletonTimestamp(createdAt: string): string {

  const parsedDate: Date = new Date(createdAt);

  if (Number.isNaN(parsedDate.getTime())) {
    return createdAt;
  }

  return parsedDate.toISOString().replace("T", " ").slice(0, 19);
}

/**
 * Return a template key for display, or an em dash when unset.
 *
 * @param templateKey - Optional carousel generator id
 * @returns The key, or —
 */
export function formatSkeletonTemplateKey(templateKey: string | null): string {

  if (templateKey === null || templateKey.trim() === "") {
    return "—";
  }

  return templateKey;
}
