import type { CampaignPostResultsRead } from "../api/types";

/** Shown when the cross-campaign list has no rows. */
export const POSTS_EMPTY: string = "No posts yet.";

/** Shown when a timeline row has no campaign. */
export const EARLIER_QUEUE_NAME: string = "Earlier queue";

/**
 * The Run rail. One list replaces Queue, Schedule, and Results.
 */
export const RUN_NAV_ITEMS: { pageId: "posts"; label: "Posts" }[] = [
  { pageId: "posts", label: "Posts" },
];

/**
 * Status word for one timeline row.
 *
 * @param status - Stored timeline status
 * @returns Upcoming, Posted, or Failed
 */
export function timelinePostStatusLabel(status: string): string {

  if (status === "upcoming") {
    return "Upcoming";
  }

  if (status === "posted") {
    return "Posted";
  }

  if (status === "failed") {
    return "Failed";
  }

  return status;
}

/**
 * Campaign name for one timeline row.
 *
 * A post job that was never on a campaign reads as Earlier queue.
 *
 * @param campaignName - Name from the timeline row, or null
 * @returns The campaign name, or Earlier queue
 */
export function timelineCampaignName(campaignName: string | null): string {

  if (campaignName === null) {
    return EARLIER_QUEUE_NAME;
  }

  return campaignName;
}

/**
 * Result counts for one timeline row.
 *
 * @param results - Latest snapshot, or null when none was recorded
 * @returns The counts sentence, or null when there are no results
 */
export function timelineResultCounts(results: CampaignPostResultsRead | null): string | null {

  if (results === null) {
    return null;
  }

  const countsText: string = [
    `${formatResultCount(results.views)} views`,
    `${formatResultCount(results.likes)} likes`,
    `${formatResultCount(results.comments)} comments`,
    `${formatResultCount(results.shares)} shares`,
  ].join(", ");

  return countsText;
}

function formatResultCount(count: number | null): string {

  if (count === null) {
    return "—";
  }

  return String(count);
}
