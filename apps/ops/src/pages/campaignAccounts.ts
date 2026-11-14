import type { AccountReadResponse, Platform } from "../api/types";

/**
 * Accounts that can be attached: matching platform, not linked yet.
 *
 * @param accounts - Every account the operator can see
 * @param campaignPlatforms - Platforms already on the campaign
 * @param linkedAccountIds - Accounts already on the campaign
 * @returns The attach choices, in the given account order
 */
export function campaignAccountsAvailableToAttach(
  accounts: AccountReadResponse[],
  campaignPlatforms: Platform[],
  linkedAccountIds: string[],
): AccountReadResponse[] {

  const linkedIds: Set<string> = new Set(linkedAccountIds);
  const allowedPlatforms: Set<Platform> = new Set(campaignPlatforms);
  const choices: AccountReadResponse[] = accounts.filter(
    (account: AccountReadResponse): boolean =>
      allowedPlatforms.has(account.platform) && !linkedIds.has(account.id),
  );

  return choices;
}

/**
 * Whether attach and detach can be pressed.
 *
 * A reader sees the list with both controls disabled.
 *
 * @param canWrite - True for an admin
 * @param isBusy - True while a request is in flight
 * @returns True when an admin can attach or detach
 */
export function campaignAccountControlsEnabled(canWrite: boolean, isBusy: boolean): boolean {

  return canWrite && !isBusy;
}
