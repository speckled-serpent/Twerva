import { useEffect, useState, type KeyboardEvent, type ReactElement } from "react";

import { fetchArtifactSlideImageBlob } from "../api/client";
import type { ArtifactSlide } from "../api/types";
import { readArtifactSlides } from "../slides/readArtifactSlides";

export interface CarouselSlideStripProps {
  artifactId: string;
  slides: ArtifactSlide[] | unknown[] | null;
}

interface SlidePreview {
  slideIndex: number;
  role: string;
  objectUrl: string;
}

/**
 * Horizontal authenticated preview strip with a simple lightbox.
 *
 * Fetches each slide as a blob so the httpOnly session cookie is sent.
 *
 * @param props - Artifact id and slides JSON
 * @returns Preview strip, or null when there are no slides
 */
export function CarouselSlideStrip({
  artifactId,
  slides,
}: CarouselSlideStripProps): ReactElement | null {

  const parsedSlides: ArtifactSlide[] = readArtifactSlides(slides);
  const [slidePreviews, setSlidePreviews] = useState<SlidePreview[]>([]);
  const [loadError, setLoadError] = useState<string>("");
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;
    const objectUrls: string[] = [];

    const loadSlidePreviews = async (): Promise<void> => {

      if (parsedSlides.length === 0) {
        setSlidePreviews([]);
        setLoadError("");

        return;
      }

      const loadedPreviews: SlidePreview[] = [];

      try {
        const imageBlobs: Blob[] = await Promise.all(
          parsedSlides.map((_slide: ArtifactSlide, slideIndex: number): Promise<Blob> => {
            return fetchArtifactSlideImageBlob(artifactId, slideIndex);
          }),
        );

        for (let slideIndex: number = 0; slideIndex < parsedSlides.length; slideIndex += 1) {
          const imageBlob: Blob = imageBlobs[slideIndex];
          const objectUrl: string = URL.createObjectURL(imageBlob);

          objectUrls.push(objectUrl);
          loadedPreviews.push({
            slideIndex,
            role: parsedSlides[slideIndex].role,
            objectUrl,
          });
        }

        if (isCancelled) {
          return;
        }

        setSlidePreviews(loadedPreviews);
        setLoadError("");
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        const errorText: string =
          caughtError instanceof Error ? caughtError.message : String(caughtError);

        setLoadError(errorText);
        setSlidePreviews([]);
      }
    };

    void loadSlidePreviews();

    return (): void => {
      isCancelled = true;

      for (const objectUrl of objectUrls) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [artifactId, parsedSlides.length]);

  if (parsedSlides.length === 0) {
    return null;
  }

  const lightboxPreview: SlidePreview | null =
    lightboxIndex === null ? null : slidePreviews[lightboxIndex] ?? null;

  return (
    <div className="slide-preview">
      {loadError !== "" ? <p className="slide-preview-error">Preview failed: {loadError}</p> : null}
      <div className="slide-preview-strip" aria-label="Carousel slide previews">
        {slidePreviews.map((slidePreview: SlidePreview): ReactElement => (
          <button
            key={`${artifactId}-${slidePreview.slideIndex}`}
            type="button"
            className="slide-preview-thumb-button"
            onClick={(): void => {
              setLightboxIndex(slidePreview.slideIndex);
            }}
          >
            <img
              className="slide-preview-thumb"
              src={slidePreview.objectUrl}
              alt={`${slidePreview.role} slide ${slidePreview.slideIndex + 1}`}
            />
          </button>
        ))}
      </div>
      {lightboxPreview === null ? null : (
        <div
          className="slide-lightbox"
          role="dialog"
          aria-modal="true"
          aria-label="Slide preview"
          tabIndex={0}
          onClick={(): void => {
            setLightboxIndex(null);
          }}
          onKeyDown={(keyboardEvent: KeyboardEvent<HTMLDivElement>): void => {

            if (keyboardEvent.key === "Escape") {
              setLightboxIndex(null);
            }
          }}
        >
          <img
            className="slide-lightbox-image"
            src={lightboxPreview.objectUrl}
            alt={`${lightboxPreview.role} slide ${lightboxPreview.slideIndex + 1} full preview`}
            onClick={(clickEvent): void => {
              clickEvent.stopPropagation();
            }}
          />
          <p className="slide-lightbox-caption">
            {lightboxPreview.role} · {lightboxPreview.slideIndex + 1} / {slidePreviews.length}
            {" · click outside to close"}
          </p>
        </div>
      )}
    </div>
  );
}
