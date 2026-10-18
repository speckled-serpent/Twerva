import { useEffect, useState, type FormEvent, type ReactElement } from "react";

import {
  appendCarouselResearch,
  createResearch,
  listResearch,
  removeCarouselResearch,
  replaceCarouselResearch,
} from "../api/client";
import type {
  CarouselReadResponse,
  CarouselResearchReadResponse,
  ResearchListItemResponse,
  ResearchReadResponse,
} from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import {
  RESEARCH_ALL_ATTACHED_COPY,
  RESEARCH_BODY_STAYS_COPY,
  RESEARCH_EMPTY_LIBRARY_COPY,
  RESEARCH_NONE_ATTACHED_COPY,
  RESEARCH_READONLY_COPY,
  RESEARCH_TITLE_REQUIRED_COPY,
  moveAttachedResearch,
  researchActionErrorText,
  researchCreateRequest,
  researchInPositionOrder,
  researchItemIds,
  researchToChoose,
  trimmedResearchTitle,
} from "./carouselResearch";

export interface CarouselResearchSectionProps {
  carousel: CarouselReadResponse;
  canWrite: boolean;
  onCarouselSaved: (savedCarousel: CarouselReadResponse) => void;
}

/**
 * Attached research under the album on Content.
 *
 * The list is position order. The operator adds an existing document,
 * creates one with a title (an empty body, then attach), removes a
 * link, or reorders. Removing a link leaves the document on the
 * Research page. Research is optional and does not change step state,
 * so a picture skeleton can still open Slides with this list empty.
 * A reader can look and cannot change the list.
 *
 * @param props - The open carousel and the write callback
 * @returns The research block
 */
