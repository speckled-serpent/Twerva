import { useEffect, useRef, useState, type FormEvent, type ReactElement } from "react";

import {
  acceptSlideText,
  createCarouselSlide,
  deleteCarousel,
  fetchTextGenerationStatus,
  generateCarouselSlide,
  generateSlideText,
  patchCarouselStep,
  deleteCarouselSlide,
  fetchCarouselById,
  fetchSkeletonById,
  listCarousels,
  patchCarouselSlide,
  renameCarousel,
  slideImageDisplayUrl,
} from "../api/client";
import type {
  CarouselListItemResponse,
  CarouselReadResponse,
  TextGenerationStatusResponse,
  SkeletonElementReadResponse,
  SkeletonReadResponse,
  SlideElementTextWrite,
  SlideImageReadResponse,
  SlideReadResponse,
  SlideWriteRequest,
} from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import { CarouselBasicStep } from "./CarouselBasicStep";
import { CarouselContentStep } from "./CarouselContentStep";
import { SkeletonAutosaveStatus } from "./SkeletonAutosaveStatus";
import type { AlbumEditorActions } from "./AlbumImagesEditor";
import { CarouselGeneration, CarouselStepBar } from "./CarouselStepBar";
import {
  carouselLabelFingerprint,
  carouselLabelReadiness,
  type CarouselLabelDraft,
} from "./carouselLabel";
import {
  CAROUSEL_STEP_BASIC,
  CAROUSEL_STEP_CONTENT,
  CAROUSEL_STEP_SLIDES,
  carouselStepByIndex,
  displayedEditorStep,
  generationLabel,
  openStepSentence,
  shellEditorStep,
  type CarouselStepDefinition,
} from "./carouselSteps";
import {
  SKELETON_AUTOSAVE_DELAY_MS,
  formatSkeletonAutosaveError,
  leaveAfterAutosave,
} from "./skeletonAutosave";
import { useSkeletonAutosave } from "./useSkeletonAutosave";
import { useCanWriteOps } from "../session/OpsSessionContext";
import { SlideAlbumImagePicker } from "./SlideAlbumImagePicker";
import {
  imageChoiceWriteRequest,
  savedSlideAlbumImageId,
} from "./slideAlbumImage";
import {
  NEW_PICTURE_SLIDE_AUTOSAVE_HINT,
  NEW_SLIDE_AUTOSAVE_HINT,
  SLIDE_AUTOSAVE_HINT,
  slideAutosaveWriteRequest,
  slideEditorFingerprint,
  slideEditorReadiness,
  slideImageChoiceWriteRequest,
  type SlideFieldDraft,
} from "./slideEditorAutosave";
import { SlideLivePreview } from "./SlideLivePreview";
import {
  labelForTextElement,
  orderedTextElements,
  textDraftsForSkeleton,
  skeletonRequiresImage,
} from "./slideSkeletonShape";

export interface CarouselsOpenRequest {
  sourceId: string;
  statusMessage: string;
}

export interface CarouselsPageProps {
  openRequest: CarouselsOpenRequest | null;
  onCreateCarousel: () => void;
}

/**
 * Carousels: one list of skeleton-bound carousels, and a slide editor that follows the skeleton.
 *
 * @param props - Optional open request from Create Carousel
 * @returns The Carousels page
 */
