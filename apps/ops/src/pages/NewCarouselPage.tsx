import { useEffect, useState, type FormEvent, type ReactElement } from "react";

import { createCarousel, listSkeletons } from "../api/client";
import type { CarouselReadResponse, SkeletonReadResponse } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import { useCanWriteOps } from "../session/OpsSessionContext";
import { createCarouselFieldError } from "./createCarousel";

export interface NewCarouselPageProps {
  onCreated: (createdCarousel: CarouselReadResponse) => void;
  onCancel: () => void;
}

/**
 * Create Carousel tab: a name and a required skeleton, then open the carousel.
 *
 * @param props - Success and cancel navigation callbacks
 * @returns The create-carousel form
 */
export function NewCarouselPage({ onCreated, onCancel }: NewCarouselPageProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [sourceName, setCarouselName] = useState<string>("");
  const [skeletonId, setSkeletonId] = useState<string>("");
  const [skeletons, setSkeletons] = useState<SkeletonReadResponse[]>([]);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [saveError, setSaveError] = useState<unknown>(null);
  const [isSaving, setIsSaving] = useState<boolean>(false);

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadSkeletons = async (): Promise<void> => {

      try {
        const loadedSkeletons: SkeletonReadResponse[] = await listSkeletons();

        if (isCancelled) {
          return;
        }

        setSkeletons(loadedSkeletons);
        setLoadError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setLoadError(caughtError);
      }
    };

    if (canWrite) {
      void loadSkeletons();
    }

    return (): void => {
      isCancelled = true;
    };
  }, [canWrite]);

  const handleCreate = async (submitEvent: FormEvent<HTMLFormElement>): Promise<void> => {
    submitEvent.preventDefault();

    if (!canWrite || isSaving) {
      return;
    }

    const fieldError: string | null = createCarouselFieldError(sourceName, skeletonId);

    if (fieldError !== null) {
      setSaveError(new Error(fieldError));

      return;
    }

    setIsSaving(true);
    setSaveError(null);

    try {
      const createdCarousel: CarouselReadResponse = await createCarousel({
        name: sourceName.trim(),
        skeleton_id: skeletonId,
      });

      onCreated(createdCarousel);
    } catch (caughtError: unknown) {
      setSaveError(caughtError);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>Create Carousel</h1>
          <p className="lede">
            A carousel needs a name and a skeleton. It then opens on Basic.
          </p>
        </div>
        <button type="button" onClick={onCancel}>
          Back to Carousels
        </button>
      </div>
      <ReadOnlyNotice />
      {canWrite ? (
        <form
          id="create-carousel-form"
          className="stack-form"
          onSubmit={(submitEvent: FormEvent<HTMLFormElement>): void => {
            void handleCreate(submitEvent);
          }}
        >
          <ErrorBanner error={loadError} />
          <label>
            Name
            <input
              id="create-carousel-name"
              value={sourceName}
              onChange={(changeEvent): void => {
                setCarouselName(changeEvent.target.value);
              }}
            />
          </label>
          <label>
            Skeleton
            <select
              id="create-carousel-skeleton"
              value={skeletonId}
              onChange={(changeEvent): void => {
                setSkeletonId(changeEvent.target.value);
              }}
            >
              <option value="">Choose a skeleton</option>
              {skeletons.map((skeleton: SkeletonReadResponse): ReactElement => (
                <option key={skeleton.id} value={skeleton.id}>
                  {skeleton.name}
                </option>
              ))}
            </select>
          </label>
          <p className="field-hint">
            The skeleton is required and stays locked. Slides follow that skeleton.
          </p>
          <ErrorBanner error={saveError} />
          <div className="button-row">
            <button id="create-carousel-submit" type="submit" disabled={isSaving || skeletons.length === 0}>
              {isSaving ? "Creating…" : "Create Carousel"}
            </button>
            <button type="button" onClick={onCancel} disabled={isSaving}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <p>Creating a carousel is an admin action.</p>
      )}
    </section>
  );
}
