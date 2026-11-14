import { useEffect, useState, type FormEvent, type ReactElement } from "react";

import {
  assembledFrameFileUrl,
  createCampaignPostStubMetrics,
  fetchCarouselById,
  placeCampaignPost,
  publishCampaignPost,
  removeCampaignPost,
  rescheduleCampaignPost,
} from "../api/client";
import type {
  CampaignAccountReadResponse,
  CampaignPostFrameRead,
  CampaignPostRead,
  CampaignReadResponse,
  CarouselAssemblyReadResponse,
} from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { formatCampaignTimestamp } from "./campaignDisplay";
import {
  ADD_CAMPAIGN_POST_READER_NAME,
  CAMPAIGN_POSTS_EMPTY,
  CAMPAIGN_TIMELINE_NEEDS_ASSEMBLY,
  addCampaignPostAccessibleName,
  campaignPostAddEnabled,
  campaignPostCanChangeTime,
  campaignPostCarouselChoices,
  campaignPostCarouselOptions,
  campaignPostFailureDetail,
  campaignPostOffersPublish,
  campaignPostOffersStubMetrics,
  campaignTimelineAfterAdd,
  campaignTimelineWithoutPost,
  campaignTimelineWithPost,
  defaultScheduledForValue,
  orderedCampaignPosts,
  scheduledForInputValue,
  type CampaignPostCarouselOption,
} from "./campaignTimeline";

export interface CampaignTimelineProps {
  campaign: CampaignReadResponse;
  canWrite: boolean;
  onCampaignReplaced: (campaign: CampaignReadResponse) => void;
}

/**
 * Posts on one campaign: add an assembled carousel, then publish it.
 *
 * The hashtag on the detail stays the hashtag. Captions are the
 * assembled carousel's and are not given that hashtag here.
 *
 * @param props - The open campaign and the replace callback
 * @returns The Posts section
 */
