import { useEffect, useState, type ReactElement } from "react";

import {
  createThemeSample,
  fetchThemeSampleImageBlob,
  listSourceItems,
} from "../api/client";
import type {
  SourceItemReadResponse,
  ThemeElementBand,
  ThemeSampleOverlap,
  ThemeSampleResponse,
} from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { useCanWriteOps } from "../session/OpsSessionContext";

export interface ThemeSamplePanelProps {
  themeId: string;
}

interface SamplePreview {
  sample: ThemeSampleResponse;
  imageUrl: string;
}

const BAND_LABELS: Record<ThemeElementBand, string> = {
  top: "Top",
  middle: "Middle",
  bottom: "Bottom",
};

/**
 * Generate one sample preview for a Spotmu source. Nothing is queued.
 *
 * @param props - The open theme
 * @returns The source picker, preview, and block highlight
 */
export function ThemeSamplePanel({ themeId }: ThemeSamplePanelProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [sourceItems, setSourceItems] = useState<SourceItemReadResponse[]>([]);
  const [sourceItemId, setSourceItemId] = useState<string>("");
  const [loadError, setLoadError] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [sourcesReady, setSourcesReady] = useState<boolean>(false);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [preview, setPreview] = useState<SamplePreview | null>(null);
  const generateDisabled: boolean = (
    !canWrite
    || !sourcesReady
    || sourceItemId === ""
    || isGenerating
  );

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadSources = async (): Promise<void> => {

      try {
        const loadedItems: SourceItemReadResponse[] = await listSourceItems();

        if (isCancelled) {
          return;
        }

        setSourceItems(spotmuSourceItems(loadedItems));
        setLoadError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setLoadError(caughtError);
      } finally {
        if (!isCancelled) {
          setSourcesReady(true);
        }
      }
    };

    void loadSources();

    return (): void => {
      isCancelled = true;
    };
  }, []);

  useEffect((): (() => void) => {

    return (): void => {

      if (preview !== null) {
        URL.revokeObjectURL(preview.imageUrl);
      }
    };
  }, [preview]);

  const handleGenerate = async (): Promise<void> => {

    if (!canWrite || sourceItemId === "") {
      return;
    }

    setIsGenerating(true);
    setActionError(null);

    try {
      const sample: ThemeSampleResponse = await createThemeSample(themeId, {
        source_item_id: sourceItemId,
      });
      const imageBlob: Blob = await fetchThemeSampleImageBlob(themeId, sample.preview_id);
      const imageUrl: string = URL.createObjectURL(imageBlob);
      const nextPreview: SamplePreview = { sample, imageUrl };

      setPreview(nextPreview);
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setIsGenerating(false);
    }
  };

  const blockMessage: string | null = preview !== null && preview.sample.blocked
    ? sampleBlockMessage(preview.sample)
    : null;

  return (
    <section className="summary-block">
      <h2>Generate samples</h2>
      <p className="field-hint">
        One Spotmu source, one preview. This does not queue, schedule, or publish.
      </p>
      <ErrorBanner error={loadError} />
      <ErrorBanner error={actionError} />
      {blockMessage !== null ? (
        <p className="error-banner" role="alert">
          {blockMessage}
        </p>
      ) : null}
      <label htmlFor="theme-sample-source">
        Spotmu source
      </label>
      <select
        id="theme-sample-source"
        value={sourceItemId}
        disabled={!canWrite || !sourcesReady || isGenerating}
        onChange={(changeEvent): void => {
          setSourceItemId(changeEvent.target.value);
        }}
      >
        <option value="">Choose a Spotmu source</option>
        {sourceItems.map((sourceItem: SourceItemReadResponse): ReactElement => (
          <option key={sourceItem.id} value={sourceItem.id}>
            {sourceItem.title}
          </option>
        ))}
      </select>
      {sourcesReady && sourceItems.length === 0 ? (
        <p className="empty-hint">No Spotmu source items yet.</p>
      ) : null}
      <div className="button-row">
        <button
          type="button"
          disabled={generateDisabled}
          onClick={(): void => {
            void handleGenerate();
          }}
        >
          {isGenerating ? "Generating…" : "Generate samples"}
        </button>
      </div>
      {preview === null ? (
        <p className="empty-hint">No sample yet. Choose a source, then generate.</p>
      ) : (
        <figure
          id="theme-sample-preview"
          className={preview.sample.blocked ? "sample-preview is-blocked" : "sample-preview"}
        >
          <img src={preview.imageUrl} alt="Theme sample preview" />
          {blockMessage !== null ? <figcaption>{blockMessage}</figcaption> : null}
        </figure>
      )}
    </section>
  );
}

function spotmuSourceItems(sourceItems: SourceItemReadResponse[]): SourceItemReadResponse[] {

  const spotmuItems: SourceItemReadResponse[] = sourceItems.filter(
    (sourceItem: SourceItemReadResponse): boolean => sourceItem.source_type === "spotmu_interest",
  );
  const orderedItems: SourceItemReadResponse[] = [...spotmuItems].sort(
    (left: SourceItemReadResponse, right: SourceItemReadResponse): number => {

      return left.title.localeCompare(right.title);
    },
  );

  return orderedItems;
}

function sampleBlockMessage(sample: ThemeSampleResponse): string {

  if (sample.block_reason === "overlap") {
    const pairText: string = overlapPairText(sample.overlaps);
    const namedPairs: string = pairText !== "" ? pairText : (sample.detail ?? "");

    return joinBlockMessage("overlap", namedPairs);
  }

  if (sample.block_reason === "missing_asset") {

    return joinBlockMessage("missing asset", sample.detail ?? "");
  }

  if (sample.block_reason === "measure_error") {

    return joinBlockMessage("measure error", sample.detail ?? "");
  }

  return "Blocked preview.";
}

function overlapPairText(overlaps: ThemeSampleOverlap[]): string {

  const pairLabels: string[] = overlaps.map((overlap: ThemeSampleOverlap): string => {

    return `${BAND_LABELS[overlap.band_a]} overlaps ${BAND_LABELS[overlap.band_b]}`;
  });

  return pairLabels.join(" ");
}

function joinBlockMessage(reasonLabel: string, detailText: string): string {

  const trimmedDetail: string = detailText.trim();

  if (trimmedDetail === "") {
    return `Blocked: ${reasonLabel}.`;
  }

  return `Blocked: ${reasonLabel}. ${trimmedDetail}`;
}
