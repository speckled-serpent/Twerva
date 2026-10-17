import { useEffect, useRef, useState, type ReactElement } from "react";

import { createSkeletonPreview } from "../api/client";
import type {
  SkeletonPatchRequest,
  SkeletonPreviewElementRequest,
  SkeletonPreviewRequest,
  SkeletonPreviewResponse,
  SkeletonSampleResponse,
} from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import {
  frameDraftError,
  skeletonPatchFromFrameDraft,
  type SkeletonFrameDraft,
} from "./SkeletonFrameFields";
import {
  type SkeletonPreviewDraftElement,
} from "./SkeletonElementEditor";
import { sampleBlockMessage } from "./skeletonSampleMessage";
import {
  PREVIEW_WORD_COUNT_MAX,
  PREVIEW_WORD_COUNT_MIN,
  loremIpsumWords,
  previewWordCountFromInput,
  textElementsInFrameOrder,
  wordCountForElement,
} from "./skeletonPreviewText";

export interface SkeletonLivePreviewProps {
  frameDraft: SkeletonFrameDraft;
  elements: SkeletonPreviewDraftElement[] | null;
  draftError: string | null;
}

interface LivePreviewImage {
  sample: SkeletonSampleResponse;
  imageUrl: string;
}

const PREVIEW_REFRESH_DELAY_MS: number = 450;

/**
 * One carousel frame from the form as it stands, including unsaved edits.
 *
 * Each text element has a word count. The preview draws that many lorem
 * ipsum words. Counts stay in this panel and are not saved. Refresh runs
 * on the button and again 450ms after the form or a count changes.
 *
 * @param props - Current frame draft, element payload, and a client draft error
 * @returns The preview panel beside the form
 */
export function SkeletonLivePreview({
  frameDraft,
  elements,
  draftError,
}: SkeletonLivePreviewProps): ReactElement {

  const [wordCounts, setWordCounts] = useState<Record<string, number>>({});
  const [actionError, setActionError] = useState<unknown>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [preview, setPreview] = useState<LivePreviewImage | null>(null);
  const requestSerialRef = useRef<number>(0);
  const previewRef = useRef<LivePreviewImage | null>(null);
  previewRef.current = preview;

  useEffect((): (() => void) => {

    return (): void => {
      const currentPreview: LivePreviewImage | null = previewRef.current;

      if (currentPreview !== null) {
        URL.revokeObjectURL(currentPreview.imageUrl);
      }
    };
  }, []);

  const textElements: SkeletonPreviewDraftElement[] = elements === null
    ? []
    : textElementsInFrameOrder(elements);

  const refreshPreview = async (): Promise<void> => {

    if (elements === null || visibleDraftError !== null) {
      return;
    }

    const requestSerial: number = requestSerialRef.current + 1;
    requestSerialRef.current = requestSerial;

    setIsRefreshing(true);
    setActionError(null);

    try {
      const previewRequest: SkeletonPreviewRequest = previewRequestFromDraft(
        frameDraft,
        elements,
        wordCounts,
      );
      const previewResponse: SkeletonPreviewResponse = await createSkeletonPreview(previewRequest);

      if (requestSerialRef.current !== requestSerial) {
        return;
      }

      const imageUrl: string = objectUrlFromPngBase64(previewResponse.image_png_base64);
      const sample: SkeletonSampleResponse = {
        preview_id: "",
        blocked: previewResponse.blocked,
        block_reason: previewResponse.block_reason,
        detail: previewResponse.detail,
        overlaps: previewResponse.overlaps,
      };
      const nextPreview: LivePreviewImage = { sample, imageUrl };

      setPreview((currentPreview: LivePreviewImage | null): LivePreviewImage => {

        if (currentPreview !== null) {
          URL.revokeObjectURL(currentPreview.imageUrl);
        }

        return nextPreview;
      });
    } catch (caughtError: unknown) {
      if (requestSerialRef.current !== requestSerial) {
        return;
      }

      setActionError(caughtError);
    } finally {
      if (requestSerialRef.current === requestSerial) {
        setIsRefreshing(false);
      }
    }
  };

  const frameError: string | null = frameDraftError(frameDraft);
  const visibleDraftError: string | null = draftError ?? frameError;
  const payloadKey: string = previewPayloadKey(
    frameDraft,
    elements,
    visibleDraftError,
    wordCounts,
  );

  useEffect((): (() => void) => {

    if (elements === null || visibleDraftError !== null) {
      return (): void => {
        return;
      };
    }

    const refreshHandle: number = window.setTimeout((): void => {
      void refreshPreview();
    }, PREVIEW_REFRESH_DELAY_MS);

    return (): void => {
      window.clearTimeout(refreshHandle);
    };
  }, [payloadKey]);

  const rememberWordCount = (elementId: string, rawValue: string): void => {

    const parsedCount: number | null = previewWordCountFromInput(rawValue);

    setWordCounts((currentCounts: Record<string, number>): Record<string, number> => {

      if (parsedCount === null) {
        return { ...currentCounts };
      }

      const nextCounts: Record<string, number> = {
        ...currentCounts,
        [elementId]: parsedCount,
      };

      return nextCounts;
    });
  };

  const blockMessage: string | null = (
    visibleDraftError === null
    && preview !== null
    && preview.sample.blocked
  )
    ? sampleBlockMessage(preview.sample)
    : null;
  const refreshDisabled: boolean = (
    elements === null
    || visibleDraftError !== null
    || isRefreshing
  );

  return (
    <aside className="skeleton-live-preview summary-block" id="skeleton-live-preview">
      <h2>Preview</h2>
      <p className="field-hint">
        One frame from the form as it is now. Word counts choose lorem
        ipsum so you can judge appearance. Refresh follows edits. This
        does not save the skeleton, queue, schedule, or publish.
      </p>
      <ErrorBanner error={actionError} />
      {visibleDraftError !== null ? (
        <p className="error-banner" role="alert">{visibleDraftError}</p>
      ) : null}
      {blockMessage !== null ? (
        <p className="error-banner" role="alert">{blockMessage}</p>
      ) : null}
      {textElements.length > 0 ? (
        <div className="preview-word-counts" role="group" aria-label="Preview word counts">
          {textElements.map((element: SkeletonPreviewDraftElement): ReactElement => {
            const inputId: string = `skeleton-preview-words-${element.element_id}`;
            const wordCount: number = wordCountForElement(wordCounts, element.element_id);

            return (
              <label key={element.element_id} htmlFor={inputId}>
                <span className="toolbar-caption">{element.name}</span>
                <input
                  id={inputId}
                  type="number"
                  min={PREVIEW_WORD_COUNT_MIN}
                  max={PREVIEW_WORD_COUNT_MAX}
                  step={1}
                  inputMode="numeric"
                  value={wordCount}
                  aria-label={`${element.name} word count`}
                  onChange={(changeEvent): void => {
                    rememberWordCount(element.element_id, changeEvent.target.value);
                  }}
                  onBlur={(blurEvent): void => {
                    rememberWordCount(element.element_id, blurEvent.target.value);
                  }}
                />
              </label>
            );
          })}
        </div>
      ) : null}
      <div className="button-row">
        <button
          id="refresh-skeleton-preview"
          type="button"
          disabled={refreshDisabled}
          onClick={(): void => {
            void refreshPreview();
          }}
        >
          {isRefreshing ? "Refreshing…" : "Refresh preview"}
        </button>
      </div>
      {preview === null ? (
        <p className="empty-hint">Preparing preview…</p>
      ) : (
        <figure
          id="skeleton-live-preview-figure"
          className={blockMessage !== null ? "sample-preview is-blocked" : "sample-preview"}
        >
          <img
            id="skeleton-live-preview-image"
            src={preview.imageUrl}
            alt="Skeleton preview"
          />
          {blockMessage !== null ? <figcaption>{blockMessage}</figcaption> : null}
        </figure>
      )}
    </aside>
  );
}

