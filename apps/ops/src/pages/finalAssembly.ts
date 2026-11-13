import type {
  AssembledCarouselReadResponse,
  AssembledFrameReadResponse,
  CarouselAssemblyReadResponse,
} from "../api/types";

/** Shown when this generation has no assembly yet. */
export const FINAL_EMPTY_NOTICE: string =
  "No assembly yet. Assemble draws the live slides with this skeleton.";

/** Accessible name when fewer than two slides are live. */
export const FINAL_ASSEMBLE_NEEDS_SLIDES: string =
  "Assemble. Add at least two live slides first.";

/** Live slides required before Assemble is enabled. */
export const FINAL_ASSEMBLE_MINIMUM_LIVE_SLIDES: number = 2;

/**
 * One assembled carousel as the Final section lists it.
 */
export interface FinalAssemblyGroupView {
  id: string;
  label: string;
  caption: string | null;
  frames: AssembledFrameReadResponse[];
}

/**
 * What Final shows for the current assembly.
 */
export interface FinalAssemblyView {
  emptyNotice: string | null;
  groups: FinalAssemblyGroupView[];
}

/**
 * Whether Assemble can be pressed.
 *
 * An admin needs at least two live slides. A reader stays disabled.
 *
 * @param canWrite - True for an admin
 * @param liveSlideCount - Slides whose text is live
 * @returns True when the button can be pressed
 */
export function finalAssembleEnabled(canWrite: boolean, liveSlideCount: number): boolean {

  if (!canWrite) {
    return false;
  }

  return liveSlideCount >= FINAL_ASSEMBLE_MINIMUM_LIVE_SLIDES;
}

/**
 * Accessible name for Assemble.
 *
 * Fewer than two live slides names that reason. Otherwise the name is Assemble.
 *
 * @param liveSlideCount - Slides whose text is live
 * @returns The accessible name
 */
export function finalAssembleAccessibleName(liveSlideCount: number): string {

  if (liveSlideCount < FINAL_ASSEMBLE_MINIMUM_LIVE_SLIDES) {
    return FINAL_ASSEMBLE_NEEDS_SLIDES;
  }

  return "Assemble";
}

/**
 * Status line after a successful assemble.
 *
 * @param groupCount - How many assembled carousels the response stored
 * @returns The status sentence
 */
export function finalAssembleStatusMessage(groupCount: number): string {

  return `Assembled ${groupCount} carousels.`;
}

/**
 * The Final section for an assembly response.
 *
 * A null assembly is the empty sentence. Groups stay in position order,
 * labeled Carousel 1, Carousel 2, and so on. Frames stay in position order.
 *
 * @param assembly - The generation's assembly, or null
 * @returns The empty sentence, or the ordered groups
 */
export function finalAssemblyView(
  assembly: CarouselAssemblyReadResponse | null,
): FinalAssemblyView {

  if (assembly === null) {
    const emptyView: FinalAssemblyView = {
      emptyNotice: FINAL_EMPTY_NOTICE,
      groups: [],
    };

    return emptyView;
  }

  const orderedCarousels: AssembledCarouselReadResponse[] = [...assembly.carousels].sort(
    (left: AssembledCarouselReadResponse, right: AssembledCarouselReadResponse): number =>
      left.position - right.position,
  );
  const groups: FinalAssemblyGroupView[] = orderedCarousels.map(
    (group: AssembledCarouselReadResponse): FinalAssemblyGroupView => {
      const frames: AssembledFrameReadResponse[] = [...group.frames].sort(
        (left: AssembledFrameReadResponse, right: AssembledFrameReadResponse): number =>
          left.position - right.position,
      );
      const groupView: FinalAssemblyGroupView = {
        id: group.id,
        label: `Carousel ${group.position + 1}`,
        caption: group.caption,
        frames,
      };

      return groupView;
    },
  );
  const filledView: FinalAssemblyView = {
    emptyNotice: null,
    groups,
  };

  return filledView;
}
