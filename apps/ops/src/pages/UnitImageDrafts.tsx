import { useState, type ReactElement } from "react";

import type { UnitImageLicense } from "../api/types";
import {
  UNIT_IMAGE_URL_ERROR,
  UNIT_IMAGE_URL_SCHEME_ERROR,
  isHttpImageUrl,
  unitImageDraftError,
  type UnitImageDraftCheck,
} from "./unitImageDraft";

const LICENSE_OPTIONS: UnitImageLicense[] = [
  "cc0",
  "public_domain",
  "owned",
  "licensed",
];

export interface UnitImageDraft extends UnitImageDraftCheck {
  clientId: string;
  file: File | null;
  previewUrl: string;
}

export interface NewUnitImagesProps {
  drafts: UnitImageDraft[];
  showFieldErrors: boolean;
  onDraftsChange: (drafts: UnitImageDraft[]) => void;
}

/**
 * Images on the Add unit form. Thumbnails and license fields show before save.
 *
 * @param props - Pending images and the change callback
 * @returns The Images section
 */
export function NewUnitImages({
  drafts,
  showFieldErrors,
  onDraftsChange,
}: NewUnitImagesProps): ReactElement {

  const [urlText, setUrlText] = useState<string>("");
  const [urlError, setUrlError] = useState<string | null>(null);

  const addFiles = (fileList: FileList | null): void => {
    const nextFile: File | undefined = fileList === null ? undefined : fileList[0];

    if (nextFile === undefined) {
      return;
    }

    for (const draft of drafts) {
      releaseUnitImageDraft(draft);
    }

    const nextDraft: UnitImageDraft = {
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
      setUrlError(UNIT_IMAGE_URL_ERROR);

      return;
    }

    if (!isHttpImageUrl(trimmedUrl)) {
      setUrlError(UNIT_IMAGE_URL_SCHEME_ERROR);

      return;
    }

    for (const draft of drafts) {
      releaseUnitImageDraft(draft);
    }

    const urlDraft: UnitImageDraft = {
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

  const updateDraft = (clientId: string, patch: Partial<UnitImageDraft>): void => {
    const nextDrafts: UnitImageDraft[] = drafts.map((draft: UnitImageDraft): UnitImageDraft => {
      if (draft.clientId !== clientId) {
        return draft;
      }

      return { ...draft, ...patch };
    });

    onDraftsChange(nextDrafts);
  };

  const removeDraft = (clientId: string): void => {
    const removed: UnitImageDraft | undefined = drafts.find(
      (draft: UnitImageDraft): boolean => draft.clientId === clientId,
    );

    if (removed !== undefined) {
      releaseUnitImageDraft(removed);
    }

    onDraftsChange(drafts.filter(
      (draft: UnitImageDraft): boolean => draft.clientId !== clientId,
    ));
  };

  return (
    <section id="unit-images" className="unit-images">
      <h2>Images</h2>
      <p className="field-hint">
        One image per unit. Upload a file or add a URL. The license, source, and note are saved with it.
      </p>
      <label>
        Files
        <input
          id="new-unit-image-files"
          type="file"
          accept=".svg,.png,.jpg,.jpeg,image/svg+xml,image/png,image/jpeg"
          onChange={(changeEvent): void => {
            addFiles(changeEvent.target.files);
            changeEvent.target.value = "";
          }}
        />
      </label>
      <p className="field-hint">SVG, PNG, or JPEG. 8 MB each.</p>
      <div className="unit-image-url-row">
        <label>
          Image URL
          <input
            id="new-unit-image-url"
            value={urlText}
            onChange={(changeEvent): void => {
              setUrlText(changeEvent.target.value);
              setUrlError(null);
            }}
          />
        </label>
        <button id="add-unit-image-url" type="button" onClick={addUrl}>
          Add URL
        </button>
      </div>
      {urlError === null ? null : <p className="error-banner">{urlError}</p>}
      <div className="unit-image-drafts">
        {drafts.map((draft: UnitImageDraft, draftIndex: number): ReactElement => {
          const draftError: string | null = showFieldErrors ? unitImageDraftError(draft) : null;
          const kindLabel: string = draft.kind === "file"
            ? (draft.fileName ?? "File")
            : draft.url;

          return (
            <div className="image-editor" key={draft.clientId}>
              <img
                id={`new-unit-image-thumb-${draftIndex}`}
                src={draft.previewUrl}
                alt={kindLabel}
              />
              <div className="stack-form">
                <p className="mono">{kindLabel}</p>
                {draftError === null ? null : <p className="error-banner">{draftError}</p>}
                <DraftLicenseFields
                  draftIndex={draftIndex}
                  draft={draft}
                  onLicenseChange={(imageLicense: UnitImageLicense): void => {
                    updateDraft(draft.clientId, { imageLicense });
                  }}
                  onSourceChange={(imageSource: string): void => {
                    updateDraft(draft.clientId, { imageSource });
                  }}
                  onNoteChange={(licenseNote: string): void => {
                    updateDraft(draft.clientId, { licenseNote });
                  }}
                />
                <p className="field-hint">A licensed image needs a note. Other licenses store an empty note.</p>
                <button
                  type="button"
                  id={`remove-new-unit-image-${draftIndex}`}
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
  draft: UnitImageDraft;
  onLicenseChange: (imageLicense: UnitImageLicense) => void;
  onSourceChange: (imageSource: string) => void;
  onNoteChange: (licenseNote: string) => void;
}

function DraftLicenseFields({
  draftIndex,
  draft,
  onLicenseChange,
  onSourceChange,
  onNoteChange,
}: DraftLicenseFieldsProps): ReactElement {

  return (
    <>
      <label>
        License
        <select
          id={`new-unit-image-license-${draftIndex}`}
          value={draft.imageLicense}
          onChange={(changeEvent): void => {
            onLicenseChange(changeEvent.target.value as UnitImageLicense);
          }}
        >
          {LICENSE_OPTIONS.map((licenseOption: UnitImageLicense): ReactElement => (
            <option key={licenseOption} value={licenseOption}>
              {licenseOption}
            </option>
          ))}
        </select>
      </label>
      <label>
        Source
        <input
          id={`new-unit-image-source-${draftIndex}`}
          value={draft.imageSource}
          onChange={(changeEvent): void => {
            onSourceChange(changeEvent.target.value);
          }}
        />
      </label>
      <label>
        License note
        <input
          id={`new-unit-image-note-${draftIndex}`}
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
export function releaseUnitImageDraft(draft: UnitImageDraft): void {

  if (draft.kind === "file") {
    URL.revokeObjectURL(draft.previewUrl);
  }
}
