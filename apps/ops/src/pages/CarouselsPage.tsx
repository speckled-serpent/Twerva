import { useEffect, useRef, useState, type FormEvent, type ReactElement } from "react";

import {
  acceptSlideText,
  createCarouselSlide,
  createSlideWithImages,
  deleteCarousel,
  fetchTextGenerationStatus,
  generateCarouselSlide,
  generateSlideText,
  patchCarouselStep,
  deleteCarouselSlide,
  deleteSlideImage,
  fetchCarouselById,
  fetchSkeletonById,
  listCarousels,
  patchCarouselSlide,
  patchSlideImageMetadata,
  renameCarousel,
  importSlideImage,
  slideImageDisplayUrl,
  uploadSlideImages,
} from "../api/client";
import type {
  CarouselListItemResponse,
  CarouselReadResponse,
  TextGenerationStatusResponse,
  SkeletonElementReadResponse,
  SkeletonReadResponse,
  SlideElementTextWrite,
  SlideImageCreatePayload,
  SlideImageLicense,
  SlideImageReadResponse,
  SlideReadResponse,
  SlideWriteRequest,
} from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import {
  NewSlideImages,
  releaseSlideImageDraft,
  type SlideImageDraft,
} from "./SlideImageDrafts";
import { firstSlideImageDraftError } from "./slideImageDraft";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import { CarouselBasicStep } from "./CarouselBasicStep";
import { CarouselGeneration, CarouselStepBar } from "./CarouselStepBar";
import {
  carouselLabelFingerprint,
  carouselLabelReadiness,
  type CarouselLabelDraft,
} from "./carouselLabel";
import {
  CAROUSEL_STEP_BASIC,
  CAROUSEL_STEP_SLIDES,
  carouselStepByIndex,
  generationLabel,
  openStepSentence,
  type CarouselStepDefinition,
} from "./carouselSteps";
import {
  SKELETON_AUTOSAVE_DELAY_MS,
  formatSkeletonAutosaveError,
  leaveAfterAutosave,
} from "./skeletonAutosave";
import { useSkeletonAutosave } from "./useSkeletonAutosave";
import { useCanWriteOps } from "../session/OpsSessionContext";
import { SlideLivePreview } from "./SlideLivePreview";
import {
  labelForTextElement,
  orderedTextElements,
  textDraftsForSkeleton,
  skeletonRequiresImage,
} from "./slideSkeletonShape";

