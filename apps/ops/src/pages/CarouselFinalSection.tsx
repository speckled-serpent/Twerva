import { useState, type ReactElement } from "react";

import { assembleCarousel, assembledFrameFileUrl } from "../api/client";
import type { AssembledFrameReadResponse, CarouselReadResponse } from "../api/types";
import {
  finalAssembleAccessibleName,
  finalAssembleEnabled,
  finalAssembleStatusMessage,
  finalAssemblyView,
  type FinalAssemblyGroupView,
  type FinalAssemblyView,
} from "./finalAssembly";

export interface CarouselFinalSectionProps {
  carousel: CarouselReadResponse;
  canWrite: boolean;
  onCarouselSaved: (savedCarousel: CarouselReadResponse) => void;
  onStatusMessage: (message: string) => void;
  onError: (error: unknown) => void;
}

/**
 * Assemble the live slides and show the frozen frames.
 *
 * The empty sentence is the only copy when this generation has no
 * assembly. A reader, and a carousel with fewer than two live slides,
 * see Assemble disabled.
 *
 * @param props - The open carousel and the save callbacks
 * @returns The Final controls and, when present, the grouped frames
 */
export function CarouselFinalSection({
  carousel,
  canWrite,
  onCarouselSaved,
  onStatusMessage,
  onError,
}: CarouselFinalSectionProps): ReactElement {

  const [isAssembling, setIsAssembling] = useState<boolean>(false);
  const enabled: boolean = finalAssembleEnabled(canWrite, carousel.live_slide_count);
  const accessibleName: string = isAssembling
    ? "Assembling…"
    : finalAssembleAccessibleName(carousel.live_slide_count);
  const view: FinalAssemblyView = finalAssemblyView(carousel.assembly);

  const runAssemble = async (): Promise<void> => {
    setIsAssembling(true);
    onError(null);

    try {
      const savedCarousel: CarouselReadResponse = await assembleCarousel(carousel.id);
      const nextView: FinalAssemblyView = finalAssemblyView(savedCarousel.assembly);
      onCarouselSaved(savedCarousel);
      onStatusMessage(finalAssembleStatusMessage(nextView.groups.length));
    } catch (caughtError: unknown) {
      onError(caughtError);
    } finally {
      setIsAssembling(false);
    }
  };

  return (
    <div className="carousel-final" id="carousel-final-body">
      {view.emptyNotice === null ? null : (
        <p className="field-hint" id="carousel-final-notice">
          {view.emptyNotice}
        </p>
      )}
      <div className="button-row">
        <button
          id="assemble-final"
          type="button"
          disabled={!enabled || isAssembling}
          aria-label={accessibleName}
          onClick={(): void => {
            void runAssemble();
          }}
        >
          {isAssembling ? "Assembling…" : "Assemble"}
        </button>
      </div>
      {view.groups.length === 0 ? null : (
        <ol className="carousel-final-groups">
          {view.groups.map((group: FinalAssemblyGroupView): ReactElement => (
            <li key={group.id}>
              <h3>{group.label}</h3>
              {group.caption === null ? null : <p>{group.caption}</p>}
              <ol className="carousel-final-frames">
                {group.frames.map((frame: AssembledFrameReadResponse): ReactElement => (
                  <li key={frame.id}>
                    <img
                      src={assembledFrameFileUrl(carousel.id, frame.id)}
                      alt={`${group.label}, frame ${frame.position + 1}`}
                    />
                    {frame.blocked && frame.block_detail !== null ? (
                      <p className="field-hint">{frame.block_detail}</p>
                    ) : null}
                  </li>
                ))}
              </ol>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
