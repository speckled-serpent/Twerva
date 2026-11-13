import type { ReactElement } from "react";

import type { CarouselReadResponse } from "../api/types";
import {
  INSTRUCTIONS_GENERATE_HINT,
  instructionsAfterGenerateClick,
  instructionsGenerateAccessibleName,
} from "./carouselInstructions";

export interface CarouselGenerateControlProps {
  carousel: CarouselReadResponse;
  enabled: boolean;
}

/**
 * Generate for the whole carousel, placed under Content.
 *
 * Enabled only when some instruction document has real text. A reader
 * stays disabled. The click does not fill slides until a later phase.
 *
 * @param props - The open carousel and whether the button can be pressed
 * @returns The button and the later-phase note
 */
export function CarouselGenerateControl({
  carousel,
  enabled,
}: CarouselGenerateControlProps): ReactElement {

  return (
    <div className="carousel-generate" id="carousel-generate">
      <div className="button-row">
        <button
          id="generate-instructions"
          type="button"
          disabled={!enabled}
          aria-label={instructionsGenerateAccessibleName(enabled)}
          onClick={(): void => {
            instructionsAfterGenerateClick(carousel);
          }}
        >
          Generate
        </button>
      </div>
      <p className="field-hint" id="generate-instructions-hint">
        {INSTRUCTIONS_GENERATE_HINT}
      </p>
    </div>
  );
}