export function CarouselResearchSection({
  carousel,
  canWrite,
  onCarouselSaved,
}: CarouselResearchSectionProps): ReactElement {

  const [trackedCarouselId, setTrackedCarouselId] = useState<string>(carousel.id);
  const [library, setLibrary] = useState<ResearchListItemResponse[] | null>(null);
  const [libraryError, setLibraryError] = useState<unknown>(null);
  const [selectedResearchId, setSelectedResearchId] = useState<string>("");
  const [newTitle, setNewTitle] = useState<string>("");
  const [isWorking, setIsWorking] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);

  if (carousel.id !== trackedCarouselId) {
    setTrackedCarouselId(carousel.id);
    setLibrary(null);
    setLibraryError(null);
    setSelectedResearchId("");
    setNewTitle("");
    setFormError(null);
  }

  useEffect((): (() => void) => {
    if (!canWrite) {
      return (): void => {
        return;
      };
    }

    let isCancelled: boolean = false;

    const loadLibrary = async (): Promise<void> => {

      try {
        const loadedResearch: ResearchListItemResponse[] = await listResearch();

        if (isCancelled) {
          return;
        }

        setLibrary(loadedResearch);
        setLibraryError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setLibrary([]);
        setLibraryError(caughtError);
      }
    };

    void loadLibrary();

    return (): void => {
      isCancelled = true;
    };
  }, [canWrite, carousel.id]);

  const orderedResearch: CarouselResearchReadResponse[] = researchInPositionOrder(
    carousel.research,
  );
  const choiceResearch: ResearchListItemResponse[] = researchToChoose(
    library ?? [],
    orderedResearch,
  );

  const handleAdd = async (): Promise<void> => {

    if (!canWrite || isWorking || selectedResearchId === "") {
      return;
    }

    setIsWorking(true);
    setFormError(null);

    try {
      const updatedCarousel: CarouselReadResponse = await appendCarouselResearch(carousel.id, {
        research_item_id: selectedResearchId,
      });
      setSelectedResearchId("");
      onCarouselSaved(updatedCarousel);
    } catch (caughtError: unknown) {
      setFormError(researchActionErrorText(caughtError));
    } finally {
      setIsWorking(false);
    }
  };

  const handleCreate = async (): Promise<void> => {

    if (!canWrite || isWorking) {
      return;
    }

    const researchTitle: string | null = trimmedResearchTitle(newTitle);

    if (researchTitle === null) {
      setFormError(RESEARCH_TITLE_REQUIRED_COPY);

      return;
    }

    setIsWorking(true);
    setFormError(null);

    try {
      const createdResearch: ResearchReadResponse = await createResearch(
        researchCreateRequest(researchTitle),
      );
      setNewTitle("");

      try {
        const loadedResearch: ResearchListItemResponse[] = await listResearch();
        setLibrary(loadedResearch);
        setLibraryError(null);
      } catch (listError: unknown) {
        setLibraryError(listError);
      }

      const updatedCarousel: CarouselReadResponse = await appendCarouselResearch(carousel.id, {
        research_item_id: createdResearch.id,
      });
      onCarouselSaved(updatedCarousel);
    } catch (caughtError: unknown) {
      setFormError(researchActionErrorText(caughtError));
    } finally {
      setIsWorking(false);
    }
  };

  const handleRemove = async (researchItemId: string): Promise<void> => {

    if (!canWrite || isWorking) {
      return;
    }

    setIsWorking(true);
    setFormError(null);

    try {
      const updatedCarousel: CarouselReadResponse = await removeCarouselResearch(
        carousel.id,
        researchItemId,
      );
      onCarouselSaved(updatedCarousel);
    } catch (caughtError: unknown) {
      setFormError(researchActionErrorText(caughtError));
    } finally {
      setIsWorking(false);
    }
  };

  const handleMove = async (researchIndex: number, direction: -1 | 1): Promise<void> => {

    if (!canWrite || isWorking) {
      return;
    }

    const movedResearch: CarouselResearchReadResponse[] | null = moveAttachedResearch(
      orderedResearch,
      researchIndex,
      direction,
    );

    if (movedResearch === null) {
      return;
    }

    setIsWorking(true);
    setFormError(null);

    try {
      const updatedCarousel: CarouselReadResponse = await replaceCarouselResearch(carousel.id, {
        research_item_ids: researchItemIds(movedResearch),
      });
      onCarouselSaved(updatedCarousel);
    } catch (caughtError: unknown) {
      setFormError(researchActionErrorText(caughtError));
    } finally {
      setIsWorking(false);
    }
  };

  return (
    <section id="carousel-research" className="carousel-research" aria-label="Research">
      <div className="carousel-research-panel" id="carousel-research-status">
        <p className="carousel-basic-kicker">Research</p>
        <p className="field-hint" id="carousel-research-body">
          {RESEARCH_BODY_STAYS_COPY}
        </p>
        {orderedResearch.length === 0 ? (
          <p id="carousel-research-none" className="carousel-research-note">
            {RESEARCH_NONE_ATTACHED_COPY}
          </p>
        ) : (
          <ol
            id="carousel-research-list"
            className="carousel-research-list"
            aria-label="Attached research"
          >
            {orderedResearch.map((
              researchItem: CarouselResearchReadResponse,
              researchIndex: number,
            ): ReactElement => (
              <ResearchRow
                key={researchItem.id}
                researchItem={researchItem}
                researchIndex={researchIndex}
                isFirst={researchIndex === 0}
                isLast={researchIndex === orderedResearch.length - 1}
                canWrite={canWrite}
                isWorking={isWorking}
                onMove={(direction: -1 | 1): void => {
                  void handleMove(researchIndex, direction);
                }}
                onRemove={(): void => {
                  void handleRemove(researchItem.id);
                }}
              />
            ))}
          </ol>
        )}
      </div>
      <ErrorBanner error={libraryError} />
      {canWrite ? (
        <form
          id="carousel-research-form"
          className="carousel-research-form"
          onSubmit={(submitEvent: FormEvent<HTMLFormElement>): void => {
            submitEvent.preventDefault();

            if (trimmedResearchTitle(newTitle) !== null) {
              void handleCreate();

              return;
            }

            void handleAdd();
          }}
        >
          {library === null && libraryError === null ? (
            <p className="field-hint" id="carousel-research-loading">
              Loading research…
            </p>
          ) : null}
          {library !== null && libraryError === null && library.length === 0 ? (
            <p className="empty-hint" id="carousel-research-empty">
              {RESEARCH_EMPTY_LIBRARY_COPY}
            </p>
          ) : null}
          {library !== null && libraryError === null && library.length > 0 && choiceResearch.length === 0 ? (
            <p className="field-hint" id="carousel-research-all-attached">
              {RESEARCH_ALL_ATTACHED_COPY}
            </p>
          ) : null}
          {choiceResearch.length > 0 ? (
            <>
              <label>
                Existing research
                <select
                  id="carousel-research-select"
                  value={selectedResearchId}
                  disabled={isWorking}
                  onChange={(changeEvent): void => {
                    setSelectedResearchId(changeEvent.target.value);
                    setFormError(null);
                  }}
                >
                  <option value="">Choose research</option>
                  {choiceResearch.map((researchItem: ResearchListItemResponse): ReactElement => (
                    <option key={researchItem.id} value={researchItem.id}>
                      {researchItem.title}
                    </option>
                  ))}
                </select>
              </label>
              <div className="button-row">
                <button
                  id="carousel-research-add"
                  type="button"
                  className="primary"
                  disabled={isWorking || selectedResearchId === ""}
                  onClick={(): void => {
                    void handleAdd();
                  }}
                >
                  {isWorking ? "Saving…" : "Add research"}
                </button>
              </div>
            </>
          ) : null}
          <label>
            New research title
            <input
              id="carousel-research-create-title"
              value={newTitle}
              disabled={isWorking}
              autoComplete="off"
              onChange={(changeEvent): void => {
                setNewTitle(changeEvent.target.value);
                setFormError(null);
              }}
            />
          </label>
          <div className="button-row">
            <button
              id="carousel-research-create"
              type="button"
              className="primary"
              disabled={isWorking}
              onClick={(): void => {
                void handleCreate();
              }}
            >
              {isWorking ? "Saving…" : "Create research"}
            </button>
          </div>
          {formError === null ? null : (
            <p className="field-error" id="carousel-research-error" role="alert">
              {formError}
            </p>
          )}
        </form>
      ) : (
        <p className="field-hint" id="carousel-research-readonly">
          {RESEARCH_READONLY_COPY}
        </p>
      )}
    </section>
  );
}

