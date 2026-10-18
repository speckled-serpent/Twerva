import type { ReactElement } from "react";

import type { CarouselStepState, CarouselStepsResponse } from "../api/types";
import {
  carouselStepAccessibleName,
  carouselStepClassName,
  carouselStepMark,
  CAROUSEL_STEP_INSTRUCTIONS,
  CAROUSEL_STEP_SLIDES,
  CAROUSEL_STEPS,
  canOpenCarouselStep,
  generationLabel,
  SLIDES_ALBUM_REQUIRED_DETAIL,
  stepClickStoresEditorStep,
  stepStateFor,
  type CarouselStepDefinition,
} from "./carouselSteps";

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
 * disabled, and its name says versioned Markdown is a later phase. A
 * reader can open a step to look. That click does not write.
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
          const showsReason: boolean = step.index === CAROUSEL_STEP_INSTRUCTIONS
            || (step.index === CAROUSEL_STEP_SLIDES && stepState === "locked");

          return (
            <li key={step.key}>
              <button
                type="button"
                id={`carousel-step-${step.index}`}
                className={className}
                aria-current={isCurrent ? "step" : undefined}
                aria-label={accessibleName}
                title={showsReason ? accessibleName : undefined}
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
    </nav>
  );
}