export function CarouselsPage({
  openRequest,
  onCreateCarousel,
}: CarouselsPageProps): ReactElement {

  const [listedCarousels, setListedCarousels] = useState<CarouselListItemResponse[]>([]);
  const [openedCarouselId, setOpenedCarouselId] = useState<string | null>(
    openRequest?.sourceId ?? null,
  );
  const [openedSlideId, setOpenedSlideId] = useState<string | null>(null);
  const [isCreatingSlide, setIsCreatingSlide] = useState<boolean>(false);
  const [selectedCarousel, setSelectedCarousel] = useState<CarouselReadResponse | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [statusMessage, setStatusMessage] = useState<string>(openRequest?.statusMessage ?? "");
  const [reloadToken, setReloadToken] = useState<number>(0);
  const [isSavingStep, setIsSavingStep] = useState<boolean>(false);
  const [stepError, setStepError] = useState<unknown>(null);
  const [viewedStep, setViewedStep] = useState<number | null>(null);
  const canWriteOps: boolean = useCanWriteOps();
  const [heldSlide, setHeldSlide] = useState<SlideReadResponse | null>(null);
  const [textGeneration, setTextGeneration] = useState<TextGenerationStatusResponse>({
    available: false,
    detail: "",
  });

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadCarousels = async (): Promise<void> => {

      try {
        const loadedCarousels: CarouselListItemResponse[] = await listCarousels();

        if (isCancelled) {
          return;
        }

        setListedCarousels(loadedCarousels);
        setLoadError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setLoadError(caughtError);
      }
    };

    void loadCarousels();

    return (): void => {
      isCancelled = true;
    };
  }, [reloadToken]);

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadTextGeneration = async (): Promise<void> => {

      try {
        const loadedStatus: TextGenerationStatusResponse = await fetchTextGenerationStatus();

        if (isCancelled) {
          return;
        }

        setTextGeneration(loadedStatus);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setTextGeneration({
          available: false,
          detail: caughtError instanceof Error
            ? caughtError.message
            : "Generate is off until OPENAI_API_KEY is set.",
        });
      }
    };

    void loadTextGeneration();

    return (): void => {
      isCancelled = true;
    };
  }, []);

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    if (openedCarouselId === null) {
      setSelectedCarousel(null);

      return (): void => {
        isCancelled = true;
      };
    }

    const loadCarousel = async (): Promise<void> => {

      try {
        const loadedCarousel: CarouselReadResponse = await fetchCarouselById(openedCarouselId);

        if (isCancelled) {
          return;
        }

        setSelectedCarousel(loadedCarousel);
        setLoadError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setSelectedCarousel(null);
        setLoadError(caughtError);
      }
    };

    void loadCarousel();

    return (): void => {
      isCancelled = true;
    };
  }, [openedCarouselId, reloadToken]);

  useEffect((): void => {
    if (openRequest === null) {
      return;
    }

    setOpenedCarouselId(openRequest.sourceId);
    setOpenedSlideId(null);
    setIsCreatingSlide(false);
    setHeldSlide(null);
    setViewedStep(null);
    setStatusMessage(openRequest.statusMessage);
  }, [openRequest]);

  useEffect((): void => {
    setViewedStep(null);
  }, [openedCarouselId]);

  const requestReload = (): void => {
    setReloadToken((currentToken: number): number => currentToken + 1);
  };

  const handleOpenStep = async (editorStep: number): Promise<void> => {

    if (openedCarouselId === null) {
      return;
    }

    if (!canWriteOps) {
      setViewedStep(editorStep);
      setStepError(null);

      if (editorStep !== CAROUSEL_STEP_SLIDES) {
        setOpenedSlideId(null);
        setIsCreatingSlide(false);
        setHeldSlide(null);
      }

      return;
    }

    const previousStep: number | null = selectedCarousel?.editor_step ?? null;
    setViewedStep(null);

    setIsSavingStep(true);
    setStepError(null);

    try {
      const updatedCarousel: CarouselReadResponse = await patchCarouselStep(openedCarouselId, {
        editor_step: editorStep,
      });
      const openedStep: CarouselStepDefinition | null = carouselStepByIndex(editorStep);
      setSelectedCarousel(updatedCarousel);

      if (editorStep !== CAROUSEL_STEP_SLIDES) {
        setOpenedSlideId(null);
        setIsCreatingSlide(false);
        setHeldSlide(null);
      }

      if (previousStep !== editorStep && openedStep !== null) {
        setStatusMessage(`Opened ${openedStep.label}.`);
      }

      requestReload();
    } catch (caughtError: unknown) {
      setStepError(caughtError);
    } finally {
      setIsSavingStep(false);
    }
  };

  const storedEditorStep: number = selectedCarousel?.editor_step ?? CAROUSEL_STEP_SLIDES;
  const requestedStep: number = displayedEditorStep(
    storedEditorStep,
    viewedStep,
    canWriteOps,
  );
  const displayStep: number = selectedCarousel === null
    ? requestedStep
    : shellEditorStep(requestedStep, selectedCarousel.steps);
  const slidesAreOpen: boolean = selectedCarousel === null
    || shellEditorStep(CAROUSEL_STEP_SLIDES, selectedCarousel.steps) === CAROUSEL_STEP_SLIDES;

  if (
    selectedCarousel !== null
    && !slidesAreOpen
    && (openedSlideId !== null || isCreatingSlide)
  ) {
    setOpenedSlideId(null);
    setIsCreatingSlide(false);
    setHeldSlide(null);
  }

  if (openedCarouselId !== null && slidesAreOpen && (openedSlideId !== null || isCreatingSlide)) {
    const loadedSlide: SlideReadResponse | null = findSlide(selectedCarousel, openedSlideId);
    const openedSlide: SlideReadResponse | null = isCreatingSlide
      ? null
      : heldSlide !== null && heldSlide.id === openedSlideId
        ? heldSlide
        : loadedSlide;

    return (
      <SlideEditorView
        carousel={selectedCarousel}
        slide={openedSlide}
        loadError={loadError}
        statusMessage={statusMessage}
        textGeneration={textGeneration}
        isSavingStep={isSavingStep}
        stepError={stepError}
        displayStep={displayStep}
        onOpenStep={(editorStep: number): void => {
          void handleOpenStep(editorStep);
        }}
        onBack={(): void => {
          setOpenedSlideId(null);
          setIsCreatingSlide(false);
          setHeldSlide(null);
          setStatusMessage("");
        }}
        onSaved={(savedSlide: SlideReadResponse, message: string): void => {

          if (message !== "") {
            setStatusMessage(message);
          }

          setHeldSlide(savedSlide);
          setIsCreatingSlide(false);
          setOpenedSlideId(savedSlide.id);
          requestReload();
        }}
        onSlideDeleted={(): void => {
          setOpenedSlideId(null);
          setIsCreatingSlide(false);
          setHeldSlide(null);
          setStatusMessage("Deleted the slide.");
          requestReload();
        }}
      />
    );
  }

  if (openedCarouselId !== null) {
    return (
      <AlbumView
        carousel={selectedCarousel}
        loadError={loadError}
        statusMessage={statusMessage}
        textGeneration={textGeneration}
        isSavingStep={isSavingStep}
        stepError={stepError}
        displayStep={displayStep}
        onOpenStep={(editorStep: number): void => {
          void handleOpenStep(editorStep);
        }}
        onBack={(): void => {
          setOpenedCarouselId(null);
          setStatusMessage("");
          setStepError(null);
        }}
        onSlideDrafted={(draftedSlide: SlideReadResponse): void => {
          setHeldSlide(draftedSlide);
          setOpenedSlideId(draftedSlide.id);
          setIsCreatingSlide(false);
          setStatusMessage("Drafted a slide. Accept the text to make it live.");
          requestReload();
        }}
        onOpenSlide={(slideId: string): void => {
          setHeldSlide(null);
          setOpenedSlideId(slideId);
          setIsCreatingSlide(false);
          setStatusMessage("");
        }}
        onCreateSlide={(): void => {
          setHeldSlide(null);
          setOpenedSlideId(null);
          setIsCreatingSlide(true);
          setStatusMessage("");
        }}
        onCarouselChanged={(message: string): void => {
          setStatusMessage(message);
          requestReload();
        }}
        onCarouselSaved={(savedCarousel: CarouselReadResponse): void => {
          setSelectedCarousel(savedCarousel);
          setStatusMessage("");
          setListedCarousels((
            currentCarousels: CarouselListItemResponse[],
          ): CarouselListItemResponse[] => (
            currentCarousels.map((
              listedCarousel: CarouselListItemResponse,
            ): CarouselListItemResponse => {

              if (listedCarousel.id !== savedCarousel.id) {
                return listedCarousel;
              }

              const renamedCarousel: CarouselListItemResponse = {
                ...listedCarousel,
                name: savedCarousel.name,
                album_id: savedCarousel.album_id,
                editor_step: savedCarousel.editor_step,
                updated_at: savedCarousel.updated_at,
              };

              return renamedCarousel;
            })
          ));
        }}
        onCarouselDeleted={(): void => {
          setOpenedCarouselId(null);
          setStatusMessage("Deleted the carousel.");
          requestReload();
        }}
      />
    );
  }

  return (
    <AlbumListView
      albums={listedCarousels}
      loadError={loadError}
      statusMessage={statusMessage}
      onCreateCarousel={onCreateCarousel}
      onOpenCarousel={(sourceId: string): void => {
        setOpenedCarouselId(sourceId);
        setStatusMessage("");
        setStepError(null);
      }}
      onAlbumDeleted={(albumName: string): void => {
        setStatusMessage(`Deleted carousel ${albumName}.`);
        requestReload();
      }}
    />
  );
}

