import type { ReactElement } from "react";

import type { CarouselStepState, CarouselStepsResponse } from "../api/types";
import {
  carouselStepAccessibleName,
  carouselStepClassName,
  carouselStepMark,
  carouselStepTitle,
  CAROUSEL_STEP_SLIDES,
  CAROUSEL_STEPS,
  canOpenCarouselStep,
  generationLabel,
  SLIDES_ALBUM_REQUIRED_DETAIL,
  stepClickStoresEditorStep,
  stepStateFor,
  type CarouselStepDefinition,
} from "./carouselSteps";
import { slideCountFallbackHint } from "./slideCountFallback";

export interface CarouselGenerationProps {
  generationNumber: number;
}

/**
 * Pill for the stored generation number. The shell shows "Generation 1" now.
 *
 * @param props - Stored generation number
 * @returns The generation pill
 */
export function CarouselGeneration({
  generationNumber,
}: CarouselGenerationProps): ReactElement {

  return (
    <p className="carousel-generation" id="carousel-generation">
      {generationLabel(generationNumber)}
    </p>
  );
}

export interface CarouselStepBarProps {
  editorStep: number;
  steps: CarouselStepsResponse;
  canWrite: boolean;
  isSavingStep: boolean;
  onOpenStep: (editorStep: number) => void;
}

/**
 * Five pill controls for the carousel steps.
 *
 * The open step uses the teal primary. A done step uses the success color.
 * A locked step uses the existing disabled control. Available stays
 * unmarked. Slides follows `steps.slides`: locked, it stays disabled and
 * its name says to attach an album on Content first. Instructions stays
 * disabled, and its name says versioned Markdown is a later phase.
 * Final stays disabled, and its name says final assembly is a later
 * phase. That name is also the tooltip. A reader can open a step to
 * look. That click does not write. Final does not navigate. While
 * Slides is open, one hint names the global slide-count default. That
 * hint is absent on the other steps and while Slides is locked.
 *
 * @param props - Stored step, derived states, and the step PATCH callback
 * @returns The stepper
 */
export function CarouselStepBar({
  editorStep,
  steps,
  canWrite,
  isSavingStep,
  onOpenStep,
}: CarouselStepBarProps): ReactElement {

  const slidesDefinition: CarouselStepDefinition | undefined = CAROUSEL_STEPS.find(
    (step: CarouselStepDefinition): boolean => step.index === CAROUSEL_STEP_SLIDES,
  );
  const slidesState: CarouselStepState = slidesDefinition === undefined
    ? "locked"
    : stepStateFor(steps, slidesDefinition);
  const slidesLocked: boolean = slidesState === "locked";
  const slideCountHint: string | null = slideCountFallbackHint(editorStep, slidesState);

  return (
    <nav className="carousel-stepper" aria-label="Carousel steps">
      <ol>
        {CAROUSEL_STEPS.map((step: CarouselStepDefinition): ReactElement => {

          const stepState: CarouselStepState = stepStateFor(steps, step);
          const isCurrent: boolean = step.index === editorStep;
          const canOpen: boolean = canOpenCarouselStep(step, stepState);
          const accessibleName: string = carouselStepAccessibleName(step, stepState);
          const className: string = carouselStepClassName(stepState, isCurrent);
          const mark: string | null = carouselStepMark(stepState);
          const closedTitle: string | undefined = carouselStepTitle(step, stepState);

          return (
            <li key={step.key}>
              <button
                type="button"
                id={`carousel-step-${step.index}`}
                className={className}
                aria-current={isCurrent ? "step" : undefined}
                aria-label={accessibleName}
                title={closedTitle}
                disabled={!canOpen || isSavingStep}
                onClick={(): void => {

                  if (!canOpen) {
                    return;
                  }

                  const storesStep: boolean = stepClickStoresEditorStep(
                    step,
                    stepState,
                    editorStep,
                    canWrite,
                  );

                  if (!storesStep && canWrite) {
                    return;
                  }

                  onOpenStep(step.index);
                }}
              >
                <span className="carousel-step-index">{step.index}</span>
                <span>{step.label}</span>
                {mark === null ? null : (
                  <span className="carousel-step-mark">{mark}</span>
                )}
              </button>
            </li>
          );
        })}
      </ol>
      {slidesLocked ? (
        <p className="field-hint" id="carousel-slides-locked">
          {SLIDES_ALBUM_REQUIRED_DETAIL}
        </p>
      ) : null}
      {slideCountHint === null ? null : (
        <p className="field-hint" id="carousel-slide-count-fallback">
          {slideCountHint}
        </p>
      )}
    </nav>
  );
}