export function CampaignTimeline({
  campaign,
  canWrite,
  onCampaignReplaced,
}: CampaignTimelineProps): ReactElement {

  const [assembly, setAssembly] = useState<CarouselAssemblyReadResponse | null>(null);
  const [assemblyLoaded, setAssemblyLoaded] = useState<boolean>(false);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [assembledCarouselId, setAssembledCarouselId] = useState<string>("");
  const [accountId, setAccountId] = useState<string>("");
  const [scheduledFor, setScheduledFor] = useState<string>(defaultScheduledForValue);
  const [rescheduleTimes, setRescheduleTimes] = useState<Record<string, string>>({});
  const [isAdding, setIsAdding] = useState<boolean>(false);
  const [busyPostId, setBusyPostId] = useState<string>("");
  const [busyAction, setBusyAction] = useState<string>("");

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    if (campaign.carousel_id === null) {
      setAssembly(null);
      setAssemblyLoaded(true);
      setLoadError(null);

      return (): void => {
        isCancelled = true;
      };
    }

    const carouselId: string = campaign.carousel_id;
    setAssemblyLoaded(false);

    const loadAssembly = async (): Promise<void> => {

      try {
        const loadedCarousel = await fetchCarouselById(carouselId);

        if (isCancelled) {
          return;
        }

        setAssembly(loadedCarousel.assembly);
        setLoadError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setAssembly(null);
        setLoadError(caughtError);
      } finally {
        if (!isCancelled) {
          setAssemblyLoaded(true);
        }
      }
    };

    void loadAssembly();

    return (): void => {
      isCancelled = true;
    };
  }, [campaign.carousel_id]);

  const carouselOptions: CampaignPostCarouselOption[] = campaignPostCarouselOptions(assembly);
  const carouselChoices: CampaignPostCarouselOption[] = campaignPostCarouselChoices(assembly);
  const selectedCarouselId: string = carouselChoices.some(
    (option: CampaignPostCarouselOption): boolean => option.id === assembledCarouselId,
  )
    ? assembledCarouselId
    : (carouselChoices[0]?.id ?? "");
  const selectedAccountId: string = campaign.accounts.some(
    (account: CampaignAccountReadResponse): boolean => account.id === accountId,
  )
    ? accountId
    : (campaign.accounts[0]?.id ?? "");
  const addEnabled: boolean = campaignPostAddEnabled(
    canWrite,
    campaign.carousel_id,
    campaign.accounts.length,
    assembly,
  );
  const addAccessibleName: string = isAdding
    ? "Adding…"
    : addCampaignPostAccessibleName(canWrite);
  const posts: CampaignPostRead[] = orderedCampaignPosts(campaign.posts);
  const showNeedsAssembly: boolean = assemblyLoaded
    && campaign.carousel_id !== null
    && assembly === null;

  const handleAdd = async (formEvent: FormEvent): Promise<void> => {

    formEvent.preventDefault();
    setActionError(null);

    const scheduledDate: Date = new Date(scheduledFor);

    if (Number.isNaN(scheduledDate.getTime())) {
      setActionError(new Error("scheduled_for is not a valid datetime."));

      return;
    }

    setIsAdding(true);

    try {
      const placedPost: CampaignPostRead = await placeCampaignPost(campaign.id, {
        assembled_carousel_id: selectedCarouselId,
        account_id: selectedAccountId,
        scheduled_for: scheduledDate.toISOString(),
      });
      const nextCampaign: CampaignReadResponse = campaignTimelineAfterAdd(campaign, placedPost);

      onCampaignReplaced(nextCampaign);
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setIsAdding(false);
    }
  };

  const handleReschedule = async (post: CampaignPostRead): Promise<void> => {

    const nextTime: string = rescheduleTimes[post.id] ?? scheduledForInputValue(post.scheduled_for);
    const scheduledDate: Date = new Date(nextTime);

    setActionError(null);

    if (Number.isNaN(scheduledDate.getTime())) {
      setActionError(new Error("scheduled_for is not a valid datetime."));

      return;
    }

    setBusyPostId(post.id);
    setBusyAction("reschedule");

    try {
      const updatedPost: CampaignPostRead = await rescheduleCampaignPost(campaign.id, post.id, {
        scheduled_for: scheduledDate.toISOString(),
      });

      onCampaignReplaced(campaignTimelineWithPost(campaign, updatedPost));
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setBusyPostId("");
      setBusyAction("");
    }
  };

  const handleRemove = async (postId: string): Promise<void> => {

    setActionError(null);
    setBusyPostId(postId);
    setBusyAction("remove");

    try {
      await removeCampaignPost(campaign.id, postId);
      onCampaignReplaced(campaignTimelineWithoutPost(campaign, postId));
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setBusyPostId("");
      setBusyAction("");
    }
  };

  const handlePublish = async (postId: string): Promise<void> => {

    setActionError(null);
    setBusyPostId(postId);
    setBusyAction("publish");

    try {
      const publishedPost: CampaignPostRead = await publishCampaignPost(campaign.id, postId);

      onCampaignReplaced(campaignTimelineWithPost(campaign, publishedPost));
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setBusyPostId("");
      setBusyAction("");
    }
  };

  const handleStubMetrics = async (postId: string): Promise<void> => {

    setActionError(null);
    setBusyPostId(postId);
    setBusyAction("stub");

    try {
      const snapshot = await createCampaignPostStubMetrics(campaign.id, postId);
      const storedPost: CampaignPostRead | undefined = campaign.posts.find(
        (post: CampaignPostRead): boolean => post.id === postId,
      );

      if (storedPost === undefined) {
        return;
      }

      const withResults: CampaignPostRead = {
        ...storedPost,
        results: {
          captured_at: snapshot.captured_at,
          views: snapshot.views,
          likes: snapshot.likes,
          comments: snapshot.comments,
          shares: snapshot.shares,
        },
      };

      onCampaignReplaced(campaignTimelineWithPost(campaign, withResults));
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setBusyPostId("");
      setBusyAction("");
    }
  };

  return (
    <section className="campaign-timeline" aria-labelledby="campaign-posts-heading">
      <h2 id="campaign-posts-heading">Posts</h2>
      <ErrorBanner error={loadError} />
      <ErrorBanner error={actionError} />
      {posts.length === 0 ? <p className="empty-hint">{CAMPAIGN_POSTS_EMPTY}</p> : null}
      {showNeedsAssembly ? (
        <p className="field-hint">{CAMPAIGN_TIMELINE_NEEDS_ASSEMBLY}</p>
      ) : null}
      <form
        className="stack-form"
        onSubmit={(formEvent: FormEvent): void => {
          void handleAdd(formEvent);
        }}
      >
        <label>
          Assembled carousel
          <select
            value={selectedCarouselId}
            onChange={(changeEvent): void => {
              setAssembledCarouselId(changeEvent.target.value);
            }}
            disabled={!canWrite || carouselChoices.length === 0}
          >
            {carouselOptions.length === 0 ? (
              <option value="">No assembled carousel</option>
            ) : null}
            {carouselOptions.map((option: CampaignPostCarouselOption): ReactElement => (
              <option key={option.id} value={option.id} disabled={!option.enabled}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Account
          <select
            value={selectedAccountId}
            onChange={(changeEvent): void => {
              setAccountId(changeEvent.target.value);
            }}
            disabled={!canWrite || campaign.accounts.length === 0}
          >
            {campaign.accounts.length === 0 ? <option value="">No linked account</option> : null}
            {campaign.accounts.map((account: CampaignAccountReadResponse): ReactElement => (
              <option key={account.id} value={account.id}>
                {account.handle} ({account.platform})
              </option>
            ))}
          </select>
        </label>
        <label>
          Time
          <input
            type="datetime-local"
            value={scheduledFor}
            onChange={(changeEvent): void => {
              setScheduledFor(changeEvent.target.value);
            }}
            disabled={!canWrite}
            required
          />
        </label>
        <button
          id="add-campaign-post"
          type="submit"
          disabled={!addEnabled || isAdding}
          aria-label={canWrite ? addAccessibleName : ADD_CAMPAIGN_POST_READER_NAME}
        >
          {isAdding ? "Adding…" : "Add to timeline"}
        </button>
      </form>
      {posts.length === 0 ? null : (
        <ol className="campaign-timeline-posts">
          {posts.map((post: CampaignPostRead): ReactElement => (
            <CampaignTimelineRow
              key={post.id}
              post={post}
              canWrite={canWrite}
              isBusy={busyPostId === post.id}
              busyAction={busyPostId === post.id ? busyAction : ""}
              rescheduleTime={rescheduleTimes[post.id] ?? scheduledForInputValue(post.scheduled_for)}
              onRescheduleTimeChange={(nextTime: string): void => {
                setRescheduleTimes({
                  ...rescheduleTimes,
                  [post.id]: nextTime,
                });
              }}
              onReschedule={(): void => {
                void handleReschedule(post);
              }}
              onRemove={(): void => {
                void handleRemove(post.id);
              }}
              onPublish={(): void => {
                void handlePublish(post.id);
              }}
              onStubMetrics={(): void => {
                void handleStubMetrics(post.id);
              }}
            />
          ))}
        </ol>
      )}
    </section>
  );
}

interface CampaignTimelineRowProps {
  post: CampaignPostRead;
  canWrite: boolean;
  isBusy: boolean;
  busyAction: string;
  rescheduleTime: string;
  onRescheduleTimeChange: (nextTime: string) => void;
  onReschedule: () => void;
  onRemove: () => void;
  onPublish: () => void;
  onStubMetrics: () => void;
}

function CampaignTimelineRow({
  post,
  canWrite,
  isBusy,
  busyAction,
  rescheduleTime,
  onRescheduleTimeChange,
  onReschedule,
  onRemove,
  onPublish,
  onStubMetrics,
}: CampaignTimelineRowProps): ReactElement {

  const canChangeTime: boolean = campaignPostCanChangeTime(post.status);
  const offersPublish: boolean = campaignPostOffersPublish(post.status);
  const offersStub: boolean = campaignPostOffersStubMetrics(post.status, post.platform_post_id);
  const isPublishing: boolean = isBusy && busyAction === "publish";
  const failureDetail: string | null = campaignPostFailureDetail(post);

  return (
    <li>
      <p>{post.status}</p>
      {failureDetail === null ? null : <p className="field-error">{failureDetail}</p>}
      <p className="mono">{formatCampaignTimestamp(post.scheduled_for)}</p>
      <p>
        {post.handle} ({post.platform})
      </p>
      {post.caption === null ? null : <p>{post.caption}</p>}
      <ol>
        {post.frames.map((frame: CampaignPostFrameRead): ReactElement => (
          <li key={frame.id}>
            <img
              src={assembledFrameFileUrl(post.carousel_id, frame.id)}
              alt={`${post.handle}, frame ${frame.position + 1}`}
            />
            {frame.blocked && frame.block_detail !== null ? (
              <p className="field-hint">{frame.block_detail}</p>
            ) : null}
          </li>
        ))}
      </ol>
      {post.results === null ? null : (
        <p>
          {formatResultCount(post.results.views)} views,{" "}
          {formatResultCount(post.results.likes)} likes,{" "}
          {formatResultCount(post.results.comments)} comments,{" "}
          {formatResultCount(post.results.shares)} shares
        </p>
      )}
      {canChangeTime ? (
        <div className="button-row">
          <label>
            Time
            <input
              type="datetime-local"
              value={rescheduleTime}
              onChange={(changeEvent): void => {
                onRescheduleTimeChange(changeEvent.target.value);
              }}
              disabled={!canWrite || isBusy}
            />
          </label>
          <button
            id="reschedule-campaign-post"
            type="button"
            disabled={!canWrite || isBusy}
            onClick={onReschedule}
          >
            Change time
          </button>
          <button
            id="remove-campaign-post"
            type="button"
            disabled={!canWrite || isBusy}
            onClick={onRemove}
          >
            Remove
          </button>
        </div>
      ) : null}
      {offersPublish ? (
        <button
          id="publish-campaign-post"
          type="button"
          disabled={!canWrite || isBusy}
          onClick={onPublish}
        >
          {isPublishing ? "Publishing…" : "Publish"}
        </button>
      ) : null}
      {offersStub ? (
        <button
          id="stub-campaign-post-metrics"
          type="button"
          disabled={!canWrite || isBusy}
          onClick={onStubMetrics}
        >
          Record sample results
        </button>
      ) : null}
    </li>
  );
}

function formatResultCount(count: number | null): string {

  if (count === null) {
    return "—";
  }

  return String(count);
}
