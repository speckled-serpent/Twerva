import { useEffect, useState, type ReactElement } from "react";

import {
  fetchCampaignById,
  finishCampaign,
  listCampaigns,
  pauseCampaign,
  resumeCampaign,
  startCampaign,
} from "../api/client";
import type {
  CampaignAccountReadResponse,
  CampaignInterestReadResponse,
  CampaignReadResponse,
} from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import { useCanWriteOps } from "../session/OpsSessionContext";
import {
  CampaignStatusBadge,
  campaignLifecycleActionLabel,
  campaignLifecycleActionPastLabel,
  campaignStatusLabel,
  formatCampaignPlatforms,
  formatCampaignTimestamp,
  listAllowedCampaignLifecycleActions,
  type CampaignLifecycleAction,
} from "./campaignDisplay";

export interface CampaignsPageProps {
  openedCampaignId: string | null;
  statusMessage: string;
  onOpenedCampaignIdChange: (campaignId: string | null) => void;
  onStatusMessageChange: (statusMessage: string) => void;
}

/**
 * Campaigns tab: list every campaign; selecting one opens a basic detail view.
 *
 * @param props - Opened campaign id, banner, and navigation callbacks
 * @returns The Campaigns list or detail
 */
export function CampaignsPage({
  openedCampaignId,
  statusMessage,
  onOpenedCampaignIdChange,
  onStatusMessageChange,
}: CampaignsPageProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [campaigns, setCampaigns] = useState<CampaignReadResponse[]>([]);
  const [selectedCampaign, setSelectedCampaign] = useState<CampaignReadResponse | null>(
    null,
  );
  const [loadError, setLoadError] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [isBusy, setIsBusy] = useState<boolean>(false);

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadList = async (): Promise<void> => {

      try {
        const loadedCampaigns: CampaignReadResponse[] = await listCampaigns();

        if (isCancelled) {
          return;
        }

        setCampaigns(loadedCampaigns);
        setLoadError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setLoadError(caughtError);
      }
    };

    void loadList();

    return (): void => {
      isCancelled = true;
    };
  }, []);

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    if (openedCampaignId === null) {
      setSelectedCampaign(null);

      return (): void => {
        isCancelled = true;
      };
    }

    const loadDetail = async (): Promise<void> => {

      try {
        const loadedCampaign: CampaignReadResponse = await fetchCampaignById(
          openedCampaignId,
        );

        if (isCancelled) {
          return;
        }

        setSelectedCampaign(loadedCampaign);
        setLoadError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setSelectedCampaign(null);
        setLoadError(caughtError);
      }
    };

    void loadDetail();

    return (): void => {
      isCancelled = true;
    };
  }, [openedCampaignId]);

  const reloadCampaignsAfterAction = async (
    updatedCampaign: CampaignReadResponse,
    nextStatusMessage: string,
  ): Promise<void> => {

    const loadedCampaigns: CampaignReadResponse[] = await listCampaigns();

    setCampaigns(loadedCampaigns);
    setSelectedCampaign(updatedCampaign);
    onStatusMessageChange(nextStatusMessage);
  };

  const handleLifecycleAction = async (
    lifecycleAction: CampaignLifecycleAction,
  ): Promise<void> => {

    if (selectedCampaign === null) {
      return;
    }

    setIsBusy(true);
    setActionError(null);
    onStatusMessageChange("");

    try {
      const updatedCampaign: CampaignReadResponse = await runCampaignLifecycleAction(
        selectedCampaign.id,
        lifecycleAction,
      );
      const statusLabel: string = campaignStatusLabel(updatedCampaign.status);

      await reloadCampaignsAfterAction(
        updatedCampaign,
        `${campaignLifecycleActionPastLabel(lifecycleAction)} ${updatedCampaign.name} (${statusLabel}).`,
      );
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setIsBusy(false);
    }
  };

  if (openedCampaignId !== null) {
    return (
      <CampaignDetailView
        selectedCampaign={selectedCampaign}
        canWrite={canWrite}
        isBusy={isBusy}
        loadError={loadError}
        actionError={actionError}
        statusMessage={statusMessage}
        onBack={(): void => {
          onOpenedCampaignIdChange(null);
          setActionError(null);
        }}
        onLifecycleAction={handleLifecycleAction}
      />
    );
  }

  return (
    <CampaignListView
      campaigns={campaigns}
      loadError={loadError}
      actionError={actionError}
      statusMessage={statusMessage}
      onSelectCampaign={(campaignId: string): void => {
        setActionError(null);
        onOpenedCampaignIdChange(campaignId);
      }}
    />
  );
}

interface CampaignListViewProps {
  campaigns: CampaignReadResponse[];
  loadError: unknown;
  actionError: unknown;
  statusMessage: string;
  onSelectCampaign: (campaignId: string) => void;
}

