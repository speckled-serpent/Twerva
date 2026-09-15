import { useEffect, useState, type ReactElement } from "react";

import {
  createStubPostJobMetrics,
  fetchClusterAgentSummaryJson,
  fetchClusterAgentSummaryMarkdown,
  fetchClusterMetricsSummary,
  listClusters,
} from "../api/client";
import type {
  AgentSummaryPostJob,
  ClusterAgentSummaryResponse,
  ClusterMetricsSummaryResponse,
  ClusterReadResponse,
  MetricSnapshotReadResponse,
} from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";

/**
 * Results page: cluster median summary, stub metrics, agent-summary pane.
 *
 * @returns The Results page
 */
export function ResultsPage(): ReactElement {

  const [clusters, setClusters] = useState<ClusterReadResponse[]>([]);
  const [clusterId, setClusterId] = useState<string>("");
  const [metricsSummary, setMetricsSummary] = useState<ClusterMetricsSummaryResponse | null>(null);
  const [agentSummaryJson, setAgentSummaryJson] = useState<ClusterAgentSummaryResponse | null>(null);
  const [agentSummaryMarkdown, setAgentSummaryMarkdown] = useState<string>("");
  const [stubPostJobId, setStubPostJobId] = useState<string>("");
  const [loadError, setLoadError] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [isBusy, setIsBusy] = useState<boolean>(false);

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadClusters = async (): Promise<void> => {

      try {
        const loadedClusters: ClusterReadResponse[] = await listClusters();

        if (isCancelled) {
          return;
        }

        setClusters(loadedClusters);
        setLoadError(null);

        if (loadedClusters.length > 0) {
          setClusterId(loadedClusters[0].id);
        }
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setLoadError(caughtError);
      }
    };

    void loadClusters();

    return (): void => {
      isCancelled = true;
    };
  }, []);

  const loadClusterResults = async (selectedClusterId: string): Promise<void> => {

    if (selectedClusterId === "") {
      setMetricsSummary(null);
      setAgentSummaryJson(null);
      setAgentSummaryMarkdown("");
      setStubPostJobId("");

      return;
    }

    const loadedMetricsSummary: ClusterMetricsSummaryResponse =
      await fetchClusterMetricsSummary(selectedClusterId);
    const loadedAgentSummaryJson: ClusterAgentSummaryResponse =
      await fetchClusterAgentSummaryJson(selectedClusterId);
    const loadedAgentSummaryMarkdown: string =
      await fetchClusterAgentSummaryMarkdown(selectedClusterId);

    setMetricsSummary(loadedMetricsSummary);
    setAgentSummaryJson(loadedAgentSummaryJson);
    setAgentSummaryMarkdown(loadedAgentSummaryMarkdown);

    if (loadedAgentSummaryJson.recent_post_jobs.length > 0) {
      setStubPostJobId(loadedAgentSummaryJson.recent_post_jobs[0].id);
    } else {
      setStubPostJobId("");
    }
  };

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadResults = async (): Promise<void> => {

      if (clusterId === "") {
        return;
      }

      try {
        await loadClusterResults(clusterId);

        if (isCancelled) {
          return;
        }

        setLoadError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setLoadError(caughtError);
      }
    };

    void loadResults();

    return (): void => {
      isCancelled = true;
    };
  }, [clusterId]);

  const handleStubMetrics = async (): Promise<void> => {

    setIsBusy(true);
    setActionError(null);
    setStatusMessage("");

    try {
      const metricSnapshot: MetricSnapshotReadResponse = await createStubPostJobMetrics(
        stubPostJobId,
      );

      setStatusMessage(
        `Stub metrics ${metricSnapshot.views} views on ${metricSnapshot.post_job_id}`,
      );
      await loadClusterResults(clusterId);
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setIsBusy(false);
    }
  };

  const medianLabel: string =
    metricsSummary === null || metricsSummary.median_views === null
      ? "null"
      : String(metricsSummary.median_views);

  return (
    <section>
      <h1>Results</h1>
      <p className="lede">
        Cluster median views and the agent-summary. Stub metrics only work on mock-published jobs.
      </p>
      <ErrorBanner error={loadError} />
      <ErrorBanner error={actionError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}

      <label>
        Cluster
        <select
          value={clusterId}
          onChange={(changeEvent): void => {
            setClusterId(changeEvent.target.value);
          }}
        >
          <option value="">Select a cluster</option>
          {clusters.map((cluster: ClusterReadResponse): ReactElement => (
            <option key={cluster.id} value={cluster.id}>
              {cluster.slug} / {cluster.name}
            </option>
          ))}
        </select>
      </label>

      {metricsSummary !== null ? (
        <div className="summary-block">
          <h2>Median summary</h2>
          <p>post_job_count: {metricsSummary.post_job_count}</p>
          <p>snapshot_job_count: {metricsSummary.snapshot_job_count}</p>
          <p>views_job_count: {metricsSummary.views_job_count}</p>
          <p>median_views: {medianLabel}</p>
        </div>
      ) : null}

      <h2>Stub metrics</h2>
      <div className="stack-form">
        <label>
          Post job (from recent agent-summary)
          <select
            value={stubPostJobId}
            onChange={(changeEvent): void => {
              setStubPostJobId(changeEvent.target.value);
            }}
          >
            <option value="">Select a post job</option>
            {(agentSummaryJson?.recent_post_jobs ?? []).map((postJob: AgentSummaryPostJob): ReactElement => (
              <option key={postJob.id} value={postJob.id}>
                {postJob.id} · {postJob.status} · views {postJob.latest_views ?? "null"}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          disabled={isBusy || stubPostJobId === ""}
          onClick={(): void => {
            void handleStubMetrics();
          }}
        >
          POST stub metrics
        </button>
      </div>

      <h2>Agent summary (markdown)</h2>
      <pre className="agent-summary">{agentSummaryMarkdown || "(empty)"}</pre>
    </section>
  );
}
