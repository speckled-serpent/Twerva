import { useEffect, useState, type ReactElement } from "react";

import { fetchSkeletonById } from "../api/client";
import type { CarouselReadResponse, SkeletonReadResponse } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { generationLabel } from "./carouselSteps";
import type { CarouselLabelDraft } from "./carouselLabel";
import { SkeletonAutosaveStatus } from "./SkeletonAutosaveStatus";
import type { SkeletonAutosaveState } from "./skeletonAutosave";

export interface CarouselBasicStepProps {
  carousel: CarouselReadResponse;
  canWrite: boolean;
  labelDraft: CarouselLabelDraft;
  autosaveState: SkeletonAutosaveState;
  onLabelChange: (name: string) => void;
  onRetry: () => void;
}

/**
 * Step 0: generation, the locked skeleton, and the label.
 *
 * The skeleton is text. There is no control to change it, including when
 * the carousel has no slides. Another skeleton means delete and create.
 *
 * @param props - The open carousel, the label draft, and the autosave status
 * @returns The Basic step
 */
export function CarouselBasicStep({
  carousel,
  canWrite,
  labelDraft,
  autosaveState,
  onLabelChange,
  onRetry,
}: CarouselBasicStepProps): ReactElement {

  const [skeleton, setSkeleton] = useState<SkeletonReadResponse | null>(null);
  const [skeletonError, setSkeletonError] = useState<unknown>(null);

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;
    const skeletonId: string = carousel.skeleton_id;

    const loadSkeleton = async (): Promise<void> => {

      try {
        const loadedSkeleton: SkeletonReadResponse = await fetchSkeletonById(skeletonId);

        if (isCancelled) {
          return;
        }

        setSkeleton(loadedSkeleton);
        setSkeletonError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setSkeleton(null);
        setSkeletonError(caughtError);
      }
    };

    void loadSkeleton();

    return (): void => {
      isCancelled = true;
    };
  }, [carousel.skeleton_id]);

  const skeletonName: string = skeletonNameText(skeleton, skeletonError);

  return (
    <section id="carousel-basic" className="carousel-basic stack-form" aria-label="Basic">
      <p id="carousel-basic-generation" className="carousel-basic-generation">
        {generationLabel(carousel.generation_number)}
      </p>
      <ErrorBanner error={skeletonError} />
      <div className="carousel-locked-skeleton">
        <p className="carousel-basic-kicker">Skeleton</p>
        <p id="carousel-skeleton-name" className="carousel-skeleton-name">
          {skeletonName}
        </p>
        <p className="field-hint" id="carousel-skeleton-locked">
          Delete this carousel and create a new one to change the skeleton.
        </p>
      </div>
      <label>
        Label
        <input
          id="carousel-label"
          value={labelDraft.name}
          disabled={!canWrite}
          autoComplete="off"
          onChange={(changeEvent): void => {
            onLabelChange(changeEvent.target.value);
          }}
        />
      </label>
      <p className="field-hint">The label saves on its own.</p>
      <SkeletonAutosaveStatus state={autosaveState} onRetry={onRetry} />
    </section>
  );
}

function skeletonNameText(
  skeleton: SkeletonReadResponse | null,
  skeletonError: unknown,
): string {

  if (skeleton !== null) {
    return skeleton.name;
  }

  if (skeletonError !== null) {
    return "This skeleton is not available.";
  }

  return "Loading skeleton…";
}