function CampaignListView({
  campaigns,
  loadError,
  actionError,
  statusMessage,
  onSelectCampaign,
}: CampaignListViewProps): ReactElement {

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>Campaigns</h1>
          <p className="lede">
            All saved campaigns. Open a row for details and lifecycle actions
            (Start / Pause / Resume / Finish). Create lives on New Campaign.
          </p>
        </div>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      <ErrorBanner error={actionError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}

      {loadError !== null ? null : campaigns.length === 0 ? (
        <p>No campaigns yet. Use New Campaign to persist a Ready definition.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Status</th>
              <th>Platforms</th>
              <th>Interests</th>
              <th>Accounts</th>
              <th>Created</th>
              <th>View</th>
            </tr>
          </thead>
          <tbody>
            {campaigns.map((campaign: CampaignReadResponse): ReactElement => (
              <tr
                key={campaign.id}
                className="clickable-row"
                onClick={(): void => {
                  onSelectCampaign(campaign.id);
                }}
              >
                <td>{campaign.name}</td>
                <td>{campaign.campaign_type}</td>
                <td>
                  <CampaignStatusBadge campaignStatus={campaign.status} />
                </td>
                <td>{formatCampaignPlatforms(campaign.platforms)}</td>
                <td>{campaign.interest_count}</td>
                <td>{campaign.account_count}</td>
                <td className="mono">{formatCampaignTimestamp(campaign.created_at)}</td>
                <td>
                  <button
                    type="button"
                    onClick={(clickEvent): void => {
                      clickEvent.stopPropagation();
                      onSelectCampaign(campaign.id);
                    }}
                  >
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

interface CampaignDetailViewProps {
  selectedCampaign: CampaignReadResponse | null;
  canWrite: boolean;
  isBusy: boolean;
  loadError: unknown;
  actionError: unknown;
  statusMessage: string;
  onBack: () => void;
  onLifecycleAction: (lifecycleAction: CampaignLifecycleAction) => Promise<void>;
}

function CampaignDetailView({
  selectedCampaign,
  canWrite,
  isBusy,
  loadError,
  actionError,
  statusMessage,
  onBack,
  onLifecycleAction,
}: CampaignDetailViewProps): ReactElement {

  const allowedActions: CampaignLifecycleAction[] =
    selectedCampaign === null
      ? []
      : listAllowedCampaignLifecycleActions(selectedCampaign.status);

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>{selectedCampaign === null ? "Campaign" : selectedCampaign.name}</h1>
          <p className="lede">
            Basic campaign record. Start flips status only — it does not ingest
            or generate yet.
          </p>
        </div>
        <button type="button" onClick={onBack}>
          Back to list
        </button>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      <ErrorBanner error={actionError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}

      {selectedCampaign === null ? (
        loadError === null ? <p>Loading campaign…</p> : null
      ) : (
        <>
          <dl className="campaign-detail-list">
            <dt>Name</dt>
            <dd>{selectedCampaign.name}</dd>
            <dt>Hashtag</dt>
            <dd className="mono">{selectedCampaign.hashtag}</dd>
            <dt>Slug</dt>
            <dd className="mono">{selectedCampaign.slug}</dd>
            <dt>Status</dt>
            <dd>
              <CampaignStatusBadge campaignStatus={selectedCampaign.status} />
            </dd>
            <dt>Type</dt>
            <dd>{selectedCampaign.campaign_type}</dd>
            <dt>Advertisement</dt>
            <dd>{selectedCampaign.advertisement_type}</dd>
            <dt>Platforms</dt>
            <dd>{formatCampaignPlatforms(selectedCampaign.platforms)}</dd>
            <dt>Accounts</dt>
            <dd>
              <CampaignAccountList accounts={selectedCampaign.accounts} />
            </dd>
            <dt>Spotmu interests</dt>
            <dd>
              <CampaignInterestList interests={selectedCampaign.interests} />
            </dd>
            <dt>Created</dt>
            <dd className="mono">{formatCampaignTimestamp(selectedCampaign.created_at)}</dd>
            <dt>Updated</dt>
            <dd className="mono">{formatCampaignTimestamp(selectedCampaign.updated_at)}</dd>
            <dt>Created by</dt>
            <dd className="mono">
              {selectedCampaign.created_by === null ? "—" : selectedCampaign.created_by}
            </dd>
          </dl>

          {canWrite ? (
            <div className="button-row">
              {(["start", "pause", "resume", "finish"] as CampaignLifecycleAction[]).map(
                (lifecycleAction: CampaignLifecycleAction): ReactElement => {
                  const isAllowed: boolean = allowedActions.includes(lifecycleAction);

                  return (
                    <button
                      key={lifecycleAction}
                      type="button"
                      disabled={!isAllowed || isBusy}
                      className={lifecycleAction === "finish" ? "danger" : undefined}
                      onClick={(): void => {
                        void onLifecycleAction(lifecycleAction);
                      }}
                    >
                      {isBusy && isAllowed
                        ? "Saving…"
                        : campaignLifecycleActionLabel(lifecycleAction)}
                    </button>
                  );
                },
              )}
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}

interface CampaignAccountListProps {
  accounts: CampaignAccountReadResponse[];
}

function CampaignAccountList({ accounts }: CampaignAccountListProps): ReactElement {

  if (accounts.length === 0) {
    return <span>—</span>;
  }

  return (
    <ul className="campaign-detail-sublist">
      {accounts.map((account: CampaignAccountReadResponse): ReactElement => (
        <li key={account.id}>
          {account.handle} ({account.platform})
        </li>
      ))}
    </ul>
  );
}

interface CampaignInterestListProps {
  interests: CampaignInterestReadResponse[];
}

function CampaignInterestList({ interests }: CampaignInterestListProps): ReactElement {

  if (interests.length === 0) {
    return <span>—</span>;
  }

  return (
    <ul className="campaign-detail-sublist">
      {interests.map((interest: CampaignInterestReadResponse): ReactElement => (
        <li key={interest.slug}>
          {interest.title === null || interest.title === "" ? interest.slug : interest.title}
          <span className="mono"> {interest.slug}</span>
        </li>
      ))}
    </ul>
  );
}

async function runCampaignLifecycleAction(
  campaignId: string,
  lifecycleAction: CampaignLifecycleAction,
): Promise<CampaignReadResponse> {

  if (lifecycleAction === "start") {
    return startCampaign(campaignId);
  }

  if (lifecycleAction === "pause") {
    return pauseCampaign(campaignId);
  }

  if (lifecycleAction === "resume") {
    return resumeCampaign(campaignId);
  }

  return finishCampaign(campaignId);
}
