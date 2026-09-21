import {
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type ReactElement,
} from "react";

import {
  createCampaign,
  listAccounts,
  listCampaigns,
  searchSpotmuInterests,
} from "../api/client";
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

type CampaignsView = "list" | "create";

interface SelectedInterest {
  slug: string;
  title: string;
  spotmu_interest_id: string | null;
}

const AVAILABLE_PLATFORMS: Platform[] = ["instagram", "tiktok"];

/**
 * Campaigns page: list saved campaigns or create a not-started definition.
 *
 * @returns The Campaigns page
 */
export function CampaignsPage(): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [activeView, setActiveView] = useState<CampaignsView>("list");
  const [campaigns, setCampaigns] = useState<CampaignReadResponse[]>([]);
  const [accounts, setAccounts] = useState<AccountReadResponse[]>([]);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [statusMessage, setStatusMessage] = useState<string>("");
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

  const reloadLists = async (): Promise<void> => {

    const loadedCampaigns: CampaignReadResponse[] = await listCampaigns();
    const loadedAccounts: AccountReadResponse[] = await listAccounts();

    setCampaigns(loadedCampaigns);
    setAccounts(loadedAccounts);
  };

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadPage = async (): Promise<void> => {

      try {
        const loadedCampaigns: CampaignReadResponse[] = await listCampaigns();
        const loadedAccounts: AccountReadResponse[] = await listAccounts();

        if (isCancelled) {
          return;
        }

        setCampaigns(loadedCampaigns);
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

  const resetCreateForm = (): void => {

    setCampaignName("");
    setCampaignType("spotmu");
    setSelectedPlatforms([]);
    setPlatformToAdd("instagram");
    setSelectedAccountIds([]);
    setSelectedInterests([]);
    setInterestQuery("");
    setInterestHits([]);
    setInterestSearchError(null);
  };

  const handleOpenCreate = (): void => {

    resetCreateForm();
    setActionError(null);
    setStatusMessage("");
    setActiveView("create");
  };

  const handleCancelCreate = (): void => {

    resetCreateForm();
    setActionError(null);
    setActiveView("list");
  };

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

    if (campaignType !== "spotmu") {
      return;
    }

    const missingCreateLabels: string[] = listMissingCampaignCreateLabels(
      readCampaignCreateRequirements(
        campaignName,
        selectedPlatforms,
        selectedAccountIds,
        selectedInterests,
      ),
    );

    if (missingCreateLabels.length > 0) {
      const missingListText: string = missingCreateLabels.join(", ");

      setActionError(new Error(`Cannot create campaign: missing ${missingListText}.`));

      return;
    }

    setIsBusy(true);
    setActionError(null);
    setStatusMessage("");

    try {
      const createdCampaign: CampaignReadResponse = await createCampaign({
        name: campaignName,
        campaign_type: "spotmu",
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

      setStatusMessage(`Created campaign ${createdCampaign.name} (${createdCampaign.status}).`);
      resetCreateForm();
      await reloadLists();
      setActiveView("list");
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <section>
      {activeView === "list" ? (
        <CampaignListView
          campaigns={campaigns}
          canWrite={canWrite}
          loadError={loadError}
          actionError={actionError}
          statusMessage={statusMessage}
          onNewCampaign={handleOpenCreate}
        />
      ) : (
        <NewCampaignForm
          canWrite={canWrite}
          isBusy={isBusy}
          actionError={actionError}
          campaignName={campaignName}
          campaignType={campaignType}
          selectedPlatforms={selectedPlatforms}
          platformToAdd={platformToAdd}
          filteredAccounts={filteredAccounts}
          selectedAccountIds={selectedAccountIds}
          selectedInterests={selectedInterests}
          interestQuery={interestQuery}
          interestHits={interestHits}
          isSearchingInterests={isSearchingInterests}
          interestSearchError={interestSearchError}
          onCampaignNameChange={setCampaignName}
          onCampaignTypeChange={setCampaignType}
          onPlatformToAddChange={setPlatformToAdd}
          onAddPlatform={handleAddPlatform}
          onRemovePlatform={handleRemovePlatform}
          onToggleAccount={handleToggleAccount}
          onInterestQueryChange={setInterestQuery}
          onSearchInterests={handleSearchInterests}
          onAddInterest={handleAddInterest}
          onRemoveInterest={handleRemoveInterest}
          onSubmit={handleCreateCampaign}
          onCancel={handleCancelCreate}
        />
      )}
    </section>
  );
}

interface CampaignListViewProps {
  campaigns: CampaignReadResponse[];
  canWrite: boolean;
  loadError: unknown;
  actionError: unknown;
  statusMessage: string;
  onNewCampaign: () => void;
}

function CampaignListView({
  campaigns,
  canWrite,
  loadError,
  actionError,
  statusMessage,
  onNewCampaign,
}: CampaignListViewProps): ReactElement {

  return (
    <>
      <div className="page-header-row">
        <div>
          <h1>Campaigns</h1>
          <p className="lede">
            Marketing campaigns (name, platforms, accounts, Spotmu interests).
            Create stores a definition only — it does not start or generate.
          </p>
        </div>
        <button type="button" disabled={!canWrite} onClick={onNewCampaign}>
          New Campaign
        </button>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      <ErrorBanner error={actionError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}

      {loadError !== null ? null : campaigns.length === 0 ? (
        <p>No campaigns yet. Create a Spotmu campaign to persist a draft definition.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Platforms</th>
              <th>Interests</th>
              <th>Accounts</th>
              <th>Status</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {campaigns.map((campaign: CampaignReadResponse): ReactElement => (
              <tr key={campaign.id}>
                <td>{campaign.name}</td>
                <td>{campaign.campaign_type}</td>
                <td>{formatPlatforms(campaign.platforms)}</td>
                <td>{campaign.interest_count}</td>
                <td>{campaign.account_count}</td>
                <td>{campaign.status}</td>
                <td className="mono">{formatCreatedAt(campaign.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}

interface NewCampaignFormProps {
  canWrite: boolean;
  isBusy: boolean;
  actionError: unknown;
  campaignName: string;
  campaignType: CampaignType;
  selectedPlatforms: Platform[];
  platformToAdd: Platform;
  filteredAccounts: AccountReadResponse[];
  selectedAccountIds: string[];
  selectedInterests: SelectedInterest[];
  interestQuery: string;
  interestHits: SpotmuInterestSearchHit[];
  isSearchingInterests: boolean;
  interestSearchError: unknown;
  onCampaignNameChange: (campaignName: string) => void;
  onCampaignTypeChange: (campaignType: CampaignType) => void;
  onPlatformToAddChange: (platform: Platform) => void;
  onAddPlatform: () => void;
  onRemovePlatform: (platform: Platform) => void;
  onToggleAccount: (accountId: string) => void;
  onInterestQueryChange: (query: string) => void;
  onSearchInterests: () => Promise<void>;
  onAddInterest: (searchHit: SpotmuInterestSearchHit) => void;
  onRemoveInterest: (slug: string) => void;
  onSubmit: (formEvent: FormEvent) => Promise<void>;
  onCancel: () => void;
}

function NewCampaignForm({
  canWrite,
  isBusy,
  actionError,
  campaignName,
  campaignType,
  selectedPlatforms,
  platformToAdd,
  filteredAccounts,
  selectedAccountIds,
  selectedInterests,
  interestQuery,
  interestHits,
  isSearchingInterests,
  interestSearchError,
  onCampaignNameChange,
  onCampaignTypeChange,
  onPlatformToAddChange,
  onAddPlatform,
  onRemovePlatform,
  onToggleAccount,
  onInterestQueryChange,
  onSearchInterests,
  onAddInterest,
  onRemoveInterest,
  onSubmit,
  onCancel,
}: NewCampaignFormProps): ReactElement {

  const isOtherType: boolean = campaignType === "other";
  const missingCreateLabels: string[] = listMissingCampaignCreateLabels(
    readCampaignCreateRequirements(
      campaignName,
      selectedPlatforms,
      selectedAccountIds,
      selectedInterests,
    ),
  );
  const canCreate: boolean =
    canWrite && !isBusy && !isOtherType && missingCreateLabels.length === 0;

  return (
    <>
      <div className="page-header-row">
        <div>
          <h1>New Campaign</h1>
          <p className="lede">
            Save a not-started campaign definition. Start, generate, and schedule
            are not in this flow.
          </p>
        </div>
        <button type="button" onClick={onCancel}>
          Back to list
        </button>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={actionError} />

      <form
        className="stack-form campaign-form"
        onSubmit={(formEvent: FormEvent): void => {
          void onSubmit(formEvent);
        }}
      >
        <label>
          Campaign name
          <input
            value={campaignName}
            onChange={(changeEvent): void => {
              onCampaignNameChange(changeEvent.target.value);
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
              onCampaignTypeChange(changeEvent.target.value as CampaignType);
            }}
            disabled={!canWrite || isBusy}
          >
            <option value="spotmu">Spotmu</option>
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
                    onPlatformToAddChange(changeEvent.target.value as Platform);
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
                  onClick={onAddPlatform}
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
                          onRemovePlatform(platform);
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
                Select at least one Instagram / TikTok handle that will publish later.
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
                              onToggleAccount(account.id);
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
                    onInterestQueryChange(changeEvent.target.value);
                  }}
                  onKeyDown={(keyboardEvent): void => {
                    if (keyboardEvent.key !== "Enter") {
                      return;
                    }

                    keyboardEvent.preventDefault();
                    void onSearchInterests();
                  }}
                  disabled={!canWrite || isBusy}
                />
                <button
                  type="button"
                  disabled={!canWrite || isBusy || isSearchingInterests || interestQuery.trim() === ""}
                  onClick={(): void => {
                    void onSearchInterests();
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
                            onAddInterest(searchHit);
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
                          onRemoveInterest(selectedInterest.slug);
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
    </>
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
): CampaignCreateRequirements {

  const campaignCreateRequirements: CampaignCreateRequirements = {
    hasName: campaignName.trim() !== "",
    hasPlatform: selectedPlatforms.length > 0,
    hasAccount: selectedAccountIds.length > 0,
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

function formatPlatforms(platforms: Platform[]): string {

  if (platforms.length === 0) {
    return "—";
  }

  return platforms.join(", ");
}

function formatCreatedAt(createdAt: string): string {

  const parsedDate: Date = new Date(createdAt);

  if (Number.isNaN(parsedDate.getTime())) {
    return createdAt;
  }

  return parsedDate.toISOString().replace("T", " ").slice(0, 19);
}
