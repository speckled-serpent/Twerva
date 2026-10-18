import type {
  CarouselResearchReadResponse,
  ResearchCreateRequest,
  ResearchListItemResponse,
} from "../api/types";

/** No research is attached. Research never gates a step. */
export const RESEARCH_NONE_ATTACHED_COPY: string =
  "Research is optional. None is attached.";

/** The library has no documents. The form still offers create. */
export const RESEARCH_EMPTY_LIBRARY_COPY: string = "No research yet.";

/** Every library document is already on this carousel. */
export const RESEARCH_ALL_ATTACHED_COPY: string =
  "Every research item is already attached.";

/** Blank title on create. Matches `POST /api/v1/research`. */
export const RESEARCH_TITLE_REQUIRED_COPY: string = "Title is required.";

/** The document body is edited on the Research page, not here. */
export const RESEARCH_BODY_STAYS_COPY: string =
  "The body stays on the Research page.";

/** A reader can see the list and cannot change it. */
export const RESEARCH_READONLY_COPY: string =
  "Changing the research list is an admin action.";

/**
 * Title sent to `POST /api/v1/research`, or null when it is blank.
 *
 * The create route stores an empty body. This step does not send one.
 *
 * @param rawTitle - The title field, before trimming
 * @returns The trimmed title, or null when nothing would be stored
 */
export function trimmedResearchTitle(rawTitle: string): string | null {

  const researchTitle: string = rawTitle.trim();

  if (researchTitle === "") {
    return null;
  }

  return researchTitle;
}

/**
 * Create body for a new research document.
 *
 * Only the title is sent. The server stores an empty body, and the
 * body is written later on the Research page.
 *
 * @param title - Trimmed title
 * @returns The `POST /api/v1/research` body
 */
export function researchCreateRequest(title: string): ResearchCreateRequest {

  const createRequest: ResearchCreateRequest = {
    title,
  };

  return createRequest;
}

/**
 * Attached research in position order.
 *
 * Carousel detail already returns this order. Sorting keeps the list
 * stable if a response arrives out of order. Equal positions fall
 * back to title, then id.
 *
 * @param research - Research on the carousel detail
 * @returns A new list, lowest position first
 */
export function researchInPositionOrder(
  research: readonly CarouselResearchReadResponse[],
): CarouselResearchReadResponse[] {

  const orderedResearch: CarouselResearchReadResponse[] = [...research];
  orderedResearch.sort(compareResearchByPosition);

  return orderedResearch;
}

/**
 * Ids in the list's current order.
 *
 * This does not sort by `position`. A move swaps neighbors and the
 * stale position numbers would undo that swap. The replace route
 * stores this order.
 *
 * @param research - Research in the order to store
 * @returns Ids for `PUT /api/v1/carousels/{id}/research`
 */
export function researchItemIds(
  research: readonly CarouselResearchReadResponse[],
): string[] {

  const researchIds: string[] = research.map(
    (researchItem: CarouselResearchReadResponse): string => researchItem.id,
  );

  return researchIds;
}

/**
 * Swap one attached document with its neighbor.
 *
 * Out of range returns null and the stored order stays.
 *
 * @param research - Current display order
 * @param researchIndex - Index of the document to move
 * @param direction - -1 up, 1 down
 * @returns The new order, or null when the move does not fit
 */
export function moveAttachedResearch(
  research: readonly CarouselResearchReadResponse[],
  researchIndex: number,
  direction: -1 | 1,
): CarouselResearchReadResponse[] | null {

  const nextIndex: number = researchIndex + direction;

  if (nextIndex < 0 || nextIndex >= research.length) {
    return null;
  }

  const nextResearch: CarouselResearchReadResponse[] = [...research];
  const movingResearch: CarouselResearchReadResponse | undefined = nextResearch[researchIndex];
  const swappedResearch: CarouselResearchReadResponse | undefined = nextResearch[nextIndex];

  if (movingResearch === undefined || swappedResearch === undefined) {
    return null;
  }

  nextResearch[researchIndex] = swappedResearch;
  nextResearch[nextIndex] = movingResearch;

  return nextResearch;
}

/**
 * Library documents that are not already attached.
 *
 * Removing a link puts that document back in this list. The research
 * row itself stays in the library. Titles sort like the Research page.
 *
 * @param library - Documents from `GET /api/v1/research`
 * @param attached - Research currently on the carousel
 * @returns Documents the operator can add, in title order
 */
export function researchToChoose(
  library: readonly ResearchListItemResponse[],
  attached: readonly CarouselResearchReadResponse[],
): ResearchListItemResponse[] {

  const attachedIds: string[] = attached.map(
    (researchItem: CarouselResearchReadResponse): string => researchItem.id,
  );
  const attachedIdSet: Set<string> = new Set(attachedIds);
  const availableResearch: ResearchListItemResponse[] = library.filter(
    (researchItem: ResearchListItemResponse): boolean => !attachedIdSet.has(researchItem.id),
  );
  const orderedResearch: ResearchListItemResponse[] = [...availableResearch];
  orderedResearch.sort(compareLibraryByTitle);

  return orderedResearch;
}

/**
 * Sentence for a failed add, create, remove, or reorder.
 *
 * A 400 or 404 uses the API detail. The stored list stays on failure.
 *
 * @param error - Caught request failure
 * @returns The reason shown in the form
 */
export function researchActionErrorText(error: unknown): string {

  const detailText: string | null = detailTextFromError(error);

  if (detailText !== null) {
    return detailText;
  }

  if (error instanceof Error && error.message !== "") {
    return error.message;
  }

  return "The research list could not be changed.";
}

function compareResearchByPosition(
  left: CarouselResearchReadResponse,
  right: CarouselResearchReadResponse,
): number {

  if (left.position !== right.position) {
    return left.position - right.position;
  }

  const titleOrder: number = left.title.localeCompare(right.title);

  if (titleOrder !== 0) {
    return titleOrder;
  }

  return left.id.localeCompare(right.id);
}

function compareLibraryByTitle(
  left: ResearchListItemResponse,
  right: ResearchListItemResponse,
): number {

  const titleOrder: number = left.title.localeCompare(right.title);

  if (titleOrder !== 0) {
    return titleOrder;
  }

  return left.id.localeCompare(right.id);
}

function detailTextFromError(error: unknown): string | null {

  if (typeof error !== "object" || error === null || !("detailText" in error)) {
    return null;
  }

  const detailText: unknown = error.detailText;

  if (typeof detailText !== "string" || detailText === "") {
    return null;
  }

  return detailText;
}
