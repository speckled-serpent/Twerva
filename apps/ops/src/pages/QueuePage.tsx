import { useEffect, useState, type ReactElement } from "react";

import {
  approveArtifact,
  listArtifacts,
  listCarouselTemplates,
  patchArtifact,
  regenerateCarouselArtifact,
  rejectArtifact,
} from "../api/client";
import type { ArtifactReadResponse, CarouselTemplateReadResponse } from "../api/types";
import { CarouselSlideStrip } from "../components/CarouselSlideStrip";
import { ErrorBanner } from "../components/ErrorBanner";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import { TemplatePicker } from "../components/TemplatePicker";
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
  const [carouselTemplates, setCarouselTemplates] = useState<CarouselTemplateReadResponse[]>([]);
  const [templateIdByArtifactId, setTemplateIdByArtifactId] = useState<Record<string, string>>({});

  const reloadDrafts = async (): Promise<void> => {

    const loadedDrafts: ArtifactReadResponse[] = await listArtifacts("draft");
    const loadedTemplates: CarouselTemplateReadResponse[] = await listCarouselTemplates();
    const nextCaptions: Record<string, string> = {};
    const nextTemplateIds: Record<string, string> = {};
    const defaultTemplateId: string = resolveDefaultTemplateId(loadedTemplates);

    for (const draftArtifact of loadedDrafts) {
      nextCaptions[draftArtifact.id] = draftArtifact.caption ?? "";
      nextTemplateIds[draftArtifact.id] = draftArtifact.template_id ?? defaultTemplateId;
    }

    setDraftArtifacts(loadedDrafts);
    setCaptionByArtifactId(nextCaptions);
    setCarouselTemplates(loadedTemplates);
    setTemplateIdByArtifactId(nextTemplateIds);
  };

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadPage = async (): Promise<void> => {

      try {
        const loadedDrafts: ArtifactReadResponse[] = await listArtifacts("draft");
        const loadedTemplates: CarouselTemplateReadResponse[] = await listCarouselTemplates();

        if (isCancelled) {
          return;
        }

        const nextCaptions: Record<string, string> = {};
        const nextTemplateIds: Record<string, string> = {};
        const defaultTemplateId: string = resolveDefaultTemplateId(loadedTemplates);

        for (const draftArtifact of loadedDrafts) {
          nextCaptions[draftArtifact.id] = draftArtifact.caption ?? "";
          nextTemplateIds[draftArtifact.id] = draftArtifact.template_id ?? defaultTemplateId;
        }

        setDraftArtifacts(loadedDrafts);
        setCaptionByArtifactId(nextCaptions);
        setCarouselTemplates(loadedTemplates);
        setTemplateIdByArtifactId(nextTemplateIds);
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

  const handleRegenerate = (artifactId: string): void => {

    const selectedTemplateId: string = templateIdByArtifactId[artifactId] ?? "";

    void runArtifactAction(
      artifactId,
      (): Promise<ArtifactReadResponse> => {
        return regenerateCarouselArtifact(artifactId, {
          template_id: selectedTemplateId === "" ? null : selectedTemplateId,
        });
      },
      "Regenerated new draft",
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
        Draft artifacts only. Preview slides, approve / reject, edit caption, or regenerate a new draft with another Spotmu template.
      </p>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      <ErrorBanner error={actionError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}

      {loadError !== null ? null : draftArtifacts.length === 0 ? (
        <p>No drafts yet. Campaign start / generate is not on this page.</p>
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
                  {draftArtifact.template_id !== null && draftArtifact.template_id !== undefined
                    ? ` · ${draftArtifact.template_id}`
                    : ""}
                </p>
                <p className="mono">{draftArtifact.id}</p>
                <p>
                  source {draftArtifact.source_item_id ?? "—"} · cluster{" "}
                  {draftArtifact.cluster_id ?? "—"}
                </p>
                {draftArtifact.cta_url !== null ? <p>CTA {draftArtifact.cta_url}</p> : null}
                <CarouselSlideStrip
                  artifactId={draftArtifact.id}
                  slides={draftArtifact.slides}
                />
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
                {draftArtifact.source_item_id === null ? null : (
                  <div className="regenerate-row">
                    <TemplatePicker
                      templates={carouselTemplates}
                      selectedTemplateId={templateIdByArtifactId[draftArtifact.id] ?? ""}
                      disabled={!canWrite || isBusy}
                      onChange={(templateId: string): void => {
                        setTemplateIdByArtifactId(
                          (previousTemplateIds: Record<string, string>): Record<string, string> => {
                            return {
                              ...previousTemplateIds,
                              [draftArtifact.id]: templateId,
                            };
                          },
                        );
                      }}
                    />
                    <button
                      type="button"
                      disabled={!canWrite || isBusy}
                      onClick={(): void => {
                        handleRegenerate(draftArtifact.id);
                      }}
                    >
                      Regenerate as new draft
                    </button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function resolveDefaultTemplateId(templates: CarouselTemplateReadResponse[]): string {

  const defaultTemplate: CarouselTemplateReadResponse | undefined = templates.find(
    (carouselTemplate: CarouselTemplateReadResponse): boolean => {
      return carouselTemplate.is_default;
    },
  );

  if (defaultTemplate !== undefined) {
    return defaultTemplate.template_id;
  }

  if (templates.length > 0) {
    return templates[0].template_id;
  }

  return "";
}
