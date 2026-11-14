import assert from "node:assert/strict";

import type {
  AssembledCarouselReadResponse,
  AssembledFrameReadResponse,
  CampaignPostRead,
  CampaignReadResponse,
  CarouselAssemblyReadResponse,
} from "./src/api/types.ts";
import {
  CAMPAIGN_POSTS_EMPTY,
  campaignPostAddEnabled,
  campaignPostCarouselChoices,
  campaignPostFailureDetail,
  campaignPostOffersPublish,
  campaignTimelineAfterAdd,
} from "./src/pages/campaignTimeline.ts";

const openFrame: AssembledFrameReadResponse = {
  id: "frame-1",
  position: 0,
  slide_id: "slide-1",
  album_image_id: null,
  blocked: false,
  block_reason: null,
  block_detail: null,
};
const blockedFrame: AssembledFrameReadResponse = {
  id: "frame-2",
  position: 0,
  slide_id: "slide-2",
  album_image_id: null,
  blocked: true,
  block_reason: "missing_asset",
  block_detail: "Missing file.",
};
const openCarousel: AssembledCarouselReadResponse = {
  id: "group-open",
  position: 0,
  status: "draft",
  caption: "Harbor",
  cta_url: null,
  blocked: false,
  frames: [openFrame],
};
const blockedCarousel: AssembledCarouselReadResponse = {
  id: "group-blocked",
  position: 1,
  status: "draft",
  caption: "Harbor",
  cta_url: null,
  blocked: true,
  frames: [blockedFrame],
};
const assembly: CarouselAssemblyReadResponse = {
  id: "assembly-1",
  generation_number: 1,
  slide_count: 5,
  carousels: [blockedCarousel, openCarousel],
};
const campaign: CampaignReadResponse = {
  id: "campaign-1",
  name: "Harbor",
  slug: "harbor",
  hashtag: "#harbor",
  campaign_type: "spotmu",
  advertisement_type: "carousel",
  status: "ready",
  platforms: ["instagram"],
  skeleton_id: "skeleton-1",
  carousel_id: "carousel-1",
  skeleton_name: "Paper",
  carousel_name: "Harbor",
  account_count: 1,
  interest_count: 0,
  accounts: [{ id: "account-1", platform: "instagram", handle: "spotmu" }],
  interests: [],
  carousels: [],
  posts: [],
  created_at: "2026-11-13T15:00:00Z",
  updated_at: "2026-11-13T15:00:00Z",
  created_by: null,
};
const placedPost: CampaignPostRead = {
  id: "post-1",
  campaign_id: "campaign-1",
  carousel_id: "carousel-1",
  generation_number: 1,
  assembled_carousel_id: "group-open",
  account_id: "account-1",
  platform: "instagram",
  handle: "spotmu",
  status: "upcoming",
  scheduled_for: "2026-11-13T16:00:00Z",
  published_at: null,
  platform_post_id: null,
  platform_post_url: null,
  last_error: null,
  caption: "Harbor",
  cta_url: null,
  blocked: false,
  frames: [],
  results: null,
};

const choices = campaignPostCarouselChoices(assembly);
const nextCampaign: CampaignReadResponse = campaignTimelineAfterAdd(campaign, placedPost);

assert.equal(campaignPostAddEnabled(true, "carousel-1", 1, assembly), true);
assert.equal(campaignPostAddEnabled(false, "carousel-1", 1, assembly), false);
assert.equal(campaignPostAddEnabled(true, "carousel-1", 1, null), false);
assert.equal(choices.some((choice) => choice.id === blockedCarousel.id), false);
assert.deepEqual(choices.map((choice) => choice.label), ["Carousel 1"]);
assert.equal(CAMPAIGN_POSTS_EMPTY, "No posts yet. Add an assembled carousel from this campaign.");
assert.deepEqual(nextCampaign.posts.map((post) => post.id), [placedPost.id]);
assert.equal(nextCampaign.hashtag, campaign.hashtag);
assert.equal(nextCampaign.posts[0].caption, "Harbor");
assert.equal(campaignPostOffersPublish("posted"), false);
assert.equal(campaignPostOffersPublish("upcoming"), true);
assert.equal(campaignPostOffersPublish("failed"), true);

const failureSentence: string = "Ayrshare post failed with HTTP 400: Instagram is not linked.";
const failedPost: CampaignPostRead = {
  ...placedPost,
  status: "failed",
  last_error: failureSentence,
};
const postedWithStaleError: CampaignPostRead = {
  ...placedPost,
  status: "posted",
  last_error: failureSentence,
};
const failedWithoutError: CampaignPostRead = {
  ...placedPost,
  status: "failed",
  last_error: null,
};

assert.equal(campaignPostFailureDetail(failedPost), failureSentence);
assert.equal(campaignPostFailureDetail(postedWithStaleError), null);
assert.equal(campaignPostFailureDetail(failedWithoutError), null);