interface ResearchRowProps {
  researchItem: CarouselResearchReadResponse;
  researchIndex: number;
  isFirst: boolean;
  isLast: boolean;
  canWrite: boolean;
  isWorking: boolean;
  onMove: (direction: -1 | 1) => void;
  onRemove: () => void;
}

function ResearchRow({
  researchItem,
  researchIndex,
  isFirst,
  isLast,
  canWrite,
  isWorking,
  onMove,
  onRemove,
}: ResearchRowProps): ReactElement {

  const displayPosition: number = researchIndex + 1;

  return (
    <li id={`carousel-research-item-${researchItem.id}`} className="carousel-research-item">
      <div className="carousel-research-heading">
        <span className="carousel-research-index">{displayPosition}</span>
        <p className="carousel-research-title">{researchItem.title}</p>
      </div>
      {canWrite ? (
        <div className="button-row">
          <button
            id={`carousel-research-up-${researchItem.id}`}
            type="button"
            aria-label={`Move ${researchItem.title} up`}
            disabled={isWorking || isFirst}
            onClick={(): void => {
              onMove(-1);
            }}
          >
            Move up
          </button>
          <button
            id={`carousel-research-down-${researchItem.id}`}
            type="button"
            aria-label={`Move ${researchItem.title} down`}
            disabled={isWorking || isLast}
            onClick={(): void => {
              onMove(1);
            }}
          >
            Move down
          </button>
          <button
            id={`carousel-research-remove-${researchItem.id}`}
            type="button"
            aria-label={`Remove ${researchItem.title}`}
            disabled={isWorking}
            onClick={onRemove}
          >
            Remove
          </button>
        </div>
      ) : null}
    </li>
  );
}
