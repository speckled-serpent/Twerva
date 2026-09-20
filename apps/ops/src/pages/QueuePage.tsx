import { useEffect, useState, type ReactElement } from "react";

import { approveArtifact, listArtifacts, patchArtifact, rejectArtifact } from "../api/client";
import type { ArtifactReadResponse } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import { useCanWriteOps } from "../session/OpsSessionContext";

/**
 * Queue page: draft artifacts with approve / reject / caption edit.
 *
 * @returns The Queue page
 */
export function QueuePage(): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [draftArtifacts, setDraftArtifacts] = useState<ArtifactReadResponse[]>([]);
  const [captionByArtifactId, setCaptionByArtifactId] = useState<Record<string, string>>({});
  const [loadError, setLoadError] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [busyArtifactId, setBusyArtifactId] = useState<string>("");

  const reloadDrafts = async (): Promise<void> => {

    const loadedDrafts: ArtifactReadResponse[] = await listArtifacts("draft");
    const nextCaptions: Record<string, string> = {};

    for (const draftArtifact of loadedDrafts) {
      nextCaptions[draftArtifact.id] = draftArtifact.caption ?? "";
    }

    setDraftArtifacts(loadedDrafts);
    setCaptionByArtifactId(nextCaptions);
  };

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadPage = async (): Promise<void> => {

      try {
        const loadedDrafts: ArtifactReadResponse[] = await listArtifacts("draft");

        if (isCancelled) {
          return;
        }

        const nextCaptions: Record<string, string> = {};

        for (const draftArtifact of loadedDrafts) {
          nextCaptions[draftArtifact.id] = draftArtifact.caption ?? "";
        }

        setDraftArtifacts(loadedDrafts);
        setCaptionByArtifactId(nextCaptions);
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

  const runArtifactAction = async (
    artifactId: string,
    action: () => Promise<ArtifactReadResponse>,
    successText: string,
  ): Promise<void> => {

    setBusyArtifactId(artifactId);
    setActionError(null);
    setStatusMessage("");

    try {
      const updatedArtifact: ArtifactReadResponse = await action();

      setStatusMessage(`${successText} (${updatedArtifact.id} → ${updatedArtifact.status})`);
      await reloadDrafts();
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setBusyArtifactId("");
    }
  };

  const handleApprove = (artifactId: string): void => {

    const caption: string = captionByArtifactId[artifactId] ?? "";

    void runArtifactAction(
      artifactId,
      (): Promise<ArtifactReadResponse> => approveArtifact(artifactId, { caption }),
      "Approved",
    );
  };

  const handleReject = (artifactId: string): void => {

    void runArtifactAction(
      artifactId,
      (): Promise<ArtifactReadResponse> => rejectArtifact(artifactId),
      "Rejected",
    );
  };

  const handleSaveCaption = (artifactId: string): void => {

    const caption: string = captionByArtifactId[artifactId] ?? "";

    void runArtifactAction(
      artifactId,
      (): Promise<ArtifactReadResponse> => patchArtifact(artifactId, { caption }),
      "Saved caption",
    );
  };

  return (
    <section>
      <h1>Queue</h1>
      <p className="lede">
        Draft artifacts only. Approve / reject, or PATCH the caption before approve.
      </p>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      <ErrorBanner error={actionError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}

      {loadError !== null ? null : draftArtifacts.length === 0 ? (
        <p>No drafts. Generate a carousel on Sources.</p>
      ) : (
        <ul className="card-list">
          {draftArtifacts.map((draftArtifact: ArtifactReadResponse): ReactElement => {
            const isBusy: boolean = busyArtifactId === draftArtifact.id;
            const captionValue: string = captionByArtifactId[draftArtifact.id] ?? "";
            const slideCount: number = Array.isArray(draftArtifact.slides)
              ? draftArtifact.slides.length
              : 0;

            return (
              <li key={draftArtifact.id} className="card">
                <p>
                  <strong>{draftArtifact.format}</strong> · {draftArtifact.status} · {slideCount} slides
                </p>
                <p className="mono">{draftArtifact.id}</p>
                <p>
                  source {draftArtifact.source_item_id ?? "—"} · cluster{" "}
                  {draftArtifact.cluster_id ?? "—"}
                </p>
                {draftArtifact.cta_url !== null ? <p>CTA {draftArtifact.cta_url}</p> : null}
                <label>
                  Caption
                  <textarea
                    rows={5}
                    value={captionValue}
                    onChange={(changeEvent): void => {
                      const nextCaption: string = changeEvent.target.value;

                      setCaptionByArtifactId((previousCaptions: Record<string, string>): Record<string, string> => {
                        return {
                          ...previousCaptions,
                          [draftArtifact.id]: nextCaption,
                        };
                      });
                    }}
                  />
                </label>
                <div className="button-row">
                  <button
                    type="button"
                    disabled={!canWrite || isBusy}
                    onClick={(): void => {
                      handleSaveCaption(draftArtifact.id);
                    }}
                  >
                    Save caption
                  </button>
                  <button
                    type="button"
                    disabled={!canWrite || isBusy}
                    onClick={(): void => {
                      handleApprove(draftArtifact.id);
                    }}
                  >
                    Approve
                  </button>
                  <button
                    type="button"
                    className="danger"
                    disabled={!canWrite || isBusy}
                    onClick={(): void => {
                      handleReject(draftArtifact.id);
                    }}
                  >
                    Reject
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