function previewRequestFromDraft(
  frameDraft: SkeletonFrameDraft,
  elements: SkeletonPreviewDraftElement[],
  wordCounts: Record<string, number>,
): SkeletonPreviewRequest {

  const framePatch: SkeletonPatchRequest = skeletonPatchFromFrameDraft(frameDraft);
  const previewElements: SkeletonPreviewElementRequest[] = elements.map(
    (element: SkeletonPreviewDraftElement): SkeletonPreviewElementRequest => {

      return previewElementRequest(element, wordCounts);
    },
  );
  const previewRequest: SkeletonPreviewRequest = {
    page_margin: framePatch.page_margin ?? 96,
    element_gap: framePatch.element_gap ?? 0,
    element_margin: framePatch.element_margin ?? 0,
    background_kind: framePatch.background_kind ?? "color",
    background_color: framePatch.background_color,
    background_gradient: framePatch.background_gradient,
    background_asset_ref: framePatch.background_asset_ref,
    elements: previewElements,
  };

  return previewRequest;
}

function previewElementRequest(
  element: SkeletonPreviewDraftElement,
  wordCounts: Record<string, number>,
): SkeletonPreviewElementRequest {

  const previewText: string | null = element.content_kind === "text"
    ? loremIpsumWords(wordCountForElement(wordCounts, element.element_id))
    : null;
  const previewElement: SkeletonPreviewElementRequest = {
    name: element.name,
    band: element.band,
    content_kind: element.content_kind,
    sort_order: element.sort_order,
    rectangle_color: element.rectangle_color,
    rectangle_opacity: element.rectangle_opacity,
    rectangle_radius: element.rectangle_radius,
    text_source: element.text_source,
    font_family: element.font_family,
    font_size: element.font_size,
    font_color: element.font_color,
    bold: element.bold,
    italic: element.italic,
    underline: element.underline,
    strikethrough: element.strikethrough,
    font_weight: element.font_weight,
    alignment: element.alignment,
    image_asset_ref: element.image_asset_ref,
    preview_text: previewText,
  };

  return previewElement;
}

function previewPayloadKey(
  frameDraft: SkeletonFrameDraft,
  elements: SkeletonPreviewDraftElement[] | null,
  draftError: string | null,
  wordCounts: Record<string, number>,
): string {

  const counts: Record<string, number> = {};

  if (elements !== null) {
    const textElements: SkeletonPreviewDraftElement[] = textElementsInFrameOrder(elements);

    textElements.forEach((element: SkeletonPreviewDraftElement): void => {
      counts[element.element_id] = wordCountForElement(wordCounts, element.element_id);
    });
  }

  const payloadKey: string = JSON.stringify({
    frameDraft,
    elements,
    draftError,
    counts,
  });

  return payloadKey;
}

function objectUrlFromPngBase64(imagePngBase64: string): string {

  const binary: string = window.atob(imagePngBase64);
  const buffer: ArrayBuffer = new ArrayBuffer(binary.length);
  const bytes: Uint8Array = new Uint8Array(buffer);

  for (let index: number = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }

  const imageBlob: Blob = new Blob([buffer], { type: "image/png" });
  const imageUrl: string = URL.createObjectURL(imageBlob);

  return imageUrl;
}
