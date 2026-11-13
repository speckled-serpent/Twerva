import { useEffect, useState, type ReactElement } from "react";

import { listTimelinePosts } from "../api/client";
import type { TimelinePostRead } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { formatCampaignTimestamp } from "./campaignDisplay";
import {
  POSTS_EMPTY,
  timelineCampaignName,
  timelinePostStatusLabel,
  timelineResultCounts,
} from "./postsPage";

/**
 * Posts across campaigns. Earlier queue rows have no campaign.
 *
 * This page does not approve, schedule, or publish.
 *
 * @returns The Posts list
 */
export function PostsPage(): ReactElement {

  const [posts, setPosts] = useState<TimelinePostRead[]>([]);
  const [loadError, setLoadError] = useState<unknown>(null);

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadPosts = async (): Promise<void> => {

      try {
        const loadedPosts: TimelinePostRead[] = await listTimelinePosts();

        if (isCancelled) {
          return;
        }

        setPosts(loadedPosts);
        setLoadError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setLoadError(caughtError);
      }
    };

    void loadPosts();

    return (): void => {
      isCancelled = true;
    };
  }, []);

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>Posts</h1>
          <p className="lede">
            Every campaign post, plus earlier queue jobs that have no campaign.
          </p>
        </div>
      </div>
      <ErrorBanner error={loadError} />
      {loadError !== null ? null : posts.length === 0 ? (
        <p className="empty-hint">{POSTS_EMPTY}</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Status</th>
              <th>Time</th>
              <th>Campaign</th>
              <th>Handle</th>
              <th>Caption</th>
              <th>Results</th>
            </tr>
          </thead>
          <tbody>
            {posts.map((post: TimelinePostRead): ReactElement => {
              const resultCounts: string | null = timelineResultCounts(post.results);

              return (
                <tr key={post.id}>
                  <td>{timelinePostStatusLabel(post.status)}</td>
                  <td className="mono">{formatTimelineTime(post.scheduled_for)}</td>
                  <td>{timelineCampaignName(post.campaign_name)}</td>
                  <td>{post.handle}</td>
                  <td>{post.caption === null ? "—" : post.caption}</td>
                  <td>{resultCounts === null ? "—" : resultCounts}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </section>
  );
}

function formatTimelineTime(scheduledFor: string | null): string {

  if (scheduledFor === null) {
    return "—";
  }

  return formatCampaignTimestamp(scheduledFor);
}
