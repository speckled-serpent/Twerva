import { useEffect, useRef, useState, type ReactElement } from "react";

import { createThemePreview, listSourceItems } from "../api/client";
import type {
  SourceItemReadResponse,
  ThemeElementCreateRequest,
  ThemePatchRequest,
  ThemePreviewRequest,
  ThemePreviewResponse,
  ThemeSampleResponse,
} from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import {
  frameDraftError,
  themePatchFromFrameDraft,
  type ThemeFrameDraft,
} from "./ThemeFrameFields";
import { sampleBlockMessage } from "./themeSampleMessage";

export interface ThemeLivePreviewProps {
  frameDraft: ThemeFrameDraft;
  elements: ThemeElementCreateRequest[] | null;
  draftError: string | null;
}

interface LivePreviewImage {
  sample: ThemeSampleResponse;
  imageUrl: string;
}

const PREVIEW_REFRESH_DELAY_MS: number = 450;

/**
 * One carousel frame from the form as it stands, including unsaved edits.
 *
 * Refresh runs on the button and again 450ms after the form or source
 * changes. Nothing is saved, queued, or published.
 *
 * @param props - Current frame draft, element payload, and a client draft error
 * @returns The preview panel beside the form
 */
export function ThemeLivePreview({
  frameDraft,
  elements,
  draftError,
}: ThemeLivePreviewProps): ReactElement {

  const [sourceItems, setSourceItems] = useState<SourceItemReadResponse[]>([]);
  const [sourceItemId, setSourceItemId] = useState<string>("");
  const [loadError, setLoadError] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [sourcesReady, setSourcesReady] = useState<boolean>(false);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [preview, setPreview] = useState<LivePreviewImage | null>(null);
  const requestSerialRef = useRef<number>(0);
  const previewRef = useRef<LivePreviewImage | null>(null);
  previewRef.current = preview;

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadSources = async (): Promise<void> => {

      try {
        const loadedItems: SourceItemReadResponse[] = await listSourceItems();

        if (isCancelled) {
          return;
        }

        const spotmuItems: SourceItemReadResponse[] = spotmuSourceItems(loadedItems);
        setSourceItems(spotmuItems);
        setSourceItemId((currentId: string): string => {

          if (currentId !== "") {
            return currentId;
          }

          const firstItem: SourceItemReadResponse | undefined = spotmuItems[0];

          if (firstItem === undefined) {
            return "";
          }

          return firstItem.id;
        });
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
      const currentPreview: LivePreviewImage | null = previewRef.current;

      if (currentPreview !== null) {
        URL.revokeObjectURL(currentPreview.imageUrl);
      }
    };
  }, []);

  const refreshPreview = async (): Promise<void> => {

    if (sourceItemId === "" || elements === null || visibleDraftError !== null) {
      return;
    }

    const requestSerial: number = requestSerialRef.current + 1;
    requestSerialRef.current = requestSerial;

    setIsRefreshing(true);
    setActionError(null);

    try {
      const previewRequest: ThemePreviewRequest = previewRequestFromDraft(
        frameDraft,
        elements,
        sourceItemId,
      );
      const previewResponse: ThemePreviewResponse = await createThemePreview(previewRequest);

      if (requestSerialRef.current !== requestSerial) {
        return;
      }

      const imageUrl: string = objectUrlFromPngBase64(previewResponse.image_png_base64);
      const sample: ThemeSampleResponse = {
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
  const payloadKey: string = previewPayloadKey(frameDraft, elements, visibleDraftError);

  useEffect((): (() => void) => {

    if (!sourcesReady || sourceItemId === "" || elements === null || visibleDraftError !== null) {
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
  }, [payloadKey, sourceItemId, sourcesReady]);

  const blockMessage: string | null = (
    visibleDraftError === null
    && preview !== null
    && preview.sample.blocked
  )
    ? sampleBlockMessage(preview.sample)
    : null;
  const refreshDisabled: boolean = (
    !sourcesReady
    || sourceItemId === ""
    || elements === null
    || visibleDraftError !== null
    || isRefreshing
  );

  return (
    <aside className="theme-live-preview summary-block" id="theme-live-preview">
      <h2>Preview</h2>
      <p className="field-hint">
        One Spotmu source, one frame, from the form as it is now. Refresh
        follows edits. This does not save the theme, queue, schedule, or publish.
      </p>
      <ErrorBanner error={loadError} />
      <ErrorBanner error={actionError} />
      {visibleDraftError !== null ? (
        <p className="error-banner" role="alert">{visibleDraftError}</p>
      ) : null}
      {blockMessage !== null ? (
        <p className="error-banner" role="alert">{blockMessage}</p>
      ) : null}
      <label htmlFor="theme-live-preview-source">
        Spotmu source
      </label>
      <select
        id="theme-live-preview-source"
        value={sourceItemId}
        disabled={!sourcesReady || isRefreshing}
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
          id="refresh-theme-preview"
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
        <p className="empty-hint">
          {elements === null
            ? "Preparing preview…"
            : "No preview yet. Choose a Spotmu source."}
        </p>
      ) : (
        <figure
          id="theme-live-preview-figure"
          className={blockMessage !== null ? "sample-preview is-blocked" : "sample-preview"}
        >
          <img
            id="theme-live-preview-image"
            src={preview.imageUrl}
            alt="Theme preview"
          />
          {blockMessage !== null ? <figcaption>{blockMessage}</figcaption> : null}
        </figure>
      )}
    </aside>
  );
}

function previewRequestFromDraft(
  frameDraft: ThemeFrameDraft,
  elements: ThemeElementCreateRequest[],
  sourceItemId: string,
): ThemePreviewRequest {

  const framePatch: ThemePatchRequest = themePatchFromFrameDraft(frameDraft);
  const previewRequest: ThemePreviewRequest = {
    source_item_id: sourceItemId,
    status: framePatch.status ?? "draft",
    page_margin: framePatch.page_margin ?? 96,
    element_gap: framePatch.element_gap ?? 0,
    element_margin: framePatch.element_margin ?? 0,
    background_kind: framePatch.background_kind ?? "color",
    background_color: framePatch.background_color,
    background_gradient: framePatch.background_gradient,
    background_asset_ref: framePatch.background_asset_ref,
    elements,
  };

  return previewRequest;
}

function previewPayloadKey(
  frameDraft: ThemeFrameDraft,
  elements: ThemeElementCreateRequest[] | null,
  draftError: string | null,
): string {

  const payloadKey: string = JSON.stringify({
    frameDraft,
    elements,
    draftError,
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
