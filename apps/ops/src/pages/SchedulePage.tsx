import { useEffect, useState, type FormEvent, type ReactElement } from "react";

import {
  listAccounts,
  listArtifacts,
  listPostJobs,
  publishPostJob,
  schedulePostJob,
} from "../api/client";
import type {
  AccountReadResponse,
  ArtifactReadResponse,
  PostJobReadResponse,
} from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";

/**
 * Build a datetime-local value one hour from now.
 *
 * @returns A local datetime string for an input
 */
function defaultScheduledForValue(): string {

  const scheduledDate: Date = new Date();
  scheduledDate.setHours(scheduledDate.getHours() + 1);
  const yearText: string = String(scheduledDate.getFullYear());
  const monthText: string = String(scheduledDate.getMonth() + 1).padStart(2, "0");
  const dayText: string = String(scheduledDate.getDate()).padStart(2, "0");
  const hourText: string = String(scheduledDate.getHours()).padStart(2, "0");
  const minuteText: string = String(scheduledDate.getMinutes()).padStart(2, "0");

  return `${yearText}-${monthText}-${dayText}T${hourText}:${minuteText}`;
}

/**
 * Schedule page: create a post job from an approved artifact, then mock-publish.
 *
 * @returns The Schedule page
 */
export function SchedulePage(): ReactElement {

  const [approvedArtifacts, setApprovedArtifacts] = useState<ArtifactReadResponse[]>([]);
  const [accounts, setAccounts] = useState<AccountReadResponse[]>([]);
  const [postJobs, setPostJobs] = useState<PostJobReadResponse[]>([]);
  const [artifactId, setArtifactId] = useState<string>("");
  const [accountId, setAccountId] = useState<string>("");
  const [scheduledFor, setScheduledFor] = useState<string>(defaultScheduledForValue);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [busyPostJobId, setBusyPostJobId] = useState<string>("");
  const [isBusy, setIsBusy] = useState<boolean>(false);

  const reloadLists = async (): Promise<void> => {

    const loadedApprovedArtifacts: ArtifactReadResponse[] = await listArtifacts("approved");
    const loadedAccounts: AccountReadResponse[] = await listAccounts();
    const loadedPostJobs: PostJobReadResponse[] = await listPostJobs();

    setApprovedArtifacts(loadedApprovedArtifacts);
    setAccounts(loadedAccounts);
    setPostJobs(loadedPostJobs);

    if (artifactId === "" && loadedApprovedArtifacts.length > 0) {
      setArtifactId(loadedApprovedArtifacts[0].id);
    }

    if (accountId === "" && loadedAccounts.length > 0) {
      setAccountId(loadedAccounts[0].id);
    }
  };

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadPage = async (): Promise<void> => {

      try {
        const loadedApprovedArtifacts: ArtifactReadResponse[] = await listArtifacts("approved");
        const loadedAccounts: AccountReadResponse[] = await listAccounts();
        const loadedPostJobs: PostJobReadResponse[] = await listPostJobs();

        if (isCancelled) {
          return;
        }

        setApprovedArtifacts(loadedApprovedArtifacts);
        setAccounts(loadedAccounts);
        setPostJobs(loadedPostJobs);
        setLoadError(null);

        if (loadedApprovedArtifacts.length > 0) {
          setArtifactId(loadedApprovedArtifacts[0].id);
        }

        if (loadedAccounts.length > 0) {
          setAccountId(loadedAccounts[0].id);
        }
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

  const handleSchedule = async (formEvent: FormEvent): Promise<void> => {

    formEvent.preventDefault();
    setIsBusy(true);
    setActionError(null);
    setStatusMessage("");

    const scheduledDate: Date = new Date(scheduledFor);

    if (Number.isNaN(scheduledDate.getTime())) {
      setActionError(new Error("scheduled_for is not a valid datetime."));
      setIsBusy(false);

      return;
    }

    try {
      const createdPostJob: PostJobReadResponse = await schedulePostJob({
        artifact_id: artifactId,
        account_id: accountId,
        scheduled_for: scheduledDate.toISOString(),
      });

      setStatusMessage(`Scheduled post job ${createdPostJob.id}`);
      await reloadLists();
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setIsBusy(false);
    }
  };

  const handleMockPublish = async (postJobId: string): Promise<void> => {

    setBusyPostJobId(postJobId);
    setActionError(null);
    setStatusMessage("");

    try {
      const publishedPostJob: PostJobReadResponse = await publishPostJob(postJobId);

      setStatusMessage(
        `Published ${publishedPostJob.id} → ${publishedPostJob.status}` +
          (publishedPostJob.platform_post_id !== null
            ? ` (${publishedPostJob.platform_post_id})`
            : ""),
      );
      await reloadLists();
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setBusyPostJobId("");
    }
  };

  return (
    <section>
      <h1>Schedule</h1>
      <p className="lede">
        Attach an approved artifact to an account and time, then mock-publish the post job.
      </p>
      <ErrorBanner error={loadError} />
      <ErrorBanner error={actionError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}

      <h2>Create post job</h2>
      <form className="stack-form" onSubmit={(formEvent: FormEvent): void => {
        void handleSchedule(formEvent);
      }}>
        <label>
          Approved artifact
          <select
            value={artifactId}
            onChange={(changeEvent): void => {
              setArtifactId(changeEvent.target.value);
            }}
            required
          >
            <option value="">Select an approved artifact</option>
            {approvedArtifacts.map((artifact: ArtifactReadResponse): ReactElement => (
              <option key={artifact.id} value={artifact.id}>
                {artifact.id} · cluster {artifact.cluster_id ?? "none"}
              </option>
            ))}
          </select>
        </label>
        <label>
          Account
          <select
            value={accountId}
            onChange={(changeEvent): void => {
              setAccountId(changeEvent.target.value);
            }}
            required
          >
            <option value="">Select an account</option>
            {accounts.map((account: AccountReadResponse): ReactElement => (
              <option key={account.id} value={account.id}>
                {account.platform} @{account.handle} (cluster {account.cluster_id})
              </option>
            ))}
          </select>
        </label>
        <label>
          scheduled_for
          <input
            type="datetime-local"
            value={scheduledFor}
            onChange={(changeEvent): void => {
              setScheduledFor(changeEvent.target.value);
            }}
            required
          />
        </label>
        <button type="submit" disabled={isBusy || artifactId === "" || accountId === ""}>
          Schedule
        </button>
      </form>

      <h2>Post jobs</h2>
      {loadError !== null ? null : postJobs.length === 0 ? (
        <p>No post jobs yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Status</th>
              <th>Scheduled</th>
              <th>Platform post</th>
              <th>ID</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {postJobs.map((postJob: PostJobReadResponse): ReactElement => {
              const canPublish: boolean =
                postJob.status === "scheduled" || postJob.status === "failed";
              const isRowBusy: boolean = busyPostJobId === postJob.id;

              return (
                <tr key={postJob.id}>
                  <td>{postJob.status}</td>
                  <td>{postJob.scheduled_for ?? "—"}</td>
                  <td className="mono">{postJob.platform_post_id ?? "—"}</td>
                  <td className="mono">{postJob.id}</td>
                  <td>
                    {canPublish ? (
                      <button
                        type="button"
                        disabled={isRowBusy}
                        onClick={(): void => {
                          void handleMockPublish(postJob.id);
                        }}
                      >
                        {isRowBusy ? "Publishing…" : "Mock publish"}
                      </button>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </section>
  );
}
