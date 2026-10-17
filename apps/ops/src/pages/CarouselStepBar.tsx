import type { ReactElement } from "react";

import type { CarouselStepState, CarouselStepsResponse } from "../api/types";
import {
  carouselStepAccessibleName,
  CAROUSEL_STEPS,
  canOpenCarouselStep,
  generationLabel,
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
 * A locked or not-yet-enabled step uses the existing disabled control.
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

  return (
    <nav className="carousel-stepper" aria-label="Carousel steps">
      <ol>
        {CAROUSEL_STEPS.map((step: CarouselStepDefinition): ReactElement => {

          const stepState: CarouselStepState = stepStateFor(steps, step);
          const isCurrent: boolean = step.index === editorStep;
          const canOpen: boolean = canOpenCarouselStep(step, stepState);
          const className: string = carouselStepClassName(stepState, isCurrent);

          return (
            <li key={step.key}>
              <button
                type="button"
                id={`carousel-step-${step.index}`}
                className={className}
                aria-current={isCurrent ? "step" : undefined}
                aria-label={carouselStepAccessibleName(step, stepState)}
                disabled={!canOpen || isSavingStep}
                onClick={(): void => {

                  if (!stepClickStoresEditorStep(step, stepState, editorStep, canWrite)) {
                    return;
                  }

                  onOpenStep(step.index);
                }}
              >
                <span className="carousel-step-index">{step.index}</span>
                <span>{step.label}</span>
                {stepState === "locked" ? (
                  <span className="carousel-step-mark">Locked</span>
                ) : null}
                {stepState === "done" ? (
                  <span className="carousel-step-mark">Done</span>
                ) : null}
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function carouselStepClassName(stepState: CarouselStepState, isCurrent: boolean): string {

  const classNames: string[] = ["carousel-step"];

  if (isCurrent) {
    classNames.push("is-current");
  }

  if (stepState === "done") {
    classNames.push("is-done");
  }

  if (stepState === "locked") {
    classNames.push("is-locked");
  }

  return classNames.join(" ");
}