interface AlbumListViewProps {
  albums: CarouselListItemResponse[];
  loadError: unknown;
  statusMessage: string;
  onCreateCarousel: () => void;
  onOpenCarousel: (sourceId: string) => void;
  onAlbumDeleted: (albumName: string) => void;
}

function AlbumListView({
  albums,
  loadError,
  statusMessage,
  onCreateCarousel,
  onOpenCarousel,
  onAlbumDeleted,
}: AlbumListViewProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [pendingDelete, setPendingDelete] = useState<CarouselListItemResponse | null>(null);

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>Carousels</h1>
          <p className="lede">
            Each carousel has a skeleton. Open one to continue from its saved step.
          </p>
        </div>
        <div className="page-header-actions">
          <button type="button" className="primary" onClick={onCreateCarousel}>
            Create Carousel
          </button>
        </div>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}
      {loadError !== null ? null : albums.length === 0 ? (
        <p className="empty-hint">No carousels yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Generation</th>
              <th>Slides</th>
              <th>Open</th>
              <th>Delete</th>
            </tr>
          </thead>
          <tbody>
            {albums.map((album: CarouselListItemResponse): ReactElement => (
              <tr key={album.id}>
                <td>{album.name}</td>
                <td>{generationLabel(album.generation_number)}</td>
                <td>{album.slide_count}</td>
                <td>
                  <button
                    type="button"
                    onClick={(): void => {
                      onOpenCarousel(album.id);
                    }}
                  >
                    Open
                  </button>
                </td>
                <td>
                  {canWrite ? (
                    <button
                      type="button"
                      className="danger"
                      onClick={(): void => {
                        setPendingDelete(album);
                      }}
                    >
                      Delete
                    </button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {pendingDelete === null ? null : (
        <DeleteConfirmDialog
          headingId="delete-album-heading"
          title={`Delete ${pendingDelete.name}?`}
          body="This removes the carousel and its slides. Delete is blocked while a skeleton or an artifact still stores one of its images, and the carousel stays."
          confirmLabel="Delete carousel"
          onCancel={(): void => {
            setPendingDelete(null);
          }}
          onConfirm={async (): Promise<void> => {
            await deleteCarousel(pendingDelete.id);
            const deletedName: string = pendingDelete.name;
            setPendingDelete(null);
            onAlbumDeleted(deletedName);
          }}
        />
      )}
    </section>
  );
}

interface AlbumViewProps {
  carousel: CarouselReadResponse | null;
  loadError: unknown;
  statusMessage: string;
  textGeneration: TextGenerationStatusResponse;
  isSavingStep: boolean;
  stepError: unknown;
  displayStep: number;
  onOpenStep: (editorStep: number) => void;
  onBack: () => void;
  onOpenSlide: (slideId: string) => void;
  onCreateSlide: () => void;
  onSlideDrafted: (draftedSlide: SlideReadResponse) => void;
  onCarouselChanged: (message: string) => void;
  onCarouselSaved: (savedCarousel: CarouselReadResponse) => void;
  onCarouselDeleted: () => void;
}

/**
 * Heading while the label is being edited. A blank draft keeps the stored name.
 *
 * @param carousel - The open carousel, or null while it loads
 * @param labelDraft - The Basic label, or null before the first load
 * @returns The name to show
 */
function carouselHeadingName(
  carousel: CarouselReadResponse | null,
  labelDraft: CarouselLabelDraft | null,
): string {

  if (labelDraft !== null && labelDraft.name.trim() !== "") {
    return labelDraft.name.trim();
  }

  if (carousel !== null) {
    return carousel.name;
  }

  return "Carousel";
}

function AlbumView({
  carousel,
  loadError,
  statusMessage,
  textGeneration,
  isSavingStep,
  stepError,
  displayStep,
  onOpenStep,
  onBack,
  onOpenSlide,
  onCreateSlide,
  onSlideDrafted,
  onCarouselChanged,
  onCarouselSaved,
  onCarouselDeleted,
}: AlbumViewProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const carouselId: string | null = carousel?.id ?? null;
  const [trackedCarouselId, setTrackedCarouselId] = useState<string | null>(carouselId);
  const [labelDraft, setLabelDraft] = useState<CarouselLabelDraft | null>(
    carousel === null ? null : { name: carousel.name },
  );
  const [saveError, setSaveError] = useState<unknown>(null);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [pendingDelete, setPendingDelete] = useState<boolean>(false);
  const [pendingSlideDelete, setPendingSlideDelete] = useState<SlideReadResponse | null>(null);
  const albumEditorActionsRef: { current: AlbumEditorActions | null } = useRef(null);
  const showsBasic: boolean = carousel !== null && displayStep === CAROUSEL_STEP_BASIC;
  const showsContent: boolean = carousel !== null && displayStep === CAROUSEL_STEP_CONTENT;
  const showsSlides: boolean = carousel !== null && displayStep === CAROUSEL_STEP_SLIDES;

  if (carouselId !== trackedCarouselId) {
    const nextDraft: CarouselLabelDraft | null = carousel === null
      ? null
      : { name: carousel.name };
    setTrackedCarouselId(carouselId);
    setLabelDraft(nextDraft);
  }

  const autosave = useSkeletonAutosave<CarouselLabelDraft>({
    delayMs: SKELETON_AUTOSAVE_DELAY_MS,
    readiness: carouselLabelReadiness,
    fingerprint: carouselLabelFingerprint,
    save: async (value: CarouselLabelDraft): Promise<void> => {

      if (carousel === null) {
        return;
      }

      const savedCarousel: CarouselReadResponse = await renameCarousel(carousel.id, {
        name: value.name.trim(),
      });
      onCarouselSaved(savedCarousel);
    },
    formatError: formatSkeletonAutosaveError,
  });

  useEffect((): void => {
    if (labelDraft === null || carousel === null) {
      return;
    }

    if (labelDraft.name.trim() !== carousel.name) {
      return;
    }

    autosave.noteSaved(labelDraft);
  }, [carousel, carouselId, labelDraft, autosave.noteSaved]);

  useEffect((): void => {
    if (!canWrite || labelDraft === null) {
      return;
    }

    autosave.schedule(labelDraft);
  }, [autosave.schedule, canWrite, labelDraft]);

  let pageLede: string = "Slides in this carousel.";

  if (carousel !== null) {
    pageLede = openStepSentence(displayStep);

    if (showsSlides) {
      pageLede = `${pageLede} A card shows the first image, or the text when there is none. ${carousel.live_slide_count} live.`;
    }
  }

  const headingName: string = carouselHeadingName(carousel, labelDraft);

  const flushOpenEdits = async (): Promise<void> => {
    await autosave.flush();
    const albumActions: AlbumEditorActions | null = albumEditorActionsRef.current;

    if (albumActions !== null) {
      await albumActions.flush();
    }
  };

  const openEditsAreDirty = (): boolean => {

    if (autosave.isDirty()) {
      return true;
    }

    const albumActions: AlbumEditorActions | null = albumEditorActionsRef.current;

    if (albumActions !== null && albumActions.isDirty()) {
      return true;
    }

    return false;
  };

  const handleBack = (): void => {
    void leaveAfterAutosave(flushOpenEdits, openEditsAreDirty, onBack);
  };

  // Leaving Basic flushes the label. Leaving Content flushes album image edits.
  const handleStep = (editorStep: number): void => {
    void leaveAfterAutosave(
      flushOpenEdits,
      openEditsAreDirty,
      (): void => {
        onOpenStep(editorStep);
      },
    );
  };

  const handleGenerateSlide = async (): Promise<void> => {

    if (!canWrite || carousel === null || !textGeneration.available) {
      return;
    }

    setIsGenerating(true);
    setSaveError(null);

    try {
      const draftedSlide: SlideReadResponse = await generateCarouselSlide(carousel.id);
      onSlideDrafted(draftedSlide);
    } catch (caughtError: unknown) {
      setSaveError(caughtError);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <section>
      <div className="page-header-row">
        <div>
          <div className="carousel-heading">
            <h1>{headingName}</h1>
            {carousel === null ? null : (
              <CarouselGeneration generationNumber={carousel.generation_number} />
            )}
          </div>
          <p className="lede">
            {pageLede}
          </p>
        </div>
        <button type="button" onClick={handleBack}>
          Back to carousels
        </button>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      <ErrorBanner error={saveError} />
      <ErrorBanner error={stepError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}
      {carousel === null ? (
        <p>Loading carousel…</p>
      ) : (
        <>
          <CarouselStepBar
            editorStep={displayStep}
            steps={carousel.steps}
            canWrite={canWrite}
            isSavingStep={isSavingStep}
            onOpenStep={handleStep}
          />
          {showsBasic && labelDraft !== null ? (
            <CarouselBasicStep
              carousel={carousel}
              canWrite={canWrite}
              labelDraft={labelDraft}
              autosaveState={autosave.state}
              onLabelChange={(name: string): void => {
                setLabelDraft({ name });
              }}
              onRetry={(): void => {
                void autosave.retry();
              }}
            />
          ) : null}
          {showsContent ? (
            <CarouselContentStep
              carousel={carousel}
              canWrite={canWrite}
              onCarouselSaved={onCarouselSaved}
              onAlbumEditorActions={(actions: AlbumEditorActions | null): void => {
                albumEditorActionsRef.current = actions;
              }}
            />
          ) : null}
          {showsSlides ? (
            <>
              {canWrite ? (
                <div className="button-row">
                  <button
                    type="button"
                    className="danger"
                    onClick={(): void => {
                      setPendingDelete(true);
                    }}
                  >
                    Delete carousel
                  </button>
                  <button id="add-slide" type="button" onClick={onCreateSlide}>
                    Add slide
                  </button>
                  <button
                    id="generate-slide"
                    type="button"
                    disabled={!textGeneration.available || isGenerating}
                    onClick={(): void => {
                      void handleGenerateSlide();
                    }}
                  >
                    {isGenerating ? "Generating…" : "Generate slide"}
                  </button>
                </div>
              ) : null}
              <p className="field-hint">
                Generate slide writes a draft.
                A draft stays off the live slide until you accept it.
              </p>
              {textGeneration.available ? null : (
                <p className="field-hint" id="generate-unavailable">
                  {textGeneration.detail}
                </p>
              )}
              {carousel.slides.length === 0 ? (
                <p>No slides yet.</p>
              ) : (
                <ul className="slide-grid">
                  {carousel.slides.map((slide: SlideReadResponse): ReactElement => (
                    <li key={slide.id}>
                      <button
                        type="button"
                        className="slide-card"
                        onClick={(): void => {
                          onOpenSlide(slide.id);
                        }}
                      >
                        <SlideCardBody sourceId={carousel.id} slide={slide} />
                      </button>
                      {canWrite ? (
                        <button
                          type="button"
                          className="danger"
                          onClick={(): void => {
                            setPendingSlideDelete(slide);
                          }}
                        >
                          Delete slide
                        </button>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </>
          ) : null}
        </>
      )}
      {pendingDelete && carousel !== null ? (
        <DeleteConfirmDialog
          headingId="delete-open-album-heading"
          title={`Delete ${carousel.name}?`}
          body="This removes the carousel and its slides. Delete is blocked while a skeleton or an artifact still stores one of its images, and the carousel stays."
          confirmLabel="Delete carousel"
          onCancel={(): void => {
            setPendingDelete(false);
          }}
          onConfirm={async (): Promise<void> => {
            await deleteCarousel(carousel.id);
            setPendingDelete(false);
            onCarouselDeleted();
          }}
        />
      ) : null}
      {pendingSlideDelete !== null && carousel !== null ? (
        <DeleteConfirmDialog
          headingId="delete-slide-heading"
          title="Delete this slide?"
          body="Delete is blocked while a skeleton or an artifact still stores one of its images, and the slide stays."
          confirmLabel="Delete slide"
          onCancel={(): void => {
            setPendingSlideDelete(null);
          }}
          onConfirm={async (): Promise<void> => {
            await deleteCarouselSlide(carousel.id, pendingSlideDelete.id);
            setPendingSlideDelete(null);
            onCarouselChanged("Deleted the slide.");
          }}
        />
      ) : null}
    </section>
  );
}

interface SlideCardBodyProps {
  sourceId: string;
  slide: SlideReadResponse;
}

function SlideCardBody({ sourceId, slide }: SlideCardBodyProps): ReactElement {

  const firstImage: SlideImageReadResponse | undefined = slide.images[0];
  const excerpt: string = slideExcerpt(slide);

  return (
    <>
      <p className="slide-card-excerpt">
        {slide.name}
        {slide.text_status === "draft" ? <span className="draft-badge">Draft</span> : null}
      </p>
      {firstImage === undefined ? (
        <p className="slide-card-excerpt">{excerpt}</p>
      ) : (
        <img
          src={slideImageDisplayUrl(sourceId, slide.id, firstImage)}
          alt={firstImage.alt_text ?? excerpt}
        />
      )}
      {firstImage === undefined ? null : <p className="slide-card-excerpt">{excerpt}</p>}
    </>
  );
}

function labelForExcludedSlide(
  candidate: SlideReadResponse,
  otherSlides: SlideReadResponse[],
): string {
  const sameNameCount: number = otherSlides.filter(
    (otherSlide: SlideReadResponse): boolean => otherSlide.name === candidate.name,
  ).length;

  if (sameNameCount > 1) {
    const shortId: string = candidate.id.slice(0, 8);

    return `${candidate.name} (${shortId})`;
  }

  return candidate.name;
}

interface SlideEditorViewProps {
  carousel: CarouselReadResponse | null;
  slide: SlideReadResponse | null;
  loadError: unknown;
  statusMessage: string;
  textGeneration: TextGenerationStatusResponse;
  isSavingStep: boolean;
  stepError: unknown;
  displayStep: number;
  onOpenStep: (editorStep: number) => void;
  onBack: () => void;
  onSaved: (savedSlide: SlideReadResponse, message: string) => void;
  onSlideDeleted: () => void;
}

function SlideEditorView({
  carousel,
  slide,
  loadError,
  statusMessage,
  textGeneration,
  isSavingStep,
  stepError,
  displayStep,
  onOpenStep,
  onBack,
  onSaved,
  onSlideDeleted,
}: SlideEditorViewProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [skeleton, setSkeleton] = useState<SkeletonReadResponse | null>(null);
  const [skeletonError, setSkeletonError] = useState<unknown>(null);
  const [skeletonReady, setSkeletonReady] = useState<boolean>(false);
  const [textSeedKey, setTextSeedKey] = useState<string | null>(null);
  const [slideName, setSlideName] = useState<string>(slide?.name ?? "");
  const [excludedIds, setExcludedIds] = useState<string[]>(slide?.excluded_slide_ids ?? []);
  const [textValues, setTextValues] = useState<Record<string, string>>({});
  const [saveError, setSaveError] = useState<unknown>(null);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [isAccepting, setIsAccepting] = useState<boolean>(false);
  const [pendingDelete, setPendingDelete] = useState<boolean>(false);
  const [chosenAlbumImageId, setChosenAlbumImageId] = useState<string | null>(null);
  const [isChoosingImage, setIsChoosingImage] = useState<boolean>(false);
  const imageChoiceRef: { current: boolean } = useRef<boolean>(false);
  const fieldDraftRef: { current: SlideFieldDraft | null } = useRef<SlideFieldDraft | null>(null);
  const createdSlideIdRef: { current: string | null } = useRef<string | null>(null);
  const lastSavedSlideRef: { current: SlideReadResponse | null } = useRef<SlideReadResponse | null>(
    slide,
  );
  const needsImage: boolean = skeleton !== null && skeletonRequiresImage(skeleton);
  const savedAlbumImageId: string | null = savedSlideAlbumImageId(slide);
  const selectedAlbumImageId: string | null = slide === null
    ? chosenAlbumImageId
    : savedAlbumImageId;
  const otherSlides: SlideReadResponse[] = (carousel?.slides ?? []).filter(
    (candidate: SlideReadResponse): boolean => candidate.id !== slide?.id,
  );
  const textElements: SkeletonElementReadResponse[] = skeleton === null
    ? []
    : orderedTextElements(skeleton.elements);
  const slideIdentity: string = slide?.id ?? "new";
  const seedKey: string = skeleton === null ? "" : `${slideIdentity}:${skeleton.id}`;

  // Seed name and text when the skeleton or the open slide arrives.
  // The row created from this form keeps what the operator already typed.
  if (skeleton !== null && textSeedKey !== seedKey) {
    const createdThisSlide: boolean = slide !== null && slide.id === createdSlideIdRef.current;

    if (createdThisSlide) {
      setTextSeedKey(seedKey);
    } else {
      setTextSeedKey(seedKey);
      setSlideName(slide?.name ?? "");
      setExcludedIds(slide?.excluded_slide_ids ?? []);
      setTextValues(textDraftsForSkeleton(skeleton, slide));
      setChosenAlbumImageId(null);
      lastSavedSlideRef.current = slide;
    }
  }

  const fieldsSeeded: boolean = skeleton !== null && textSeedKey === seedKey;
  const textWrites: SlideElementTextWrite[] = textElements.map(
    (element: SkeletonElementReadResponse): SlideElementTextWrite => ({
      skeleton_element_id: element.id,
      value: textValues[element.id] ?? "",
    }),
  );
  const otherIds: Set<string> = new Set(
    otherSlides.map((candidate: SlideReadResponse): string => candidate.id),
  );
  const storedExcludedIds: string[] = excludedIds.filter(
    (excludedId: string): boolean => otherIds.has(excludedId),
  );
  const fieldDraft: SlideFieldDraft = {
    slideId: slide?.id ?? null,
    needsImage,
    skeletonReady: fieldsSeeded,
    name: slideName,
    texts: textWrites,
    excludedSlideIds: storedExcludedIds,
    albumImageId: selectedAlbumImageId,
  };
  fieldDraftRef.current = fieldDraft;
  const draftFingerprint: string = slideEditorFingerprint(fieldDraft);

  useEffect((): (() => void) => {
    if (carousel === null) {
      return (): void => {
        return;
      };
    }

    let isCancelled: boolean = false;
    const skeletonId: string = carousel.skeleton_id;

    const loadSkeleton = async (): Promise<void> => {
      setSkeletonReady(false);

      try {
        const loadedSkeleton: SkeletonReadResponse = await fetchSkeletonById(skeletonId);

        if (isCancelled) {
          return;
        }

        setSkeleton(loadedSkeleton);
        setSkeletonError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setSkeleton(null);
        setSkeletonError(caughtError);
      } finally {
        if (!isCancelled) {
          setSkeletonReady(true);
        }
      }
    };

    void loadSkeleton();

    return (): void => {
      isCancelled = true;
    };
  }, [carousel?.id, carousel?.skeleton_id]);

  const serverTexts: Record<string, string> = skeleton === null
    ? {}
    : textDraftsForSkeleton(skeleton, slide);
  const serverDraft: SlideFieldDraft | null = slide === null || skeleton === null
    ? null
    : {
      slideId: slide.id,
      needsImage,
      skeletonReady: true,
      name: slide.name,
      texts: textElements.map(
        (element: SkeletonElementReadResponse): SlideElementTextWrite => ({
          skeleton_element_id: element.id,
          value: serverTexts[element.id] ?? "",
        }),
      ),
      excludedSlideIds: slide.excluded_slide_ids.filter(
        (excludedId: string): boolean => otherIds.has(excludedId),
      ),
      albumImageId: savedAlbumImageId,
    };
  const serverFingerprint: string = serverDraft === null
    ? ""
    : slideEditorFingerprint(serverDraft);
  const autosave = useSkeletonAutosave<SlideFieldDraft>({
    delayMs: SKELETON_AUTOSAVE_DELAY_MS,
    readiness: slideEditorReadiness,
    fingerprint: slideEditorFingerprint,
    save: async (draft: SlideFieldDraft): Promise<void> => {

      if (carousel === null) {
        return;
      }

      const persistedSlideId: string | null = draft.slideId ?? createdSlideIdRef.current;
      let savedSlide: SlideReadResponse;

      if (persistedSlideId === null) {
        savedSlide = await createCarouselSlide(
          carousel.id,
          slideAutosaveWriteRequest(draft),
        );
        createdSlideIdRef.current = savedSlide.id;
        lastSavedSlideRef.current = savedSlide;
        onSaved(savedSlide, "Created the slide.");

        return;
      }

      const persistedDraft: SlideFieldDraft = {
        ...draft,
        slideId: persistedSlideId,
      };
      savedSlide = await patchCarouselSlide(
        carousel.id,
        persistedSlideId,
        slideAutosaveWriteRequest(persistedDraft),
      );
      lastSavedSlideRef.current = savedSlide;
      onSaved(savedSlide, "");
    },
    formatError: formatSkeletonAutosaveError,
  });

  useEffect((): void => {
    const currentDraft: SlideFieldDraft | null = fieldDraftRef.current;

    if (currentDraft === null || !currentDraft.skeletonReady || serverFingerprint === "") {
      return;
    }

    if (slideEditorFingerprint(currentDraft) !== serverFingerprint) {
      return;
    }

    autosave.noteSaved(currentDraft);
  }, [
    autosave.noteSaved,
    draftFingerprint,
    fieldDraft.skeletonReady,
    serverFingerprint,
  ]);

  useEffect((): void => {
    const currentDraft: SlideFieldDraft | null = fieldDraftRef.current;

    if (!canWrite || currentDraft === null || !currentDraft.skeletonReady) {
      return;
    }

    autosave.schedule(currentDraft);
  }, [
    autosave.schedule,
    canWrite,
    draftFingerprint,
    fieldDraft.albumImageId,
    fieldDraft.skeletonReady,
    fieldDraft.slideId,
  ]);

  useEffect((): void => {
    const imagesSection: HTMLElement | null = document.getElementById("slide-images");

    if (imagesSection !== null) {
      imagesSection.scrollIntoView({ block: "start" });
    }
  }, [slide?.id]);

  const handleChooseAlbumImage = async (albumImageId: string): Promise<void> => {

    if (
      !canWrite
      || carousel === null
      || skeleton === null
      || imageChoiceRef.current
    ) {
      return;
    }

    if (slide === null) {
      setChosenAlbumImageId(albumImageId);
      setSaveError(null);

      return;
    }

    if (albumImageId === savedAlbumImageId) {
      return;
    }

    imageChoiceRef.current = true;
    setIsChoosingImage(true);
    setSaveError(null);

    try {
      await autosave.flush();
      const flushedDraft: SlideFieldDraft | null = fieldDraftRef.current;
      const storedSlide: SlideReadResponse = lastSavedSlideRef.current ?? slide;
      const slideWriteRequest: SlideWriteRequest = flushedDraft !== null
        && slideEditorReadiness(flushedDraft).kind === "ready"
        ? slideImageChoiceWriteRequest(flushedDraft, albumImageId)
        : imageChoiceWriteRequest(storedSlide, skeleton, albumImageId);
      const savedSlide: SlideReadResponse = await patchCarouselSlide(
        carousel.id,
        slide.id,
        slideWriteRequest,
      );
      onSaved(savedSlide, "Chose the image.");
    } catch (caughtError: unknown) {
      setSaveError(caughtError);
    } finally {
      imageChoiceRef.current = false;
      setIsChoosingImage(false);
    }
  };

  const handleGenerateText = async (): Promise<void> => {
    if (!canWrite || carousel === null || slide === null || skeleton === null || !textGeneration.available) {
      return;
    }

    setIsGenerating(true);
    setSaveError(null);

    try {
      await autosave.flush();
      const draftedSlide: SlideReadResponse = await generateSlideText(carousel.id, slide.id);
      lastSavedSlideRef.current = draftedSlide;
      setSlideName(draftedSlide.name);
      setExcludedIds(draftedSlide.excluded_slide_ids);
      setTextValues(textDraftsForSkeleton(skeleton, draftedSlide));
      onSaved(draftedSlide, "Drafted text. Accept it to make this slide live.");
    } catch (caughtError: unknown) {
      setSaveError(caughtError);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleAcceptText = async (): Promise<void> => {

    if (
      !canWrite
      || carousel === null
      || slide === null
      || skeleton === null
      || slide.text_status !== "draft"
    ) {
      return;
    }

    setIsAccepting(true);
    setSaveError(null);

    try {
      await autosave.flush();
      const acceptedSlide: SlideReadResponse = await acceptSlideText(carousel.id, slide.id, {
        texts: fieldDraftRef.current?.texts ?? textWrites,
      });
      lastSavedSlideRef.current = acceptedSlide;
      setSlideName(acceptedSlide.name);
      setExcludedIds(acceptedSlide.excluded_slide_ids);
      setTextValues(textDraftsForSkeleton(skeleton, acceptedSlide));
      onSaved(acceptedSlide, "Accepted the text. This slide is live.");
    } catch (caughtError: unknown) {
      setSaveError(caughtError);
    } finally {
      setIsAccepting(false);
    }
  };

  const handleBack = (): void => {
    void leaveAfterAutosave(autosave.flush, autosave.isDirty, onBack);
  };

  const handleStep = (editorStep: number): void => {
    void leaveAfterAutosave(
      autosave.flush,
      autosave.isDirty,
      (): void => {
        onOpenStep(editorStep);
      },
    );
  };

  const autosaveHint: string = slide !== null
    ? SLIDE_AUTOSAVE_HINT
    : needsImage
      ? NEW_PICTURE_SLIDE_AUTOSAVE_HINT
      : NEW_SLIDE_AUTOSAVE_HINT;
  const editorBusy: boolean = isGenerating || isAccepting || isChoosingImage;

  const pageTitle: string = slide === null ? "New slide" : "Slide";
  let pageLede: string = (
    "The fields follow this carousel's skeleton. Preview shows the slide on that skeleton."
  );

  if (carousel !== null) {
    pageLede = `${openStepSentence(displayStep)} ${pageLede}`;
  }

  return (
    <section>
      <div className="page-header-row">
        <div>
          <div className="carousel-heading">
            <h1>{pageTitle}</h1>
            {carousel === null ? null : (
              <CarouselGeneration generationNumber={carousel.generation_number} />
            )}
          </div>
          <p className="lede">
            {carousel === null ? "Carousel" : carousel.name}
            . {pageLede}
          </p>
        </div>
        <button type="button" onClick={handleBack}>
          Back to slides
        </button>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      <ErrorBanner error={skeletonError} />
      <ErrorBanner error={saveError} />
      <ErrorBanner error={stepError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}
      {carousel === null ? (
        <p>Loading carousel…</p>
      ) : (
        <>
          <CarouselStepBar
            editorStep={displayStep}
            steps={carousel.steps}
            canWrite={canWrite}
            isSavingStep={isSavingStep}
            onOpenStep={handleStep}
          />
          {slide === null && !canWrite ? (
            <p>This slide is not available.</p>
          ) : !skeletonReady ? (
            <p>Loading skeleton…</p>
          ) : skeleton === null ? (
            <p>This skeleton is not available.</p>
          ) : (
        <div className="skeleton-editor-layout">
          <div className="skeleton-editor-main">
            {needsImage ? (
              <SlideAlbumImagePicker
                albumId={carousel.album_id}
                selectedImageId={selectedAlbumImageId}
                canWrite={canWrite}
                isChoosing={isChoosingImage}
                isLocked={autosave.state.phase === "saving" || isGenerating || isAccepting}
                onChoose={(albumImageId: string): void => {
                  void handleChooseAlbumImage(albumImageId);
                }}
                onOpenContent={(): void => {
                  handleStep(CAROUSEL_STEP_CONTENT);
                }}
              />
            ) : null}
            <form
              className="stack-form"
              onSubmit={(submitEvent: FormEvent<HTMLFormElement>): void => {
                submitEvent.preventDefault();
                void autosave.flush();
              }}
            >
              {slide?.text_status === "draft" ? (
                <p className="status-banner" id="slide-draft-banner">
                  This text is a draft. It stays off the live slide until you accept it.
                </p>
              ) : null}
              <label>
                Name
                <input
                  id="slide-name"
                  value={slideName}
                  disabled={!canWrite}
                  onChange={(changeEvent): void => {
                    setSlideName(changeEvent.target.value);
                  }}
                />
              </label>
              <p className="field-hint">The id stays the same. The name is what you call this slide.</p>
              {canWrite ? (
                <p className="field-hint" id="slide-autosave-hint">{autosaveHint}</p>
              ) : null}
              {canWrite ? (
                <SkeletonAutosaveStatus
                  state={autosave.state}
                  onRetry={(): void => {
                    void autosave.retry();
                  }}
                />
              ) : null}
              {slide === null ? null : (
                <p className="field-hint">Id {slide.id}</p>
              )}
              {textElements.map((element: SkeletonElementReadResponse): ReactElement => (
                <label key={element.id}>
                  {labelForTextElement(element, textElements)}
                  <textarea
                    id={`slide-text-${element.id}`}
                    rows={3}
                    value={textValues[element.id] ?? ""}
                    disabled={!canWrite}
                    onChange={(changeEvent): void => {
                      setTextValues({
                        ...textValues,
                        [element.id]: changeEvent.target.value,
                      });
                    }}
                  />
                </label>
              ))}
              <fieldset className="form-fieldset" disabled={!canWrite}>
                <legend>Cannot be shown with</legend>
                <p className="field-hint">
                  The rule applies both ways. Marking it here also marks this slide on the other slide.
                </p>
                {otherSlides.length === 0 ? (
                  <p>No other slides in this carousel yet.</p>
                ) : (
                  <ul className="account-pick-list">
                    {otherSlides.map((otherSlide: SlideReadResponse): ReactElement => {
                      const isExcluded: boolean = excludedIds.includes(otherSlide.id);
                      const exclusionLabel: string = labelForExcludedSlide(otherSlide, otherSlides);

                      return (
                        <li key={otherSlide.id}>
                          <label className="checkbox-row">
                            <input
                              id={`slide-exclude-${otherSlide.id}`}
                              type="checkbox"
                              checked={isExcluded}
                              disabled={!canWrite}
                              onChange={(): void => {
                                if (isExcluded) {
                                  setExcludedIds(
                                    excludedIds.filter(
                                      (excludedId: string): boolean => excludedId !== otherSlide.id,
                                    ),
                                  );

                                  return;
                                }

                                setExcludedIds([...excludedIds, otherSlide.id]);
                              }}
                            />
                            <span>{exclusionLabel}</span>
                          </label>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </fieldset>
              {canWrite && slide !== null && !textGeneration.available ? (
                <p className="field-hint" id="generate-unavailable">
                  {textGeneration.detail}
                </p>
              ) : null}
              {canWrite && slide !== null ? (
                <div className="button-row">
                  <button
                    id="generate-slide-text"
                    type="button"
                    disabled={!textGeneration.available || editorBusy}
                    onClick={(): void => {
                      void handleGenerateText();
                    }}
                  >
                    {isGenerating ? "Generating…" : "Generate text"}
                  </button>
                  {slide.text_status === "draft" ? (
                    <button
                      id="accept-slide-text"
                      type="button"
                      disabled={editorBusy}
                      onClick={(): void => {
                        void handleAcceptText();
                      }}
                    >
                      {isAccepting ? "Accepting…" : "Accept text"}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="danger"
                    disabled={editorBusy}
                    onClick={(): void => {
                      setPendingDelete(true);
                    }}
                  >
                    Delete slide
                  </button>
                </div>
              ) : null}
            </form>
          </div>
          <SlideLivePreview
            sourceId={carousel.id}
            slideId={slide?.id ?? null}
            texts={textWrites}
            savedImageId={savedAlbumImageId}
          />
        </div>
          )}
        </>
      )}
      {pendingDelete && carousel !== null && slide !== null ? (
        <DeleteConfirmDialog
          headingId="delete-editor-slide-heading"
          title="Delete this slide?"
          body="Delete is blocked while a skeleton or an artifact still stores one of its images, and the slide stays."
          confirmLabel="Delete slide"
          onCancel={(): void => {
            setPendingDelete(false);
          }}
          onConfirm={async (): Promise<void> => {
            await autosave.abandon();
            await deleteCarouselSlide(carousel.id, slide.id);
            setPendingDelete(false);
            onSlideDeleted();
          }}
        />
      ) : null}
    </section>
  );
}

interface DeleteConfirmDialogProps {
  headingId: string;
  title: string;
  body: string;
  confirmLabel: string;
  onCancel: () => void;
  onConfirm: () => Promise<void>;
}

function DeleteConfirmDialog({
  headingId,
  title,
  body,
  confirmLabel,
  onCancel,
  onConfirm,
}: DeleteConfirmDialogProps): ReactElement {

  const [deleteError, setDeleteError] = useState<unknown>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  const handleConfirm = async (): Promise<void> => {
    setIsDeleting(true);
    setDeleteError(null);

    try {
      await onConfirm();
    } catch (caughtError: unknown) {
      setDeleteError(caughtError);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div
      className="confirm-backdrop"
      onClick={(): void => {
        if (!isDeleting) {
          onCancel();
        }
      }}
    >
      <div
        className="confirm-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={headingId}
        onClick={(clickEvent): void => {
          clickEvent.stopPropagation();
        }}
      >
        <h2 id={headingId}>{title}</h2>
        <p>{body}</p>
        <ErrorBanner error={deleteError} />
        <div className="button-row">
          <button
            type="button"
            className="danger"
            disabled={isDeleting}
            onClick={(): void => {
              void handleConfirm();
            }}
          >
            {isDeleting ? "Deleting…" : confirmLabel}
          </button>
          <button type="button" disabled={isDeleting} onClick={onCancel}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

function findSlide(
  carousel: CarouselReadResponse | null,
  slideId: string | null,
): SlideReadResponse | null {

  if (carousel === null || slideId === null) {
    return null;
  }

  const foundSlide: SlideReadResponse | undefined = carousel.slides.find(
    (slide: SlideReadResponse): boolean => slide.id === slideId,
  );

  return foundSlide ?? null;
}

function slideExcerpt(slide: SlideReadResponse): string {

  for (const elementText of slide.texts) {
    const trimmedValue: string = elementText.value.trim();

    if (trimmedValue !== "") {
      return trimmedValue;
    }
  }

  const firstImage: SlideImageReadResponse | undefined = slide.images[0];

  if (firstImage !== undefined) {
    return firstImage.relative_path;
  }

  return "Empty slide";
}
