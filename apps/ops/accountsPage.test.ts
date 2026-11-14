import assert from "node:assert/strict";

import {
  AYRSHARE_PROFILE_KEY_LABEL,
  accountCreateRequestFromDraft,
  accountProfileKeySaveEnabled,
  accountProfileKeyText,
} from "./src/pages/accountsPage.ts";

const filled = accountCreateRequestFromDraft({
  clusterId: "cluster-1",
  platform: "instagram",
  handle: "brendan",
  cadenceCapPerDay: null,
  profileKey: "  profile-key-1  ",
});
const empty = accountCreateRequestFromDraft({
  clusterId: "cluster-1",
  platform: "instagram",
  handle: "brendan",
  cadenceCapPerDay: null,
  profileKey: "   ",
});

assert.equal(filled.external_account_id, "profile-key-1");
assert.equal(empty.external_account_id, null);
assert.equal(Object.hasOwn(filled, "password"), false);
assert.equal(Object.hasOwn(filled, "AYRSHARE_API_KEY"), false);
assert.equal(accountProfileKeyText("profile-key-1"), "profile-key-1");
assert.equal(accountProfileKeyText(null), "—");
assert.equal(accountProfileKeySaveEnabled(false, false), false);
assert.equal(accountProfileKeySaveEnabled(true, false), true);
assert.equal(
  AYRSHARE_PROFILE_KEY_LABEL,
  "Ayrshare profile key. The API key stays on the server.",
);
