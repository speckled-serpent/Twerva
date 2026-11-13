import type { CarouselStepsResponse } from "../api/types";
import {
  CAROUSEL_STEPS,
  FINAL_CLOSED_DETAIL,
  SLIDES_ALBUM_REQUIRED_DETAIL,
  type CarouselStepDefinition,
} from "./carouselSteps.ts";

/**
 * One heading on the carousel page.
 *
 * The label is the heading text. The href is an in-page anchor.
 * The page does not read `editor_step` to decide whether to show it.
 */
export interface CarouselPageSection {
  id: string;
  label: string;
  href: string;
  key: CarouselStepDefinition["key"];
}

/**
 * A block in the stacked editor.
 *
 * Generate is a control, not a heading. It sits after Content.
 */
export type CarouselEditorBlock =
  | { kind: "section"; key: CarouselPageSection["key"] }
  | { kind: "generate" };

/**
 * Headings in scroll order: Basic, Instructions, Content, Slides, Final.
 */
export const CAROUSEL_PAGE_SECTIONS: readonly CarouselPageSection[] = CAROUSEL_STEPS.map(
  (step: CarouselStepDefinition): CarouselPageSection => {

    const sectionId: string = `carousel-${step.key}`;

    return {
      id: sectionId,
      label: step.label,
      href: `#${sectionId}`,
      key: step.key,
    };
  },
);

/**
 * What the open carousel stacks, top to bottom.
 *
 * Generate follows Content and comes before Slides.
 */
export const CAROUSEL_EDITOR_BLOCKS: readonly CarouselEditorBlock[] = [
  { kind: "section", key: "basic" },
  { kind: "section", key: "instructions" },
  { kind: "section", key: "content" },
  { kind: "generate" },
  { kind: "section", key: "slides" },
  { kind: "section", key: "final" },
];

/** List lede. Opening a carousel shows every section, not a stored step. */
export const CAROUSEL_LIST_LEDE: string =
  "Each carousel has a skeleton. Open one to edit every section on one page.";

/**
 * The section for a heading key.
 *
 * @param key - basic, instructions, content, slides, or final
 * @returns That section's id, label, and anchor
 */
export function carouselPageSection(
  key: CarouselPageSection["key"],
): CarouselPageSection {

  const found: CarouselPageSection | undefined = CAROUSEL_PAGE_SECTIONS.find(
    (section: CarouselPageSection): boolean => section.key === key,
  );

  if (found === undefined) {
    throw new Error(`Unknown carousel section ${key}.`);
  }

  return found;
}

/**
 * Whether a section stays on the page.
 *
 * A stored `editor_step` does not hide a section. A locked Slides or
 * Final state does not hide it either. An id that is not a page section
 * is not shown.
 *
 * @param section - A heading, or an id that is not on this page
 * @param editorStep - `carousels.editor_step`, ignored for visibility
 * @param steps - Derived step states, ignored for visibility
 * @returns True for every real section
 */
export function sectionIsVisible(
  section: CarouselPageSection,
  editorStep: number,
  steps: CarouselStepsResponse,
): boolean {

  const knownSection: boolean = CAROUSEL_PAGE_SECTIONS.some(
    (candidate: CarouselPageSection): boolean => candidate.id === section.id,
  );

  void editorStep;
  void steps;

  return knownSection;
}

/**
 * Why Slides cannot use a picture yet.
 *
 * A picture carousel with no album used to hide Slides. The section
 * stays, and this sentence says to attach an album on Content first.
 * Research does not lock Slides.
 *
 * @param steps - Derived step states from the carousel detail
 * @returns The album sentence, or null when Slides is available or done
 */
export function slidesSectionNotice(steps: CarouselStepsResponse): string | null {

  if (steps.slides !== "locked") {
    return null;
  }

  return SLIDES_ALBUM_REQUIRED_DETAIL;
}

/**
 * Why Final has no assembly controls.
 *
 * Final is a heading on the page. The assembly itself is a later phase.
 *
 * @returns The later-phase sentence
 */
export function finalSectionNotice(): string {

  return FINAL_CLOSED_DETAIL;
}

/**
 * Lede under the carousel name.
 *
 * It does not name a stored open step.
 *
 * @param liveSlideCount - How many slides are live
 * @returns The page lede, including the live count
 */
export function carouselPageLede(liveSlideCount: number): string {

  return `Basic, instructions, content, and slides are on this page. A card shows the first image, or the text when there is none. ${liveSlideCount} live.`;
}
