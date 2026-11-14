import assert from "node:assert/strict";

import type { AccountReadResponse } from "./src/api/types.ts";
import {
  campaignAccountControlsEnabled,
  campaignAccountsAvailableToAttach,
} from "./src/pages/campaignAccounts.ts";

const instagramAccount: AccountReadResponse = {
  id: "account-ig",
  cluster_id: "cluster-1",
  platform: "instagram",
  handle: "brendan",
  external_account_id: null,
  status: "active",
  cadence_cap_per_day: null,
  created_at: "2026-11-14T00:00:00Z",
  updated_at: "2026-11-14T00:00:00Z",
};
const tiktokAccount: AccountReadResponse = {
  ...instagramAccount,
  id: "account-tt",
  platform: "tiktok",
  handle: "brendan-tt",
};

const choices = campaignAccountsAvailableToAttach(
  [tiktokAccount, instagramAccount],
  ["instagram"],
  [],
);
const alreadyLinked = campaignAccountsAvailableToAttach(
  [instagramAccount],
  ["instagram"],
  [instagramAccount.id],
);

assert.deepEqual(choices.map((account) => account.id), ["account-ig"]);
assert.deepEqual(alreadyLinked, []);
assert.equal(campaignAccountControlsEnabled(true, false), true);
assert.equal(campaignAccountControlsEnabled(false, false), false);
assert.equal(campaignAccountControlsEnabled(true, true), false);
