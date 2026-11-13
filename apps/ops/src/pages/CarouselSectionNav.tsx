import type { ReactElement } from "react";

import {
  CAROUSEL_PAGE_SECTIONS,
  type CarouselPageSection,
} from "./carouselPage";
import { generationLabel } from "./carouselSteps";

export interface CarouselGenerationProps {
  generationNumber: number;
}

/**
 * Pill for the stored generation number.
 *
 * Duplicate sits beside this pill on the open carousel. The slide editor
 * keeps the pill only. The page does not switch generations.
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

/**
 * Links that scroll to each carousel section.
 *
 * They do not switch a step, store `editor_step`, or hide a section.
 *
 * @returns The section links
 */
export function CarouselSectionNav(): ReactElement {

  return (
    <nav className="carousel-section-nav" aria-label="Carousel sections">
      <ol>
        {CAROUSEL_PAGE_SECTIONS.map((section: CarouselPageSection): ReactElement => (
          <li key={section.id}>
            <a href={section.href}>{section.label}</a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
