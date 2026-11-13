import assert from "node:assert/strict";

import {
  listMissingCampaignCreateLabels,
  readCampaignCreateRequirements,
} from "./src/pages/campaignCreate.ts";

const readyWithoutInterest = readCampaignCreateRequirements(
  "Spring",
  "skeleton-1",
  "carousel-1",
  ["instagram"],
  ["account-1"],
  true,
);
const missingPlatform = readCampaignCreateRequirements(
  "Spring",
  "skeleton-1",
  "carousel-1",
  [],
  ["account-1"],
  true,
);
const spotmuTestWithoutAccount = readCampaignCreateRequirements(
  "Spring",
  "skeleton-1",
  "carousel-1",
  ["instagram"],
  [],
  false,
);

assert.deepEqual(listMissingCampaignCreateLabels(readyWithoutInterest), []);
assert.equal(
  listMissingCampaignCreateLabels(missingPlatform).includes("at least one Spotmu interest"),
  false,
);
assert.deepEqual(listMissingCampaignCreateLabels(missingPlatform), [
  "at least one platform",
]);
assert.deepEqual(listMissingCampaignCreateLabels(spotmuTestWithoutAccount), []);
assert.equal(
  listMissingCampaignCreateLabels(
    readCampaignCreateRequirements(
      "Spring",
      "skeleton-1",
      "carousel-1",
      ["instagram"],
      [],
      true,
    ),
  ).includes("at least one account"),
  true,
);
