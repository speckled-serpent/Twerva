import { useState, type ReactElement } from "react";

import { acceptSlideDraftBatch, discardSlideDraftBatch } from "../api/client";
import type { CarouselReadResponse } from "../api/types";
import {
  COLLECTION_ACCEPT_STATUS,
  COLLECTION_DISCARD_STATUS,
  collectionReviewState,
} from "./carouselCollection";

export interface CarouselCollectionReviewProps {
  carousel: CarouselReadResponse;
  canWrite: boolean;
  onCarouselSaved: (savedCarousel: CarouselReadResponse) => void;
  onStatusMessage: (message: string) => void;
  onError: (error: unknown) => void;
}

/**
 * Accept or discard the generated set, above the slide grid.
 *
 * The block is absent when nothing is pending. A reader sees the
 * sentence and both buttons disabled. Final stays where it is.
 *
 * @param props - The open carousel and the save callbacks
 * @returns The review block, or null when no set is waiting
 */
export function CarouselCollectionReview({
  carousel,
  canWrite,
  onCarouselSaved,
  onStatusMessage,
  onError,
}: CarouselCollectionReviewProps): ReactElement | null {

  const [isWorking, setIsWorking] = useState<boolean>(false);
  const review = collectionReviewState(carousel.pending_slide_draft_batch, canWrite);

  if (!review.reviewVisible || review.pendingBatch === null || review.notice === null) {
    return null;
  }

  const pendingBatchId: string = review.pendingBatch.id;

  const runReview = async (
    request: () => Promise<CarouselReadResponse>,
    statusMessage: string,
  ): Promise<void> => {
    setIsWorking(true);
    onError(null);

    try {
      const savedCarousel: CarouselReadResponse = await request();
      onCarouselSaved(savedCarousel);
      onStatusMessage(statusMessage);
    } catch (caughtError: unknown) {
      onError(caughtError);
    } finally {
      setIsWorking(false);
    }
  };

  return (
    <div className="carousel-collection-review" id="carousel-collection-review">
      <p className="field-hint" id="carousel-collection-review-notice">
        {review.notice}
      </p>
      <div className="button-row">
        <button
          id="accept-slide-draft-batch"
          type="button"
          disabled={!review.canAccept || isWorking}
          onClick={(): void => {
            void runReview(
              (): Promise<CarouselReadResponse> => acceptSlideDraftBatch(
                carousel.id,
                pendingBatchId,
              ),
              COLLECTION_ACCEPT_STATUS,
            );
          }}
        >
          Accept set
        </button>
        <button
          id="discard-slide-draft-batch"
          type="button"
          disabled={!review.canDiscard || isWorking}
          onClick={(): void => {
            void runReview(
              (): Promise<CarouselReadResponse> => discardSlideDraftBatch(
                carousel.id,
                pendingBatchId,
              ),
              COLLECTION_DISCARD_STATUS,
            );
          }}
        >
          Discard set
        </button>
      </div>
    </div>
  );
}
