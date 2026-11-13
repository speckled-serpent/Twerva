import type {
  AssembledCarouselReadResponse,
  CampaignPostRead,
  CampaignReadResponse,
  CarouselAssemblyReadResponse,
} from "../api/types";

/** Shown when the open campaign has no posts. */
export const CAMPAIGN_POSTS_EMPTY: string =
  "No posts yet. Add an assembled carousel from this campaign.";

/** Shown when the bound carousel has no assembly for this generation. */
export const CAMPAIGN_TIMELINE_NEEDS_ASSEMBLY: string =
  "Assemble this carousel on Final before adding a post.";

/** Accessible name when a reader cannot add a post. */
export const ADD_CAMPAIGN_POST_READER_NAME: string =
  "Add to timeline. A reader cannot add a post.";

/**
 * One assembled carousel in the add form.
 *
 * A blocked carousel is not a choice. Its label still says Blocked
 * when the form shows it disabled.
 */
export interface CampaignPostCarouselOption {
  id: string;
  label: string;
  enabled: boolean;
}

/**
 * Build a datetime-local value one hour from now.
 *
 * The old Schedule page used this same one-hour default.
 *
 * @returns A local datetime string for an input
 */
export function defaultScheduledForValue(): string {

  const scheduledDate: Date = new Date();
  scheduledDate.setHours(scheduledDate.getHours() + 1);

  return formatDatetimeLocal(scheduledDate);
}

/**
 * Format a stored timestamp for a datetime-local input.
 *
 * @param scheduledFor - ISO timestamp from the post
 * @returns A local datetime string, or empty when the timestamp is unusable
 */
export function scheduledForInputValue(scheduledFor: string): string {

  const scheduledDate: Date = new Date(scheduledFor);

  if (Number.isNaN(scheduledDate.getTime())) {
    return "";
  }

  return formatDatetimeLocal(scheduledDate);
}

/**
 * Whether Add to timeline can be pressed.
 *
 * An admin needs a bound carousel, one linked account, and at least
 * one unblocked assembled carousel. A reader stays disabled. A null
 * assembly has no choice, so the button stays disabled.
 *
 * @param canWrite - True for an admin
 * @param carouselId - The campaign's bound carousel, or null
 * @param accountCount - Linked accounts on the campaign
 * @param assembly - The current generation's assembly, or null
 * @returns True when the button can be pressed
 */
export function campaignPostAddEnabled(
  canWrite: boolean,
  carouselId: string | null,
  accountCount: number,
  assembly: CarouselAssemblyReadResponse | null,
): boolean {

  if (!canWrite) {
    return false;
  }

  if (carouselId === null || accountCount < 1) {
    return false;
  }

  return campaignPostCarouselChoices(assembly).length > 0;
}

/**
 * Accessible name for Add to timeline.
 *
 * A reader hears why the button is disabled. An admin hears the label.
 *
 * @param canWrite - True for an admin
 * @returns The accessible name
 */
export function addCampaignPostAccessibleName(canWrite: boolean): string {

  if (!canWrite) {
    return ADD_CAMPAIGN_POST_READER_NAME;
  }

  return "Add to timeline";
}

/**
 * Assembled carousels for the add form, blocked ones disabled.
 *
 * Labels use the stored position. The current assembly is already the
 * current generation.
 *
 * @param assembly - The carousel's assembly, or null
 * @returns Options in position order
 */
export function campaignPostCarouselOptions(
  assembly: CarouselAssemblyReadResponse | null,
): CampaignPostCarouselOption[] {

  if (assembly === null) {
    return [];
  }

  const orderedCarousels: AssembledCarouselReadResponse[] = [...assembly.carousels];
  orderedCarousels.sort(
    (left: AssembledCarouselReadResponse, right: AssembledCarouselReadResponse): number =>
      left.position - right.position,
  );

  return orderedCarousels.map(
    (assembledCarousel: AssembledCarouselReadResponse): CampaignPostCarouselOption => {
      const carouselNumber: number = assembledCarousel.position + 1;
      const label: string = assembledCarousel.blocked
        ? `Carousel ${carouselNumber} Blocked`
        : `Carousel ${carouselNumber}`;

      return {
        id: assembledCarousel.id,
        label,
        enabled: !assembledCarousel.blocked,
      };
    },
  );
}

/**
 * Assembled carousels an operator can place.
 *
 * Blocked carousels are left out.
 *
 * @param assembly - The carousel's assembly, or null
 * @returns Enabled options in position order
 */
