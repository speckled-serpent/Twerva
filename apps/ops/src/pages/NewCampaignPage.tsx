import {
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type ReactElement,
} from "react";

import { createCampaign, listAccounts, searchSpotmuInterests } from "../api/client";
import type {
  AccountReadResponse,
  CampaignReadResponse,
  CampaignType,
  Platform,
  SpotmuInterestSearchHit,
} from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import { useCanWriteOps } from "../session/OpsSessionContext";
import { campaignTypeRequiresLinkedAccount } from "./campaignDisplay";

interface SelectedInterest {
  slug: string;
  title: string;
  spotmu_interest_id: string | null;
}

const AVAILABLE_PLATFORMS: Platform[] = ["instagram", "tiktok"];

export interface NewCampaignPageProps {
  onCreated: (createdCampaign: CampaignReadResponse) => void;
  onCancel: () => void;
}

/**
 * New Campaign tab: save a Ready definition. Does not start the campaign.
 *
 * @param props - Success and cancel navigation callbacks
 * @returns The New Campaign form
 */
export function NewCampaignPage({ onCreated, onCancel }: NewCampaignPageProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [accounts, setAccounts] = useState<AccountReadResponse[]>([]);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [isBusy, setIsBusy] = useState<boolean>(false);

  const [campaignName, setCampaignName] = useState<string>("");
  const [campaignType, setCampaignType] = useState<CampaignType>("spotmu");
  const [selectedPlatforms, setSelectedPlatforms] = useState<Platform[]>([]);
  const [platformToAdd, setPlatformToAdd] = useState<Platform>("instagram");
  const [selectedAccountIds, setSelectedAccountIds] = useState<string[]>([]);
  const [selectedInterests, setSelectedInterests] = useState<SelectedInterest[]>([]);
  const [interestQuery, setInterestQuery] = useState<string>("");
  const [interestHits, setInterestHits] = useState<SpotmuInterestSearchHit[]>([]);
  const [isSearchingInterests, setIsSearchingInterests] = useState<boolean>(false);
  const [interestSearchError, setInterestSearchError] = useState<unknown>(null);

  const filteredAccounts: AccountReadResponse[] = useMemo((): AccountReadResponse[] => {
    if (selectedPlatforms.length === 0) {
      return [];
    }

    return accounts.filter((account: AccountReadResponse): boolean => {
      return selectedPlatforms.includes(account.platform);
    });
  }, [accounts, selectedPlatforms]);

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadPage = async (): Promise<void> => {

      try {
        const loadedAccounts: AccountReadResponse[] = await listAccounts();

        if (isCancelled) {
          return;
        }

        setAccounts(loadedAccounts);
        setLoadError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setLoadError(caughtError);
      }
    };

    void loadPage();

    return (): void => {
      isCancelled = true;
    };
  }, []);

  const handleAddPlatform = (): void => {

    if (selectedPlatforms.includes(platformToAdd)) {
      return;
    }

    setSelectedPlatforms([...selectedPlatforms, platformToAdd]);
    setSelectedAccountIds((currentAccountIds: string[]): string[] => {
      return currentAccountIds.filter((accountId: string): boolean => {
        const matchingAccount: AccountReadResponse | undefined = accounts.find(
          (account: AccountReadResponse): boolean => {
            return account.id === accountId;
          },
        );

        if (matchingAccount === undefined) {
          return false;
        }

        const nextPlatforms: Platform[] = [...selectedPlatforms, platformToAdd];

        return nextPlatforms.includes(matchingAccount.platform);
      });
    });
  };

  const handleRemovePlatform = (platform: Platform): void => {

    const nextPlatforms: Platform[] = selectedPlatforms.filter(
      (selectedPlatform: Platform): boolean => {
        return selectedPlatform !== platform;
      },
    );

    setSelectedPlatforms(nextPlatforms);
    setSelectedAccountIds((currentAccountIds: string[]): string[] => {
      return currentAccountIds.filter((accountId: string): boolean => {
        const matchingAccount: AccountReadResponse | undefined = accounts.find(
          (account: AccountReadResponse): boolean => {
            return account.id === accountId;
          },
        );

        if (matchingAccount === undefined) {
          return false;
        }

        return nextPlatforms.includes(matchingAccount.platform);
      });
    });
  };

  const handleToggleAccount = (accountId: string): void => {

    if (selectedAccountIds.includes(accountId)) {
      setSelectedAccountIds(
        selectedAccountIds.filter((selectedAccountId: string): boolean => {
          return selectedAccountId !== accountId;
        }),
      );

      return;
    }

    setSelectedAccountIds([...selectedAccountIds, accountId]);
  };

  const handleSearchInterests = async (): Promise<void> => {

    const trimmedQuery: string = interestQuery.trim();

    if (trimmedQuery === "") {
      setInterestHits([]);
      setInterestSearchError(null);

      return;
    }

    setIsSearchingInterests(true);
    setInterestSearchError(null);

    try {
      const loadedHits: SpotmuInterestSearchHit[] = await searchSpotmuInterests(
        trimmedQuery,
        10,
      );

      setInterestHits(loadedHits);
    } catch (caughtError: unknown) {
      setInterestHits([]);
      setInterestSearchError(caughtError);
    } finally {
      setIsSearchingInterests(false);
    }
  };

  const handleAddInterest = (searchHit: SpotmuInterestSearchHit): void => {

    const alreadySelected: boolean = selectedInterests.some(
      (selectedInterest: SelectedInterest): boolean => {
        return selectedInterest.slug === searchHit.slug;
      },
    );

    if (alreadySelected) {
      return;
    }

    const nextInterest: SelectedInterest = {
      slug: searchHit.slug,
      title: searchHit.title,
      spotmu_interest_id: searchHit.spotmu_interest_id,
    };

    setSelectedInterests([...selectedInterests, nextInterest]);
  };

  const handleRemoveInterest = (slug: string): void => {

    setSelectedInterests(
      selectedInterests.filter((selectedInterest: SelectedInterest): boolean => {
        return selectedInterest.slug !== slug;
      }),
    );
  };

  const handleCreateCampaign = async (formEvent: FormEvent): Promise<void> => {

    formEvent.preventDefault();

    if (campaignType === "other") {
      return;
    }

    const missingCreateLabels: string[] = listMissingCampaignCreateLabels(
      readCampaignCreateRequirements(
        campaignName,
        selectedPlatforms,
        selectedAccountIds,
        selectedInterests,
        campaignTypeRequiresLinkedAccount(campaignType),
      ),
    );

    if (missingCreateLabels.length > 0) {
      const missingListText: string = missingCreateLabels.join(", ");

      setActionError(new Error(`Cannot create campaign: missing ${missingListText}.`));

      return;
    }

    setIsBusy(true);
    setActionError(null);

    try {
      const createdCampaign: CampaignReadResponse = await createCampaign({
        name: campaignName,
        campaign_type: campaignType,
        advertisement_type: "carousel",
        platforms: selectedPlatforms,
        account_ids: selectedAccountIds,
        interests: selectedInterests.map((selectedInterest: SelectedInterest) => {
          return {
            slug: selectedInterest.slug,
            title: selectedInterest.title,
            spotmu_interest_id: selectedInterest.spotmu_interest_id,
          };
        }),
      });

      onCreated(createdCampaign);
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setIsBusy(false);
    }
  };

  const isOtherType: boolean = campaignType === "other";
  const isSpotmuTestType: boolean = campaignType === "spotmu_test";
  const accountsAreRequired: boolean = campaignTypeRequiresLinkedAccount(campaignType);
  const missingCreateLabels: string[] = listMissingCampaignCreateLabels(
    readCampaignCreateRequirements(
      campaignName,
      selectedPlatforms,
      selectedAccountIds,
      selectedInterests,
      accountsAreRequired,
    ),
  );
  const canCreate: boolean =
    canWrite && !isBusy && !isOtherType && missingCreateLabels.length === 0;

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>New Campaign</h1>
          <p className="lede">
            Save a Ready campaign definition. Start, generate, and schedule are
            separate — this form does not run ingest or generate.
          </p>
        </div>
        <button type="button" onClick={onCancel}>
          Back to Campaigns
        </button>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      <ErrorBanner error={actionError} />

      <form
        className="stack-form campaign-form"
        onSubmit={(formEvent: FormEvent): void => {
          void handleCreateCampaign(formEvent);
        }}
      >
        <label>
          Campaign name
          <input
            value={campaignName}
            onChange={(changeEvent): void => {
              setCampaignName(changeEvent.target.value);
            }}
            required={!isOtherType}
            disabled={!canWrite || isBusy}
          />
        </label>

        <label>
          Campaign type
          <select
            value={campaignType}
            onChange={(changeEvent): void => {
              setCampaignType(changeEvent.target.value as CampaignType);
            }}
            disabled={!canWrite || isBusy}
          >
            <option value="spotmu">Spotmu</option>
            <option value="spotmu_test">Spotmu - test</option>
            <option value="other">Other</option>
          </select>
        </label>

        {isOtherType ? (
          <p className="coming-soon-banner" role="status">
            Not implemented yet. Coming soon.
          </p>
        ) : (
          <>
            <label>
              Advertisement type
              <select value="carousel" disabled={true}>
                <option value="carousel">Carousel</option>
              </select>
            </label>

            <fieldset className="form-fieldset">
              <legend>Platforms</legend>
              <p className="field-hint">Instagram and TikTok only for now.</p>
              <div className="inline-add-row">
                <select
                  value={platformToAdd}
                  onChange={(changeEvent): void => {
                    setPlatformToAdd(changeEvent.target.value as Platform);
                  }}
                  disabled={!canWrite || isBusy}
                >
                  {AVAILABLE_PLATFORMS.map((platform: Platform): ReactElement => (
                    <option key={platform} value={platform}>
                      {platform}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  disabled={!canWrite || isBusy || selectedPlatforms.includes(platformToAdd)}
                  onClick={handleAddPlatform}
                >
                  +
                </button>
              </div>
              {selectedPlatforms.length === 0 ? (
                <p className="empty-hint">No platforms added yet.</p>
              ) : (
                <ul className="chip-list">
                  {selectedPlatforms.map((platform: Platform): ReactElement => (
                    <li key={platform} className="chip">
                      <span>{platform}</span>
                      <button
                        type="button"
                        disabled={!canWrite || isBusy}
                        onClick={(): void => {
                          handleRemovePlatform(platform);
                        }}
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </fieldset>

            <fieldset className="form-fieldset">
              <legend>Accounts</legend>
              <p className="field-hint">
                {isSpotmuTestType
                  ? "Test campaigns don't need a linked account. You can still pick one if you want."
                  : "Select at least one Instagram / TikTok handle that will publish later."}
              </p>
              {selectedPlatforms.length === 0 ? (
                <p className="empty-hint">Add a platform to see matching accounts.</p>
              ) : filteredAccounts.length === 0 ? (
                <p className="empty-hint">
                  No accounts on the selected platforms. Add an account first.
                </p>
              ) : (
                <ul className="account-pick-list">
                  {filteredAccounts.map((account: AccountReadResponse): ReactElement => {
                    const isChecked: boolean = selectedAccountIds.includes(account.id);

                    return (
                      <li key={account.id}>
                        <label className="checkbox-row">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            disabled={!canWrite || isBusy}
                            onChange={(): void => {
                              handleToggleAccount(account.id);
                            }}
                          />
                          <span>
                            {account.handle} ({account.platform})
                          </span>
                        </label>
                      </li>
                    );
                  })}
                </ul>
              )}
            </fieldset>

            <fieldset className="form-fieldset">
              <legend>Interest sources</legend>
              <p className="field-hint">
                Search live Spotmu interests and add at least one. This does not
                ingest or generate carousels.
              </p>
              <div className="inline-add-row">
                <input
                  type="search"
                  placeholder="Search Spotmu interests"
                  value={interestQuery}
                  onChange={(changeEvent): void => {
                    setInterestQuery(changeEvent.target.value);
                  }}
                  onKeyDown={(keyboardEvent): void => {
                    if (keyboardEvent.key !== "Enter") {
                      return;
                    }

                    keyboardEvent.preventDefault();
                    void handleSearchInterests();
                  }}
                  disabled={!canWrite || isBusy}
                />
                <button
                  type="button"
                  disabled={!canWrite || isBusy || isSearchingInterests || interestQuery.trim() === ""}
                  onClick={(): void => {
                    void handleSearchInterests();
                  }}
                >
                  {isSearchingInterests ? "Searching…" : "Search"}
                </button>
              </div>
              <ErrorBanner error={interestSearchError} />
              {interestHits.length === 0 ? null : (
                <ul className="search-hit-list">
                  {interestHits.map((searchHit: SpotmuInterestSearchHit): ReactElement => {
                    const alreadyAdded: boolean = selectedInterests.some(
                      (selectedInterest: SelectedInterest): boolean => {
                        return selectedInterest.slug === searchHit.slug;
                      },
                    );

                    return (
                      <li key={searchHit.slug} className="search-hit-row">
                        <span>
                          {searchHit.title}
                          <span className="mono"> {searchHit.slug}</span>
                        </span>
                        <button
                          type="button"
                          disabled={!canWrite || isBusy || alreadyAdded}
                          onClick={(): void => {
                            handleAddInterest(searchHit);
                          }}
                        >
                          {alreadyAdded ? "Added" : "Add"}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
              {selectedInterests.length === 0 ? (
                <p className="empty-hint">No interests added yet.</p>
              ) : (
                <ul className="chip-list">
                  {selectedInterests.map((selectedInterest: SelectedInterest): ReactElement => (
                    <li key={selectedInterest.slug} className="chip">
                      <span>
                        {selectedInterest.title}
                        <span className="mono"> {selectedInterest.slug}</span>
                      </span>
                      <button
                        type="button"
                        disabled={!canWrite || isBusy}
                        onClick={(): void => {
                          handleRemoveInterest(selectedInterest.slug);
                        }}
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </fieldset>
          </>
        )}

        {isOtherType || !canWrite || isBusy || missingCreateLabels.length === 0 ? null : (
          <p className="field-hint">
            Add {missingCreateLabels.join(", ")} before creating.
          </p>
        )}
        <div className="button-row">
          {isOtherType ? null : (
            <button type="submit" disabled={!canCreate}>
              {isBusy ? "Saving…" : "Create Campaign"}
            </button>
          )}
          <button type="button" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </form>
    </section>
  );
}

interface CampaignCreateRequirements {
  hasName: boolean;
  hasPlatform: boolean;
  hasAccount: boolean;
  hasInterest: boolean;
}

function readCampaignCreateRequirements(
  campaignName: string,
  selectedPlatforms: Platform[],
  selectedAccountIds: string[],
  selectedInterests: SelectedInterest[],
  accountsAreRequired: boolean,
): CampaignCreateRequirements {

  const campaignCreateRequirements: CampaignCreateRequirements = {
    hasName: campaignName.trim() !== "",
    hasPlatform: selectedPlatforms.length > 0,
    hasAccount: !accountsAreRequired || selectedAccountIds.length > 0,
    hasInterest: selectedInterests.length > 0,
  };

  return campaignCreateRequirements;
}

function listMissingCampaignCreateLabels(
  campaignCreateRequirements: CampaignCreateRequirements,
): string[] {

  const missingLabels: string[] = [];

  if (!campaignCreateRequirements.hasName) {
    missingLabels.push("a campaign name");
  }

  if (!campaignCreateRequirements.hasPlatform) {
    missingLabels.push("at least one platform");
  }

  if (!campaignCreateRequirements.hasAccount) {
    missingLabels.push("at least one account");
  }

  if (!campaignCreateRequirements.hasInterest) {
    missingLabels.push("at least one Spotmu interest");
  }

  return missingLabels;
}
