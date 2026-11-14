import type { AccountCreateRequest, Platform } from "../api/types";

/** Label for the profile-key input. The API key stays on the server. */
export const AYRSHARE_PROFILE_KEY_LABEL: string =
  "Ayrshare profile key. The API key stays on the server.";

/**
 * Fields the create form has collected.
 */
export interface AccountCreateDraft {
  clusterId: string;
  platform: Platform;
  handle: string;
  cadenceCapPerDay: number | null;
  profileKey: string;
}

/**
 * Build the create body. A filled profile key is sent. A blank field is null.
 *
 * @param draft - The create form
 * @returns The request body
 */
export function accountCreateRequestFromDraft(draft: AccountCreateDraft): AccountCreateRequest {

  const createRequest: AccountCreateRequest = {
    cluster_id: draft.clusterId,
    platform: draft.platform,
    handle: draft.handle,
    cadence_cap_per_day: draft.cadenceCapPerDay,
    external_account_id: accountProfileKeyPatchValue(draft.profileKey),
  };

  return createRequest;
}

/**
 * Value stored by Save. Blank becomes null.
 *
 * @param rawValue - The input text
 * @returns The stripped key, or null
 */
export function accountProfileKeyPatchValue(rawValue: string): string | null {

  const trimmedProfileKey: string = rawValue.trim();

  if (trimmedProfileKey === "") {
    return null;
  }

  return trimmedProfileKey;
}

/**
 * Text shown in the accounts table for the profile key.
 *
 * @param profileKey - The stored key, or null
 * @returns The key, or an em dash when it is empty
 */
export function accountProfileKeyText(profileKey: string | null): string {

  if (profileKey === null || profileKey === "") {
    return "—";
  }

  return profileKey;
}

/**
 * Whether Save can be pressed.
 *
 * @param canWrite - True for an admin
 * @param isBusy - True while a request is in flight
 * @returns True when an admin can save
 */
export function accountProfileKeySaveEnabled(canWrite: boolean, isBusy: boolean): boolean {

  return canWrite && !isBusy;
}
