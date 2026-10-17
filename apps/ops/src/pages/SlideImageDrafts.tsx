import { useState, type ReactElement } from "react";

import type { SlideImageLicense } from "../api/types";
import {
  SLIDE_IMAGE_URL_ERROR,
  SLIDE_IMAGE_URL_SCHEME_ERROR,
  isHttpImageUrl,
  slideImageDraftError,
  type SlideImageDraftCheck,
} from "./slideImageDraft";

const LICENSE_OPTIONS: SlideImageLicense[] = [
  "cc0",
  "public_domain",
  "owned",
  "licensed",
];

export interface SlideImageDraft extends SlideImageDraftCheck {
  clientId: string;
  file: File | null;
  previewUrl: string;
}

export interface NewSlideImagesProps {
  drafts: SlideImageDraft[];
  showFieldErrors: boolean;
  onDraftsChange: (drafts: SlideImageDraft[]) => void;
}

/**
 * Images on the Add slide form. Thumbnails and license fields show before save.
 *
 * @param props - Pending images and the change callback
 * @returns The Images section
 */
export function NewSlideImages({
  drafts,
  showFieldErrors,
  onDraftsChange,
}: NewSlideImagesProps): ReactElement {

  const [urlText, setUrlText] = useState<string>("");
  const [urlError, setUrlError] = useState<string | null>(null);

  const addFiles = (fileList: FileList | null): void => {
    const nextFile: File | undefined = fileList === null ? undefined : fileList[0];

    if (nextFile === undefined) {
      return;
    }

    for (const draft of drafts) {
      releaseSlideImageDraft(draft);
    }

    const nextDraft: SlideImageDraft = {
      clientId: crypto.randomUUID(),
      kind: "file",
      file: nextFile,
      fileName: nextFile.name,
      url: "",
      previewUrl: URL.createObjectURL(nextFile),
      imageLicense: "cc0",
      imageSource: "",
      licenseNote: "",
    };

    onDraftsChange([nextDraft]);
  };

  const addUrl = (): void => {
    const trimmedUrl: string = urlText.trim();

    if (trimmedUrl === "") {
      setUrlError(SLIDE_IMAGE_URL_ERROR);

      return;
    }

    if (!isHttpImageUrl(trimmedUrl)) {
      setUrlError(SLIDE_IMAGE_URL_SCHEME_ERROR);

      return;
    }

    for (const draft of drafts) {
      releaseSlideImageDraft(draft);
    }

    const urlDraft: SlideImageDraft = {
      clientId: crypto.randomUUID(),
      kind: "url",
      file: null,
      fileName: null,
      url: trimmedUrl,
      previewUrl: trimmedUrl,
      imageLicense: "cc0",
      imageSource: trimmedUrl,
      licenseNote: "",
    };

    setUrlError(null);
    setUrlText("");
    onDraftsChange([urlDraft]);
  };

  const updateDraft = (clientId: string, patch: Partial<SlideImageDraft>): void => {
    const nextDrafts: SlideImageDraft[] = drafts.map((draft: SlideImageDraft): SlideImageDraft => {
      if (draft.clientId !== clientId) {
        return draft;
      }

      return { ...draft, ...patch };
    });

    onDraftsChange(nextDrafts);
  };

  const removeDraft = (clientId: string): void => {
    const removed: SlideImageDraft | undefined = drafts.find(
      (draft: SlideImageDraft): boolean => draft.clientId === clientId,
    );

    if (removed !== undefined) {
      releaseSlideImageDraft(removed);
    }

    onDraftsChange(drafts.filter(
      (draft: SlideImageDraft): boolean => draft.clientId !== clientId,
    ));
  };

  return (
    <section id="slide-images" className="slide-images">
      <h2>Images</h2>
      <p className="field-hint">
        One image per slide. Upload a file or add a URL. The license, source, and note are saved with it.
      </p>
      <label>
        Files
        <input
          id="new-slide-image-files"
          type="file"
          accept=".svg,.png,.jpg,.jpeg,image/svg+xml,image/png,image/jpeg"
          onChange={(changeEvent): void => {
            addFiles(changeEvent.target.files);
            changeEvent.target.value = "";
          }}
        />
      </label>
      <p className="field-hint">SVG, PNG, or JPEG. 8 MB each.</p>
      <div className="slide-image-url-row">
        <label>
          Image URL
          <input
            id="new-slide-image-url"
            value={urlText}
            onChange={(changeEvent): void => {
              setUrlText(changeEvent.target.value);
              setUrlError(null);
            }}
          />
        </label>
        <button id="add-slide-image-url" type="button" onClick={addUrl}>
          Add URL
        </button>
      </div>
      {urlError === null ? null : <p className="error-banner">{urlError}</p>}
      <div className="slide-image-drafts">
        {drafts.map((draft: SlideImageDraft, draftIndex: number): ReactElement => {
          const draftError: string | null = showFieldErrors ? slideImageDraftError(draft) : null;
          const kindLabel: string = draft.kind === "file"
            ? (draft.fileName ?? "File")
            : draft.url;

          return (
            <div className="image-editor" key={draft.clientId}>
              <img
                id={`new-slide-image-thumb-${draftIndex}`}
                src={draft.previewUrl}
                alt={kindLabel}
              />
              <div className="stack-form">
                <p className="mono">{kindLabel}</p>
                {draftError === null ? null : <p className="error-banner">{draftError}</p>}
                <DraftLicenseFields
                  draftIndex={draftIndex}
                  draft={draft}
                  onLicenseChange={(imageLicense: SlideImageLicense): void => {
                    updateDraft(draft.clientId, { imageLicense });
                  }}
                  onCarouselChange={(imageSource: string): void => {
                    updateDraft(draft.clientId, { imageSource });
                  }}
                  onNoteChange={(licenseNote: string): void => {
                    updateDraft(draft.clientId, { licenseNote });
                  }}
                />
                <p className="field-hint">A licensed image needs a note. Other licenses store an empty note.</p>
                <button
                  type="button"
                  id={`remove-new-slide-image-${draftIndex}`}
                  onClick={(): void => {
                    removeDraft(draft.clientId);
                  }}
                >
                  Remove image
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

interface DraftLicenseFieldsProps {
  draftIndex: number;
  draft: SlideImageDraft;
  onLicenseChange: (imageLicense: SlideImageLicense) => void;
  onCarouselChange: (imageSource: string) => void;
  onNoteChange: (licenseNote: string) => void;
}

function DraftLicenseFields({
  draftIndex,
  draft,
  onLicenseChange,
  onCarouselChange,
  onNoteChange,
}: DraftLicenseFieldsProps): ReactElement {

  return (
    <>
      <label>
        License
        <select
          id={`new-slide-image-license-${draftIndex}`}
          value={draft.imageLicense}
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
          id={`new-slide-image-source-${draftIndex}`}
          value={draft.imageSource}
          onChange={(changeEvent): void => {
            onCarouselChange(changeEvent.target.value);
          }}
        />
      </label>
      <label>
        License note
        <input
          id={`new-slide-image-note-${draftIndex}`}
          value={draft.licenseNote}
          onChange={(changeEvent): void => {
            onNoteChange(changeEvent.target.value);
          }}
        />
      </label>
    </>
  );
}

/**
 * Drop a local thumbnail. URL previews are remote and are not revoked.
 *
 * @param draft - Pending image
 */
export function releaseSlideImageDraft(draft: SlideImageDraft): void {

  if (draft.kind === "file") {
    URL.revokeObjectURL(draft.previewUrl);
  }
}
