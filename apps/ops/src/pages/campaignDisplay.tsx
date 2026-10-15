import type { ReactElement } from "react";

import type { CampaignStatus, CampaignType, Platform } from "../api/types";

export type CampaignLifecycleAction = "start" | "pause" | "resume" | "finish";

const CAMPAIGN_STATUS_LABELS: Record<CampaignStatus, string> = {
  ready: "Ready",
  running: "Running",
  paused: "Paused",
  finished: "Finished",
};

const CAMPAIGN_TYPE_LABELS: Record<CampaignType, string> = {
  spotmu: "Spotmu",
  spotmu_test: "Spotmu - test",
  other: "Other",
};

const CAMPAIGN_LIFECYCLE_ACTION_LABELS: Record<CampaignLifecycleAction, string> = {
  start: "Start",
  pause: "Pause",
  resume: "Resume",
  finish: "Finish",
};

const CAMPAIGN_LIFECYCLE_ACTION_PAST_LABELS: Record<CampaignLifecycleAction, string> = {
  start: "Started",
  pause: "Paused",
  resume: "Resumed",
  finish: "Finished",
};

/**
 * Return the operator-facing label for a stored campaign type.
 *
 * @param campaignType - Stored campaign type
 * @returns Spotmu / Spotmu - test / Other
 */
export function campaignTypeLabel(campaignType: CampaignType): string {

  const typeLabel: string = CAMPAIGN_TYPE_LABELS[campaignType];

  return typeLabel;
}

/**
 * Return whether Create campaign requires a linked social account.
 *
 * @param campaignType - Selected campaign type
 * @returns True only for production Spotmu
 */
export function campaignTypeRequiresLinkedAccount(campaignType: CampaignType): boolean {

  const requiresLinkedAccount: boolean = campaignType === "spotmu";

  return requiresLinkedAccount;
}

/**
 * Return the operator-facing label for a stored campaign status.
 *
 * @param campaignStatus - Stored lifecycle value
 * @returns Ready / Running / Paused / Finished
 */
export function campaignStatusLabel(campaignStatus: CampaignStatus): string {

  const statusLabel: string = CAMPAIGN_STATUS_LABELS[campaignStatus];

  return statusLabel;
}

/**
 * Return the button label for a lifecycle action.
 *
 * @param lifecycleAction - start / pause / resume / finish
 * @returns Title-case action name
 */
export function campaignLifecycleActionLabel(
  lifecycleAction: CampaignLifecycleAction,
): string {

  const actionLabel: string = CAMPAIGN_LIFECYCLE_ACTION_LABELS[lifecycleAction];

  return actionLabel;
}

/**
 * Return the past-tense label used in status banners.
 *
 * @param lifecycleAction - start / pause / resume / finish
 * @returns Started / Paused / Resumed / Finished
 */
export function campaignLifecycleActionPastLabel(
  lifecycleAction: CampaignLifecycleAction,
): string {

  const actionPastLabel: string = CAMPAIGN_LIFECYCLE_ACTION_PAST_LABELS[lifecycleAction];

  return actionPastLabel;
}

/**
 * Return the lifecycle actions that are legal from this status.
 *
 * @param campaignStatus - Current stored status
 * @returns Actions the write-role operator may run
 */
export function listAllowedCampaignLifecycleActions(
  campaignStatus: CampaignStatus,
): CampaignLifecycleAction[] {

  if (campaignStatus === "ready") {
    return ["start"];
  }

  if (campaignStatus === "running") {
    return ["pause", "finish"];
  }

  if (campaignStatus === "paused") {
    return ["resume", "finish"];
  }

  return [];
}

/**
 * Format platform enum values for a table cell.
 *
 * @param platforms - Instagram / TikTok list
 * @returns Comma-separated platforms, or an em dash
 */
export function formatCampaignPlatforms(platforms: Platform[]): string {

  if (platforms.length === 0) {
    return "—";
  }

  return platforms.join(", ");
}

/**
 * Format a campaign timestamp as UTC `YYYY-MM-DD HH:MM:SS`.
 *
 * @param createdAt - ISO timestamp from the API
 * @returns Display string
 */
export function formatCampaignTimestamp(createdAt: string): string {

  const parsedDate: Date = new Date(createdAt);

  if (Number.isNaN(parsedDate.getTime())) {
    return createdAt;
  }

  return parsedDate.toISOString().replace("T", " ").slice(0, 19);
}

interface CampaignStatusBadgeProps {
  campaignStatus: CampaignStatus;
}

/**
 * Colored status pill with a human label.
 *
 * @param props - Stored campaign status
 * @returns A status badge
 */
export function CampaignStatusBadge({
  campaignStatus,
}: CampaignStatusBadgeProps): ReactElement {

  const statusLabel: string = campaignStatusLabel(campaignStatus);

  return (
    <span className={`campaign-status-badge is-${campaignStatus}`}>{statusLabel}</span>
  );
}
