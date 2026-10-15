import { useEffect, useState, type ReactElement } from "react";

import {
  fetchCampaignById,
  finishCampaign,
  listCampaigns,
  pauseCampaign,
  resumeCampaign,
  runCampaign,
  startCampaign,
} from "../api/client";
import type {
  CampaignAccountReadResponse,
  CampaignCarouselRead,
  CampaignCarouselUnitRead,
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
  campaignTypeLabel,
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
  onCreateCampaign: () => void;
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
  onCreateCampaign,
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

  const handleRun = async (): Promise<void> => {

    if (selectedCampaign === null) {
      return;
    }

    setIsBusy(true);
    setActionError(null);
    onStatusMessageChange("");

    try {
      const assembledCampaign: CampaignReadResponse = await runCampaign(selectedCampaign.id);
      const carouselCount: number = assembledCampaign.carousels.length;
      const statusText: string = carouselCount === 0
        ? `Ran ${assembledCampaign.name}. No live units, so no carousel.`
        : `Ran ${assembledCampaign.name}. ${carouselCount} carousel${carouselCount === 1 ? "" : "s"}.`;

      await reloadCampaignsAfterAction(assembledCampaign, statusText);
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setIsBusy(false);
    }
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
        onRun={handleRun}
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
      onCreateCampaign={onCreateCampaign}
    />
  );
}

interface CampaignListViewProps {
  campaigns: CampaignReadResponse[];
  loadError: unknown;
  actionError: unknown;
  statusMessage: string;
  onSelectCampaign: (campaignId: string) => void;
  onCreateCampaign: () => void;
}

function CampaignListView({
  campaigns,
  loadError,
  actionError,
  statusMessage,
  onSelectCampaign,
  onCreateCampaign,
}: CampaignListViewProps): ReactElement {

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>Campaigns</h1>
          <p className="lede">
            All saved campaigns. Open a row for details and lifecycle actions
            (Start / Pause / Resume / Finish).
          </p>
        </div>
        <div className="page-header-actions">
          <button type="button" className="primary" onClick={onCreateCampaign}>
            Create campaign
          </button>
        </div>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      <ErrorBanner error={actionError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}

      {loadError !== null ? null : campaigns.length === 0 ? (
        <p className="empty-hint">No campaigns yet.</p>
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
                <td>{campaignTypeLabel(campaign.campaign_type)}</td>
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
  onRun: () => Promise<void>;
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
  onRun,
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
            Run assembles accepted units from the source into carousels on the
            theme. Drafts stay out. Run does not generate text.
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
            <dd>{campaignTypeLabel(selectedCampaign.campaign_type)}</dd>
            <dt>Theme</dt>
            <dd>{selectedCampaign.theme_name === null ? "—" : selectedCampaign.theme_name}</dd>
            <dt>Source</dt>
            <dd>{selectedCampaign.source_name === null ? "—" : selectedCampaign.source_name}</dd>
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
            <dt>Carousels</dt>
            <dd>
              <CampaignCarouselList carousels={selectedCampaign.carousels} />
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

          {canWrite && (selectedCampaign.theme_id === null || selectedCampaign.source_id === null) ? (
            <p className="field-hint">
              This campaign was saved before a theme and source. Run stays off until both are set.
            </p>
          ) : null}
          {canWrite ? (
            <div className="button-row">
              <button
                id="run-campaign"
                type="button"
                disabled={
                  isBusy
                  || selectedCampaign.theme_id === null
                  || selectedCampaign.source_id === null
                }
                onClick={(): void => {
                  void onRun();
                }}
              >
                Run
              </button>
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

interface CampaignCarouselListProps {
  carousels: CampaignCarouselRead[];
}

function CampaignCarouselList({ carousels }: CampaignCarouselListProps): ReactElement {

  if (carousels.length === 0) {
    return <span id="campaign-carousels">No carousel yet.</span>;
  }

  return (
    <ol id="campaign-carousels">
      {carousels.map((carousel: CampaignCarouselRead): ReactElement => (
        <li key={carousel.id}>
          Carousel {carousel.position + 1}
          <ul>
            {carousel.units.map((unit: CampaignCarouselUnitRead): ReactElement => (
              <li key={unit.unit_id}>{unit.name}</li>
            ))}
          </ul>
        </li>
      ))}
    </ol>
  );
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
