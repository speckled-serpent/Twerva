import assert from "node:assert/strict";

import {
  EARLIER_QUEUE_NAME,
  POSTS_EMPTY,
  RUN_NAV_ITEMS,
  timelineCampaignName,
  timelinePostStatusLabel,
} from "./src/pages/postsPage.ts";

const runLabels: string[] = RUN_NAV_ITEMS.map((item) => item.label);

assert.deepEqual(RUN_NAV_ITEMS, [{ pageId: "posts", label: "Posts" }]);
assert.equal(runLabels.includes("Queue"), false);
assert.equal(runLabels.includes("Schedule"), false);
assert.equal(runLabels.includes("Results"), false);
assert.equal(timelinePostStatusLabel("upcoming"), "Upcoming");
assert.equal(timelinePostStatusLabel("posted"), "Posted");
assert.equal(timelinePostStatusLabel("failed"), "Failed");
assert.equal(timelineCampaignName(null), EARLIER_QUEUE_NAME);
assert.equal(timelineCampaignName(null), "Earlier queue");
assert.equal(POSTS_EMPTY, "No posts yet.");
