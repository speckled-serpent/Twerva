import { useEffect, useRef, useState, type ReactElement } from "react";

import { previewSourceUnit } from "../api/client";
import type {
  ThemePreviewResponse,
  ThemeSampleResponse,
  UnitElementTextWrite,
} from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { sampleBlockMessage } from "./themeSampleMessage";

export interface UnitLivePreviewProps {
  sourceId: string;
  unitId: string | null;
  texts: UnitElementTextWrite[];
}

interface LivePreviewImage {
  sample: ThemeSampleResponse;
  imageUrl: string;
}

const PREVIEW_REFRESH_DELAY_MS: number = 450;

/**
 * One frame of the source's theme filled from this unit.
 *
 * Refresh runs 450ms after the text changes. The image is the one
 * already saved on the unit. Nothing is saved, queued, or published.
 *
 * @param props - Source, optional saved unit, and the text in the form
 * @returns The preview panel beside the unit form
 */
export function UnitLivePreview({
  sourceId,
  unitId,
  texts,
}: UnitLivePreviewProps): ReactElement {

  const [actionError, setActionError] = useState<unknown>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [preview, setPreview] = useState<LivePreviewImage | null>(null);
  const requestSerialRef = useRef<number>(0);
  const previewRef = useRef<LivePreviewImage | null>(null);
  previewRef.current = preview;
  const payloadKey: string = JSON.stringify({ sourceId, unitId, texts });

  const refreshPreview = async (): Promise<void> => {
    const requestSerial: number = requestSerialRef.current + 1;
    requestSerialRef.current = requestSerial;

    setIsRefreshing(true);
    setActionError(null);

    try {
      const previewResponse: ThemePreviewResponse = await previewSourceUnit(sourceId, {
        texts,
        unit_id: unitId,
      });

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

  useEffect((): (() => void) => {

    return (): void => {
      const currentPreview: LivePreviewImage | null = previewRef.current;

      if (currentPreview !== null) {
        URL.revokeObjectURL(currentPreview.imageUrl);
      }
    };
  }, []);

  useEffect((): (() => void) => {
    const refreshHandle: number = window.setTimeout((): void => {
      void refreshPreview();
    }, PREVIEW_REFRESH_DELAY_MS);

    return (): void => {
      window.clearTimeout(refreshHandle);
    };
  }, [payloadKey]);

  const blockMessage: string | null = preview !== null && preview.sample.blocked
    ? sampleBlockMessage(preview.sample)
    : null;

  return (
    <aside className="theme-live-preview summary-block" id="unit-live-preview">
      <h2>Preview</h2>
      <p className="field-hint">
        This frame uses the source theme and the text in the form. The image
        is the one already saved on the unit. This does not save a campaign.
      </p>
      <ErrorBanner error={actionError} />
      {blockMessage !== null ? (
        <p className="error-banner" role="alert">{blockMessage}</p>
      ) : null}
      <div className="button-row">
        <button
          id="refresh-unit-preview"
          type="button"
          disabled={isRefreshing}
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
          id="unit-live-preview-figure"
          className={blockMessage !== null ? "sample-preview is-blocked" : "sample-preview"}
        >
          <img
            id="unit-live-preview-image"
            src={preview.imageUrl}
            alt="Unit preview"
          />
          {blockMessage !== null ? <figcaption>{blockMessage}</figcaption> : null}
        </figure>
      )}
    </aside>
  );
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