const LICENSE_OPTIONS: SlideImageLicense[] = [
  "cc0",
  "public_domain",
  "owned",
  "licensed",
];

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
    setStatusMessage(openRequest.statusMessage);
  }, [openRequest]);

  const requestReload = (): void => {
    setReloadToken((currentToken: number): number => currentToken + 1);
  };

  const handleOpenStep = async (editorStep: number): Promise<void> => {

    if (openedCarouselId === null) {
      return;
    }

    const previousStep: number | null = selectedCarousel?.editor_step ?? null;

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

  if (openedCarouselId !== null && (openedSlideId !== null || isCreatingSlide)) {
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
          setStatusMessage(message);
          setHeldSlide(savedSlide);
          setIsCreatingSlide(false);
          setOpenedSlideId(savedSlide.id);
          requestReload();
        }}
        onImagesChanged={(message: string): void => {
          setStatusMessage(message);
          setHeldSlide(null);
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
  const showsBasic: boolean = carousel !== null && carousel.editor_step === CAROUSEL_STEP_BASIC;
  const showsSlides: boolean = carousel !== null && carousel.editor_step === CAROUSEL_STEP_SLIDES;

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
    pageLede = openStepSentence(carousel.editor_step);

    if (showsSlides) {
      pageLede = `${pageLede} A card shows the first image, or the text when there is none. ${carousel.live_slide_count} live.`;
    }
  }

  const headingName: string = carouselHeadingName(carousel, labelDraft);

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
            editorStep={carousel.editor_step}
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
                A draft stays off the live slide until you accept it. Images stay a manual upload.
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
  onOpenStep: (editorStep: number) => void;
  onBack: () => void;
  onSaved: (savedSlide: SlideReadResponse, message: string) => void;
  onImagesChanged: (message: string) => void;
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
  onOpenStep,
  onBack,
  onSaved,
  onImagesChanged,
  onSlideDeleted,
}: SlideEditorViewProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [skeleton, setSkeleton] = useState<SkeletonReadResponse | null>(null);
  const [skeletonError, setSkeletonError] = useState<unknown>(null);
  const [skeletonReady, setSkeletonReady] = useState<boolean>(false);
  const [slideName, setSlideName] = useState<string>(slide?.name ?? "");
  const [excludedIds, setExcludedIds] = useState<string[]>(slide?.excluded_slide_ids ?? []);
  const [textValues, setTextValues] = useState<Record<string, string>>({});
  const [saveError, setSaveError] = useState<unknown>(null);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [pendingDelete, setPendingDelete] = useState<boolean>(false);
  const [imageDrafts, setImageDrafts] = useState<SlideImageDraft[]>([]);
  const [showImageErrors, setShowImageErrors] = useState<boolean>(false);
  const imageDraftsRef = useRef<SlideImageDraft[]>(imageDrafts);
  imageDraftsRef.current = imageDrafts;
  const needsImage: boolean = skeleton !== null && skeletonRequiresImage(skeleton);
  const otherSlides: SlideReadResponse[] = (carousel?.slides ?? []).filter(
    (candidate: SlideReadResponse): boolean => candidate.id !== slide?.id,
  );
  const textElements: SkeletonElementReadResponse[] = skeleton === null
    ? []
    : orderedTextElements(skeleton.elements);
  const textWrites: SlideElementTextWrite[] = textElements.map(
    (element): SlideElementTextWrite => ({
      skeleton_element_id: element.id,
      value: textValues[element.id] ?? "",
    }),
  );

  useEffect((): (() => void) => {
    return (): void => {
      for (const draft of imageDraftsRef.current) {
        releaseSlideImageDraft(draft);
      }
    };
  }, []);

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

  const shownTextKey: string = slide === null
    ? ""
    : (slide.text_status === "draft" ? slide.draft_texts : slide.texts)
      .map((elementText): string => `${elementText.skeleton_element_id}:${elementText.value}`)
      .join("|");

  useEffect((): void => {
    setSlideName(slide?.name ?? "");
    setExcludedIds(slide?.excluded_slide_ids ?? []);

    if (skeleton === null) {
      setTextValues({});

      return;
    }

    setTextValues(textDraftsForSkeleton(skeleton, slide));
  }, [slide?.id, slide?.text_status, shownTextKey, skeleton]);

  useEffect((): void => {
    const imagesSection: HTMLElement | null = document.getElementById("slide-images");

    if (imagesSection !== null) {
      imagesSection.scrollIntoView({ block: "start" });
    }
  }, [slide?.id]);

  const handleSave = async (submitEvent: FormEvent<HTMLFormElement>): Promise<void> => {
    submitEvent.preventDefault();

    if (!canWrite || carousel === null || skeleton === null) {
      return;
    }

    const imageError: string | null = slide === null && needsImage
      ? firstSlideImageDraftError(imageDrafts)
      : null;

    if (imageError !== null) {
      setShowImageErrors(true);
      setSaveError(new Error(imageError));

      return;
    }

    if (slide === null && needsImage && imageDrafts.length === 0) {
      setShowImageErrors(true);
      setSaveError(new Error("This skeleton needs an image on the slide."));

      return;
    }

    if (slideName.trim() === "") {
      setSaveError(new Error("Name is required."));

      return;
    }

    const otherIds: Set<string> = new Set(
      otherSlides.map((candidate: SlideReadResponse): string => candidate.id),
    );
    const storedExcludedIds: string[] = excludedIds.filter(
      (excludedId: string): boolean => otherIds.has(excludedId),
    );
    const slideWriteRequest: SlideWriteRequest = {
      name: slideName.trim(),
      texts: textWrites,
      excluded_slide_ids: storedExcludedIds,
    };

    setIsSaving(true);
    setSaveError(null);
    setShowImageErrors(false);

    try {
      const imagePayloads: SlideImageCreatePayload[] = imageDrafts.map(
        (draft: SlideImageDraft): SlideImageCreatePayload => ({
          kind: draft.kind,
          file: draft.file,
          url: draft.url,
          license: draft.imageLicense,
          source: draft.imageSource,
          license_note: draft.licenseNote,
        }),
      );
      let savedSlide: SlideReadResponse;

      if (slide === null && needsImage) {
        savedSlide = await createSlideWithImages(carousel.id, slideWriteRequest, imagePayloads);
      } else if (slide === null) {
        savedSlide = await createCarouselSlide(carousel.id, slideWriteRequest);
      } else {
        savedSlide = await patchCarouselSlide(carousel.id, slide.id, slideWriteRequest);
      }

      const message: string = slide === null ? "Created the slide." : "Saved the slide.";

      for (const draft of imageDrafts) {
        releaseSlideImageDraft(draft);
      }

      setImageDrafts([]);
      onSaved(savedSlide, message);
    } catch (caughtError: unknown) {
      setSaveError(caughtError);
    } finally {
      setIsSaving(false);
    }
  };

  const handleGenerateText = async (): Promise<void> => {
    if (!canWrite || carousel === null || slide === null || !textGeneration.available) {
      return;
    }

    setIsGenerating(true);
    setSaveError(null);

    try {
      const draftedSlide: SlideReadResponse = await generateSlideText(carousel.id, slide.id);
      onSaved(draftedSlide, "Drafted text. Accept it to make this slide live.");
    } catch (caughtError: unknown) {
      setSaveError(caughtError);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleAcceptText = async (): Promise<void> => {
    if (!canWrite || carousel === null || slide === null || slide.text_status !== "draft") {
      return;
    }

    setIsSaving(true);
    setSaveError(null);

    try {
      const acceptedSlide: SlideReadResponse = await acceptSlideText(carousel.id, slide.id, {
        texts: textWrites,
      });
      onSaved(acceptedSlide, "Accepted the text. This slide is live.");
    } catch (caughtError: unknown) {
      setSaveError(caughtError);
    } finally {
      setIsSaving(false);
    }
  };

  const pageTitle: string = slide === null ? "New slide" : "Slide";
  let pageLede: string = (
    "The fields follow this carousel's skeleton. Preview shows the slide on that skeleton."
  );

  if (carousel !== null) {
    pageLede = `${openStepSentence(carousel.editor_step)} ${pageLede}`;
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
        <button type="button" onClick={onBack}>
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
            editorStep={carousel.editor_step}
            steps={carousel.steps}
            canWrite={canWrite}
            isSavingStep={isSavingStep}
            onOpenStep={onOpenStep}
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
            {slide === null || !needsImage ? null : (
              <section id="slide-images" className="slide-images">
                <h2>Image</h2>
                <p className="field-hint">
                  This skeleton uses one image on the slide.
                </p>
                {slide.images.length === 0 ? <p>No image on this slide yet.</p> : null}
                {slide.images.map((image: SlideImageReadResponse): ReactElement => (
                  <ImageMetadataEditor
                    key={image.id}
                    sourceId={carousel.id}
                    slideId={slide.id}
                    image={image}
                    canWrite={canWrite}
                    onChanged={(message: string): void => {
                      onImagesChanged(message);
                    }}
                  />
                ))}
                {canWrite && slide.images.length === 0 ? (
                  <ImageIntakeForm
                    sourceId={carousel.id}
                    slideId={slide.id}
                    onChanged={(message: string): void => {
                      onImagesChanged(message);
                    }}
                  />
                ) : null}
              </section>
            )}
            <form
              className="stack-form"
              onSubmit={(submitEvent: FormEvent<HTMLFormElement>): void => {
                void handleSave(submitEvent);
              }}
            >
              {slide === null && needsImage ? (
                <NewSlideImages
                  drafts={imageDrafts}
                  showFieldErrors={showImageErrors}
                  onDraftsChange={setImageDrafts}
                />
              ) : null}
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
                  The rule applies both ways. Saving it here also marks this slide on the other slide.
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
              {canWrite ? (
                <div className="button-row">
                  <button id="save-slide" type="submit" disabled={isSaving || isGenerating}>
                    {isSaving ? "Saving…" : "Save slide"}
                  </button>
                  {slide === null ? null : (
                    <button
                      id="generate-slide-text"
                      type="button"
                      disabled={!textGeneration.available || isGenerating || isSaving}
                      onClick={(): void => {
                        void handleGenerateText();
                      }}
                    >
                      {isGenerating ? "Generating…" : "Generate text"}
                    </button>
                  )}
                  {slide?.text_status === "draft" ? (
                    <button
                      id="accept-slide-text"
                      type="button"
                      disabled={isSaving || isGenerating}
                      onClick={(): void => {
                        void handleAcceptText();
                      }}
                    >
                      Accept text
                    </button>
                  ) : null}
                  {slide === null ? null : (
                    <button
                      type="button"
                      className="danger"
                      onClick={(): void => {
                        setPendingDelete(true);
                      }}
                    >
                      Delete slide
                    </button>
                  )}
                </div>
              ) : null}
            </form>
          </div>
          <SlideLivePreview
            sourceId={carousel.id}
            slideId={slide?.id ?? null}
            texts={textWrites}
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
            await deleteCarouselSlide(carousel.id, slide.id);
            setPendingDelete(false);
            onSlideDeleted();
          }}
        />
      ) : null}
    </section>
  );
}

