import type { Platform } from "../api/types";

export interface CampaignCreateRequirements {
  hasName: boolean;
  hasSkeleton: boolean;
  hasCarousel: boolean;
  hasPlatform: boolean;
  hasAccount: boolean;
}

/**
 * Return which create fields are filled. A Spotmu interest is not required.
 *
 * @param campaignName - Name typed on the form
 * @param selectedSkeletonId - Chosen skeleton id, or empty
 * @param selectedCarouselId - Chosen carousel id, or empty
 * @param selectedPlatforms - Platforms added so far
 * @param selectedAccountIds - Linked account ids
 * @param accountsAreRequired - True for a production Spotmu campaign
 * @returns The filled-field flags the submit button reads
 */
export function readCampaignCreateRequirements(
  campaignName: string,
  selectedSkeletonId: string,
  selectedCarouselId: string,
  selectedPlatforms: Platform[],
  selectedAccountIds: string[],
  accountsAreRequired: boolean,
): CampaignCreateRequirements {

  const campaignCreateRequirements: CampaignCreateRequirements = {
    hasName: campaignName.trim() !== "",
    hasSkeleton: selectedSkeletonId !== "",
    hasCarousel: selectedCarouselId !== "",
    hasPlatform: selectedPlatforms.length > 0,
    hasAccount: !accountsAreRequired || selectedAccountIds.length > 0,
  };

  return campaignCreateRequirements;
}

/**
 * Return the operator-facing gaps that still block Create campaign.
 *
 * @param campaignCreateRequirements - Filled-field flags
 * @returns Missing labels, in form order
 */
export function listMissingCampaignCreateLabels(
  campaignCreateRequirements: CampaignCreateRequirements,
): string[] {

  const missingLabels: string[] = [];

  if (!campaignCreateRequirements.hasSkeleton) {
    missingLabels.push("a skeleton");
  }

  if (!campaignCreateRequirements.hasCarousel) {
    missingLabels.push("a carousel");
  }

  if (!campaignCreateRequirements.hasName) {
    missingLabels.push("a campaign name");
  }

  if (!campaignCreateRequirements.hasPlatform) {
    missingLabels.push("at least one platform");
  }

  if (!campaignCreateRequirements.hasAccount) {
    missingLabels.push("at least one account");
  }

  return missingLabels;
}