export function campaignPostCarouselChoices(
  assembly: CarouselAssemblyReadResponse | null,
): CampaignPostCarouselOption[] {

  return campaignPostCarouselOptions(assembly).filter(
    (option: CampaignPostCarouselOption): boolean => option.enabled,
  );
}

/**
 * Posts in scheduled time order, then id.
 *
 * @param posts - Posts stored on the campaign
 * @returns A new list, soonest first
 */
export function orderedCampaignPosts(posts: CampaignPostRead[]): CampaignPostRead[] {

  const orderedPosts: CampaignPostRead[] = [...posts];
  orderedPosts.sort((left: CampaignPostRead, right: CampaignPostRead): number => {
    const timeCompare: number = left.scheduled_for.localeCompare(right.scheduled_for);

    if (timeCompare !== 0) {
      return timeCompare;
    }

    return left.id.localeCompare(right.id);
  });

  return orderedPosts;
}

/**
 * The campaign after a successful add.
 *
 * The placed post is listed with the posts already on the campaign.
 *
 * @param campaign - The open campaign
 * @param placedPost - The post the API stored
 * @returns The campaign the detail should show next
 */
export function campaignTimelineAfterAdd(
  campaign: CampaignReadResponse,
  placedPost: CampaignPostRead,
): CampaignReadResponse {

  return campaignTimelineWithPost(campaign, placedPost);
}

/**
 * Replace one post, or append it when it is new.
 *
 * @param campaign - The open campaign
 * @param updatedPost - The post returned by the API
 * @returns The campaign the detail should show next
 */
export function campaignTimelineWithPost(
  campaign: CampaignReadResponse,
  updatedPost: CampaignPostRead,
): CampaignReadResponse {

  const remainingPosts: CampaignPostRead[] = campaign.posts.filter(
    (post: CampaignPostRead): boolean => post.id !== updatedPost.id,
  );
  const nextCampaign: CampaignReadResponse = {
    ...campaign,
    posts: orderedCampaignPosts([...remainingPosts, updatedPost]),
  };

  return nextCampaign;
}

/**
 * The campaign after an upcoming post is removed.
 *
 * @param campaign - The open campaign
 * @param postId - Post that was deleted
 * @returns The campaign the detail should show next
 */
export function campaignTimelineWithoutPost(
  campaign: CampaignReadResponse,
  postId: string,
): CampaignReadResponse {

  const nextCampaign: CampaignReadResponse = {
    ...campaign,
    posts: campaign.posts.filter((post: CampaignPostRead): boolean => post.id !== postId),
  };

  return nextCampaign;
}

/**
 * Whether the row shows Publish.
 *
 * Upcoming and failed can be published. Posted does not.
 *
 * @param status - Stored campaign post status
 * @returns True when Publish is on the row
 */
export function campaignPostOffersPublish(status: string): boolean {

  return status === "upcoming" || status === "failed";
}

/**
 * Whether the row can change its time or be removed.
 *
 * @param status - Stored campaign post status
 * @returns True for an upcoming post
 */
export function campaignPostCanChangeTime(status: string): boolean {

  return status === "upcoming";
}

/**
 * Whether the row offers sample results.
 *
 * Only a posted mock publish can record them.
 *
 * @param status - Stored campaign post status
 * @param platformPostId - Id returned by the publisher
 * @returns True when the stub button is shown
 */
export function campaignPostOffersStubMetrics(
  status: string,
  platformPostId: string | null,
): boolean {

  if (status !== "posted" || platformPostId === null) {
    return false;
  }

  return platformPostId.startsWith("mock-");
}

/**
 * Format a local date as a datetime-local value.
 *
 * @param scheduledDate - Date already shifted to the intended clock time
 * @returns `YYYY-MM-DDTHH:mm`
 */
function formatDatetimeLocal(scheduledDate: Date): string {

  const yearText: string = String(scheduledDate.getFullYear());
  const monthText: string = String(scheduledDate.getMonth() + 1).padStart(2, "0");
  const dayText: string = String(scheduledDate.getDate()).padStart(2, "0");
  const hourText: string = String(scheduledDate.getHours()).padStart(2, "0");
  const minuteText: string = String(scheduledDate.getMinutes()).padStart(2, "0");

  return `${yearText}-${monthText}-${dayText}T${hourText}:${minuteText}`;
}