interface ImageIntakeFormProps {
  sourceId: string;
  slideId: string;
  onChanged: (message: string) => void;
}

function ImageIntakeForm({
  sourceId,
  slideId,
  onChanged,
}: ImageIntakeFormProps): ReactElement {

  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [previewUrls, setPreviewUrls] = useState<string[]>([]);
  const [uploadLicense, setUploadLicense] = useState<SlideImageLicense>("cc0");
  const [uploadCarousel, setUploadCarousel] = useState<string>("");
  const [uploadNote, setUploadNote] = useState<string>("");
  const [uploadAlt, setUploadAlt] = useState<string>("");
  const [uploadError, setUploadError] = useState<unknown>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [importUrl, setImportUrl] = useState<string>("");
  const [importLicense, setImportLicense] = useState<SlideImageLicense>("cc0");
  const [importCarousel, setImportCarousel] = useState<string>("");
  const [importNote, setImportNote] = useState<string>("");
  const [importError, setImportError] = useState<unknown>(null);
  const [isImporting, setIsImporting] = useState<boolean>(false);

  useEffect((): (() => void) => {
    const nextUrls: string[] = selectedFiles.map((file: File): string => URL.createObjectURL(file));
    setPreviewUrls(nextUrls);

    return (): void => {
      for (const previewUrl of nextUrls) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [selectedFiles]);

  const handleUpload = async (submitEvent: FormEvent<HTMLFormElement>): Promise<void> => {
    submitEvent.preventDefault();
    setIsUploading(true);
    setUploadError(null);

    try {
      await uploadSlideImages(
        sourceId,
        slideId,
        selectedFiles,
        uploadLicense,
        uploadCarousel,
        uploadAlt,
        uploadNote,
      );
      setSelectedFiles([]);
      onChanged(selectedFiles.length === 1 ? "Uploaded the image." : "Uploaded the images.");
    } catch (caughtError: unknown) {
      setUploadError(caughtError);
    } finally {
      setIsUploading(false);
    }
  };

  const handleImport = async (submitEvent: FormEvent<HTMLFormElement>): Promise<void> => {
    submitEvent.preventDefault();
    setIsImporting(true);
    setImportError(null);

    const provenance: string = importCarousel.trim() === "" ? importUrl.trim() : importCarousel.trim();

    try {
      await importSlideImage(sourceId, slideId, {
        url: importUrl.trim(),
        license: importLicense,
        source: provenance,
        alt_text: null,
        license_note: importNote,
      });
      setImportUrl("");
      onChanged("Imported the image.");
    } catch (caughtError: unknown) {
      setImportError(caughtError);
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <>
      <form
        className="stack-form"
        onSubmit={(submitEvent: FormEvent<HTMLFormElement>): void => {
          void handleUpload(submitEvent);
        }}
      >
        <fieldset>
          <legend>Upload images</legend>
          <label>
            Files
            <input
              id="slide-image-files"
              type="file"
              accept=".svg,.png,.jpg,.jpeg,image/svg+xml,image/png,image/jpeg"
              onChange={(changeEvent): void => {
                const fileList: FileList | null = changeEvent.target.files;
                const nextFiles: File[] = fileList === null ? [] : [...fileList];
                setSelectedFiles(nextFiles);
              }}
            />
          </label>
          <p>SVG, PNG, or JPEG. 8 MB each. One license and source apply to every file in this upload.</p>
          {previewUrls.length === 0 ? null : (
            <div id="slide-image-preview" className="pending-thumbs">
              {previewUrls.map((previewUrl: string, previewIndex: number): ReactElement => (
                <img
                  key={previewUrl}
                  src={previewUrl}
                  alt={selectedFiles[previewIndex]?.name ?? "Selected image"}
                />
              ))}
            </div>
          )}
          <LicenseFields
            licenseId="slide-image-license"
            sourceId="slide-image-source"
            noteId="slide-image-note"
            imageLicense={uploadLicense}
            imageSource={uploadCarousel}
            licenseNote={uploadNote}
            onLicenseChange={setUploadLicense}
            onCarouselChange={setUploadCarousel}
            onNoteChange={setUploadNote}
          />
          <label>
            Alt text
            <input
              value={uploadAlt}
              onChange={(changeEvent): void => {
                setUploadAlt(changeEvent.target.value);
              }}
            />
          </label>
          <ErrorBanner error={uploadError} />
          <button
            id="upload-images"
            type="submit"
            disabled={isUploading || selectedFiles.length === 0 || uploadCarousel.trim() === ""}
          >
            {isUploading ? "Uploading…" : "Upload"}
          </button>
        </fieldset>
      </form>
      <form
        className="stack-form"
        onSubmit={(submitEvent: FormEvent<HTMLFormElement>): void => {
          void handleImport(submitEvent);
        }}
      >
        <fieldset>
          <legend>Import from a URL</legend>
          <label>
            Image URL
            <input
              id="import-image-url"
              value={importUrl}
              onChange={(changeEvent): void => {
                const nextUrl: string = changeEvent.target.value;
                setImportUrl(nextUrl);

                if (importCarousel.trim() === "" || importCarousel === importUrl) {
                  setImportCarousel(nextUrl);
                }
              }}
            />
          </label>
          <p>The server downloads the file once. Carousel records the provenance, and defaults to that URL.</p>
          <LicenseFields
            licenseId="import-image-license"
            sourceId="import-image-source"
            noteId="import-image-note"
            imageLicense={importLicense}
            imageSource={importCarousel}
            licenseNote={importNote}
            onLicenseChange={setImportLicense}
            onCarouselChange={setImportCarousel}
            onNoteChange={setImportNote}
          />
          <ErrorBanner error={importError} />
          <button
            id="import-image-submit"
            type="submit"
            disabled={isImporting || importUrl.trim() === ""}
          >
            {isImporting ? "Importing…" : "Import"}
          </button>
        </fieldset>
      </form>
    </>
  );
}

interface LicenseFieldsProps {
  licenseId: string;
  sourceId: string;
  noteId: string;
  imageLicense: SlideImageLicense;
  imageSource: string;
  licenseNote: string;
  onLicenseChange: (imageLicense: SlideImageLicense) => void;
  onCarouselChange: (imageSource: string) => void;
  onNoteChange: (licenseNote: string) => void;
}

function LicenseFields({
  licenseId,
  sourceId,
  noteId,
  imageLicense,
  imageSource,
  licenseNote,
  onLicenseChange,
  onCarouselChange,
  onNoteChange,
}: LicenseFieldsProps): ReactElement {

  return (
    <>
      <label>
        License
        <select
          id={licenseId}
          value={imageLicense}
          onChange={(changeEvent): void => {
            onLicenseChange(changeEvent.target.value as SlideImageLicense);
          }}
        >
          {LICENSE_OPTIONS.map((licenseOption: SlideImageLicense): ReactElement => (
            <option key={licenseOption} value={licenseOption}>
              {licenseOption}
            </option>
          ))}
        </select>
      </label>
      <label>
        Source
        <input
          id={sourceId}
          value={imageSource}
          onChange={(changeEvent): void => {
            onCarouselChange(changeEvent.target.value);
          }}
        />
      </label>
      <label>
        License note
        <input
          id={noteId}
          value={licenseNote}
          onChange={(changeEvent): void => {
            onNoteChange(changeEvent.target.value);
          }}
        />
      </label>
    </>
  );
}

interface ImageMetadataEditorProps {
  sourceId: string;
  slideId: string;
  image: SlideImageReadResponse;
  canWrite: boolean;
  onChanged: (message: string) => void;
}

function ImageMetadataEditor({
  sourceId,
  slideId,
  image,
  canWrite,
  onChanged,
}: ImageMetadataEditorProps): ReactElement {

  const [altText, setAltText] = useState<string>(image.alt_text ?? "");
  const [imageLicense, setImageLicense] = useState<SlideImageLicense>(image.license);
  const [imageSource, setImageSource] = useState<string>(image.source);
  const [licenseNote, setLicenseNote] = useState<string>(image.license_note);
  const [saveError, setSaveError] = useState<unknown>(null);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [pendingDelete, setPendingDelete] = useState<boolean>(false);

  useEffect((): void => {
    setAltText(image.alt_text ?? "");
    setImageLicense(image.license);
    setImageSource(image.source);
    setLicenseNote(image.license_note);
  }, [image]);

  const handleSave = async (): Promise<void> => {

    if (!canWrite) {
      return;
    }

    setIsSaving(true);
    setSaveError(null);

    try {
      await patchSlideImageMetadata(sourceId, slideId, image.id, {
        alt_text: altText,
        license: imageLicense,
        source: imageSource,
        license_note: licenseNote,
      });
      onChanged("Saved image details.");
    } catch (caughtError: unknown) {
      setSaveError(caughtError);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="image-editor">
      <img
        src={slideImageDisplayUrl(sourceId, slideId, image)}
        alt={image.alt_text ?? image.relative_path}
      />
      <div className="stack-form">
        <p className="mono">{image.relative_path}</p>
        <ErrorBanner error={saveError} />
        <label>
          License
          <select
            id={`image-license-${image.id}`}
            value={imageLicense}
            disabled={!canWrite}
            onChange={(changeEvent): void => {
              setImageLicense(changeEvent.target.value as SlideImageLicense);
            }}
          >
            {LICENSE_OPTIONS.map((licenseOption: SlideImageLicense): ReactElement => (
              <option key={licenseOption} value={licenseOption}>
                {licenseOption}
              </option>
            ))}
          </select>
        </label>
        <label>
          Carousel
          <input
            value={imageSource}
            disabled={!canWrite}
            onChange={(changeEvent): void => {
              setImageSource(changeEvent.target.value);
            }}
          />
        </label>
        <label>
          Alt text
          <input
            value={altText}
            disabled={!canWrite}
            onChange={(changeEvent): void => {
              setAltText(changeEvent.target.value);
            }}
          />
        </label>
        <label>
          License note
          <input
            value={licenseNote}
            disabled={!canWrite}
            onChange={(changeEvent): void => {
              setLicenseNote(changeEvent.target.value);
            }}
          />
        </label>
        <p>A licensed image needs a note. Other licenses store an empty note.</p>
        {canWrite ? (
          <div className="button-row">
            <button type="button" disabled={isSaving} onClick={(): void => {
              void handleSave();
            }}>
              {isSaving ? "Saving…" : "Save image"}
            </button>
            <button
              type="button"
              className="danger"
              onClick={(): void => {
                setPendingDelete(true);
              }}
            >
              Delete image
            </button>
          </div>
        ) : null}
      </div>
      {pendingDelete ? (
        <DeleteConfirmDialog
          headingId={`delete-image-${image.id}`}
          title="Delete this image?"
          body="Delete is blocked while a skeleton or an artifact stores this image, and the row stays. A slide also has to keep an image, free text, or a field."
          confirmLabel="Delete image"
          onCancel={(): void => {
            setPendingDelete(false);
          }}
          onConfirm={async (): Promise<void> => {
            await deleteSlideImage(sourceId, slideId, image.id);
            setPendingDelete(false);
            onChanged("Deleted the image.");
          }}
        />
      ) : null}
    </div>
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
