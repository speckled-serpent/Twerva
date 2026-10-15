import { useEffect, useRef, useState, type FormEvent, type ReactElement } from "react";

import {
  createSourceUnit,
  createUnitWithImages,
  deleteSource,
  deleteSourceUnit,
  deleteUnitImage,
  fetchSourceById,
  fetchThemeById,
  listAlbums,
  patchSourceUnit,
  patchUnitImageMetadata,
  renameSource,
  importUnitImage,
  unitImageDisplayUrl,
  uploadUnitImages,
} from "../api/client";
import type {
  SourceListItemResponse,
  SourceReadResponse,
  ThemeElementReadResponse,
  ThemeReadResponse,
  UnitElementTextWrite,
  UnitImageCreatePayload,
  UnitImageLicense,
  UnitImageReadResponse,
  UnitReadResponse,
  UnitWriteRequest,
} from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import {
  NewUnitImages,
  releaseUnitImageDraft,
  type UnitImageDraft,
} from "./UnitImageDrafts";
import { firstUnitImageDraftError } from "./unitImageDraft";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import { useCanWriteOps } from "../session/OpsSessionContext";
import { UnitLivePreview } from "./UnitLivePreview";
import {
  labelForTextElement,
  orderedTextElements,
  textDraftsForTheme,
  themeRequiresImage,
} from "./unitThemeShape";

const LICENSE_OPTIONS: UnitImageLicense[] = [
  "cc0",
  "public_domain",
  "owned",
  "licensed",
];

export interface SourcesOpenRequest {
  sourceId: string;
  statusMessage: string;
}

export interface SourcesPageProps {
  openRequest: SourcesOpenRequest | null;
}

/**
 * Sources: one list of theme-bound sources, and a unit editor that follows the theme.
 *
 * @param props - Optional open request from Create Source
 * @returns The Sources page
 */
export function SourcesPage({ openRequest }: SourcesPageProps): ReactElement {

  const [listedSources, setListedSources] = useState<SourceListItemResponse[]>([]);
  const [openedSourceId, setOpenedSourceId] = useState<string | null>(
    openRequest?.sourceId ?? null,
  );
  const [openedUnitId, setOpenedUnitId] = useState<string | null>(null);
  const [isCreatingUnit, setIsCreatingUnit] = useState<boolean>(false);
  const [selectedSource, setSelectedSource] = useState<SourceReadResponse | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [statusMessage, setStatusMessage] = useState<string>(openRequest?.statusMessage ?? "");
  const [reloadToken, setReloadToken] = useState<number>(0);
  const [heldUnit, setHeldUnit] = useState<UnitReadResponse | null>(null);

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadSources = async (): Promise<void> => {

      try {
        const loadedSources: SourceListItemResponse[] = await listAlbums();

        if (isCancelled) {
          return;
        }

        setListedSources(loadedSources);
        setLoadError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setLoadError(caughtError);
      }
    };

    void loadSources();

    return (): void => {
      isCancelled = true;
    };
  }, [reloadToken]);

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    if (openedSourceId === null) {
      setSelectedSource(null);

      return (): void => {
        isCancelled = true;
      };
    }

    const loadSource = async (): Promise<void> => {

      try {
        const loadedSource: SourceReadResponse = await fetchSourceById(openedSourceId);

        if (isCancelled) {
          return;
        }

        setSelectedSource(loadedSource);
        setLoadError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setSelectedSource(null);
        setLoadError(caughtError);
      }
    };

    void loadSource();

    return (): void => {
      isCancelled = true;
    };
  }, [openedSourceId, reloadToken]);

  useEffect((): void => {
    if (openRequest === null) {
      return;
    }

    setOpenedSourceId(openRequest.sourceId);
    setOpenedUnitId(null);
    setIsCreatingUnit(false);
    setHeldUnit(null);
    setStatusMessage(openRequest.statusMessage);
  }, [openRequest]);

  const requestReload = (): void => {
    setReloadToken((currentToken: number): number => currentToken + 1);
  };

  if (openedSourceId !== null && (openedUnitId !== null || isCreatingUnit)) {
    const loadedUnit: UnitReadResponse | null = findUnit(selectedSource, openedUnitId);
    const openedUnit: UnitReadResponse | null = isCreatingUnit
      ? null
      : heldUnit !== null && heldUnit.id === openedUnitId
        ? heldUnit
        : loadedUnit;

    return (
      <UnitEditorView
        source={selectedSource}
        unit={openedUnit}
        loadError={loadError}
        statusMessage={statusMessage}
        onBack={(): void => {
          setOpenedUnitId(null);
          setIsCreatingUnit(false);
          setHeldUnit(null);
          setStatusMessage("");
        }}
        onSaved={(savedUnit: UnitReadResponse, message: string): void => {
          setStatusMessage(message);
          setHeldUnit(savedUnit);
          setIsCreatingUnit(false);
          setOpenedUnitId(savedUnit.id);
          requestReload();
        }}
        onImagesChanged={(message: string): void => {
          setStatusMessage(message);
          setHeldUnit(null);
          requestReload();
        }}
        onUnitDeleted={(): void => {
          setOpenedUnitId(null);
          setIsCreatingUnit(false);
          setHeldUnit(null);
          setStatusMessage("Deleted the unit.");
          requestReload();
        }}
      />
    );
  }

  if (openedSourceId !== null) {
    return (
      <AlbumView
        source={selectedSource}
        loadError={loadError}
        statusMessage={statusMessage}
        onBack={(): void => {
          setOpenedSourceId(null);
          setStatusMessage("");
        }}
        onOpenUnit={(unitId: string): void => {
          setHeldUnit(null);
          setOpenedUnitId(unitId);
          setIsCreatingUnit(false);
          setStatusMessage("");
        }}
        onCreateUnit={(): void => {
          setHeldUnit(null);
          setOpenedUnitId(null);
          setIsCreatingUnit(true);
          setStatusMessage("");
        }}
        onSourceChanged={(message: string): void => {
          setStatusMessage(message);
          requestReload();
        }}
        onSourceDeleted={(): void => {
          setOpenedSourceId(null);
          setStatusMessage("Deleted the album.");
          requestReload();
        }}
      />
    );
  }

  return (
    <AlbumListView
      albums={listedSources}
      loadError={loadError}
      statusMessage={statusMessage}
      onOpenAlbum={(sourceId: string): void => {
        setOpenedSourceId(sourceId);
        setStatusMessage("");
      }}
      onAlbumDeleted={(albumName: string): void => {
        setStatusMessage(`Deleted album ${albumName}.`);
        requestReload();
      }}
    />
  );
}

interface AlbumListViewProps {
  albums: SourceListItemResponse[];
  loadError: unknown;
  statusMessage: string;
  onOpenAlbum: (sourceId: string) => void;
  onAlbumDeleted: (albumName: string) => void;
}

function AlbumListView({
  albums,
  loadError,
  statusMessage,
  onOpenAlbum,
  onAlbumDeleted,
}: AlbumListViewProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [pendingDelete, setPendingDelete] = useState<SourceListItemResponse | null>(null);

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>Sources</h1>
          <p className="lede">
            Each source has a theme. Open one to edit units.
            Create lives on Create Source.
          </p>
        </div>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}
      {loadError !== null ? null : albums.length === 0 ? (
        <p>No sources yet. Use Create Source to add one.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Units</th>
              <th>Open</th>
              <th>Delete</th>
            </tr>
          </thead>
          <tbody>
            {albums.map((album: SourceListItemResponse): ReactElement => (
              <tr key={album.id}>
                <td>{album.name}</td>
                <td>{album.unit_count}</td>
                <td>
                  <button
                    type="button"
                    onClick={(): void => {
                      onOpenAlbum(album.id);
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
          body="This removes the album and its units. Delete is blocked while a theme or an artifact still stores one of its images, and the album stays."
          confirmLabel="Delete album"
          onCancel={(): void => {
            setPendingDelete(null);
          }}
          onConfirm={async (): Promise<void> => {
            await deleteSource(pendingDelete.id);
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
  source: SourceReadResponse | null;
  loadError: unknown;
  statusMessage: string;
  onBack: () => void;
  onOpenUnit: (unitId: string) => void;
  onCreateUnit: () => void;
  onSourceChanged: (message: string) => void;
  onSourceDeleted: () => void;
}

function AlbumView({
  source,
  loadError,
  statusMessage,
  onBack,
  onOpenUnit,
  onCreateUnit,
  onSourceChanged,
  onSourceDeleted,
}: AlbumViewProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [albumName, setAlbumName] = useState<string>(source?.name ?? "");
  const [saveError, setSaveError] = useState<unknown>(null);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [pendingDelete, setPendingDelete] = useState<boolean>(false);
  const [pendingUnitDelete, setPendingUnitDelete] = useState<UnitReadResponse | null>(null);

  useEffect((): void => {
    setAlbumName(source?.name ?? "");
  }, [source]);

  const handleRename = async (submitEvent: FormEvent<HTMLFormElement>): Promise<void> => {
    submitEvent.preventDefault();

    if (!canWrite || source === null) {
      return;
    }

    setIsSaving(true);
    setSaveError(null);

    try {
      const renamedSource: SourceReadResponse = await renameSource(source.id, {
        name: albumName,
      });
      onSourceChanged(`Renamed album to ${renamedSource.name}.`);
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
          <h1>{source === null ? "Album" : source.name}</h1>
          <p className="lede">
            Units in this album. A card shows the first image, or the text when there is none.
          </p>
        </div>
        <button type="button" onClick={onBack}>
          Back to albums
        </button>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      <ErrorBanner error={saveError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}
      {source === null ? (
        <p>Loading album…</p>
      ) : (
        <>
          {canWrite ? (
            <form
              className="stack-form"
              onSubmit={(submitEvent: FormEvent<HTMLFormElement>): void => {
                void handleRename(submitEvent);
              }}
            >
              <label>
                Album name
                <input
                  id="rename-album-name"
                  value={albumName}
                  onChange={(changeEvent): void => {
                    setAlbumName(changeEvent.target.value);
                  }}
                />
              </label>
              <div className="button-row">
                <button type="submit" disabled={isSaving || albumName.trim() === ""}>
                  {isSaving ? "Saving…" : "Rename album"}
                </button>
                <button
                  type="button"
                  className="danger"
                  onClick={(): void => {
                    setPendingDelete(true);
                  }}
                >
                  Delete album
                </button>
                <button id="add-unit" type="button" onClick={onCreateUnit}>
                  Add unit
                </button>
              </div>
            </form>
          ) : null}
          {source.units.length === 0 ? (
            <p>No units yet.</p>
          ) : (
            <ul className="unit-grid">
              {source.units.map((unit: UnitReadResponse): ReactElement => (
                <li key={unit.id}>
                  <button
                    type="button"
                    className="unit-card"
                    onClick={(): void => {
                      onOpenUnit(unit.id);
                    }}
                  >
                    <UnitCardBody sourceId={source.id} unit={unit} />
                  </button>
                  {canWrite ? (
                    <button
                      type="button"
                      className="danger"
                      onClick={(): void => {
                        setPendingUnitDelete(unit);
                      }}
                    >
                      Delete unit
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      {pendingDelete && source !== null ? (
        <DeleteConfirmDialog
          headingId="delete-open-album-heading"
          title={`Delete ${source.name}?`}
          body="This removes the album and its units. Delete is blocked while a theme or an artifact still stores one of its images, and the album stays."
          confirmLabel="Delete album"
          onCancel={(): void => {
            setPendingDelete(false);
          }}
          onConfirm={async (): Promise<void> => {
            await deleteSource(source.id);
            setPendingDelete(false);
            onSourceDeleted();
          }}
        />
      ) : null}
      {pendingUnitDelete !== null && source !== null ? (
        <DeleteConfirmDialog
          headingId="delete-unit-heading"
          title="Delete this unit?"
          body="Delete is blocked while a theme or an artifact still stores one of its images, and the unit stays."
          confirmLabel="Delete unit"
          onCancel={(): void => {
            setPendingUnitDelete(null);
          }}
          onConfirm={async (): Promise<void> => {
            await deleteSourceUnit(source.id, pendingUnitDelete.id);
            setPendingUnitDelete(null);
            onSourceChanged("Deleted the unit.");
          }}
        />
      ) : null}
    </section>
  );
}

interface UnitCardBodyProps {
  sourceId: string;
  unit: UnitReadResponse;
}

function UnitCardBody({ sourceId, unit }: UnitCardBodyProps): ReactElement {

  const firstImage: UnitImageReadResponse | undefined = unit.images[0];
  const excerpt: string = unitExcerpt(unit);

  return (
    <>
      <p className="unit-card-excerpt">{unit.name}</p>
      {firstImage === undefined ? (
        <p className="unit-card-excerpt">{excerpt}</p>
      ) : (
        <img
          src={unitImageDisplayUrl(sourceId, unit.id, firstImage)}
          alt={firstImage.alt_text ?? excerpt}
        />
      )}
      {firstImage === undefined ? null : <p className="unit-card-excerpt">{excerpt}</p>}
    </>
  );
}

interface UnitEditorViewProps {
  source: SourceReadResponse | null;
  unit: UnitReadResponse | null;
  loadError: unknown;
  statusMessage: string;
  onBack: () => void;
  onSaved: (savedUnit: UnitReadResponse, message: string) => void;
  onImagesChanged: (message: string) => void;
  onUnitDeleted: () => void;
}

function UnitEditorView({
  source,
  unit,
  loadError,
  statusMessage,
  onBack,
  onSaved,
  onImagesChanged,
  onUnitDeleted,
}: UnitEditorViewProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [theme, setTheme] = useState<ThemeReadResponse | null>(null);
  const [themeError, setThemeError] = useState<unknown>(null);
  const [themeReady, setThemeReady] = useState<boolean>(false);
  const [unitName, setUnitName] = useState<string>(unit?.name ?? "");
  const [textValues, setTextValues] = useState<Record<string, string>>({});
  const [saveError, setSaveError] = useState<unknown>(null);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [pendingDelete, setPendingDelete] = useState<boolean>(false);
  const [imageDrafts, setImageDrafts] = useState<UnitImageDraft[]>([]);
  const [showImageErrors, setShowImageErrors] = useState<boolean>(false);
  const imageDraftsRef = useRef<UnitImageDraft[]>(imageDrafts);
  imageDraftsRef.current = imageDrafts;
  const needsImage: boolean = theme !== null && themeRequiresImage(theme);
  const textElements: ThemeElementReadResponse[] = theme === null
    ? []
    : orderedTextElements(theme.elements);
  const textWrites: UnitElementTextWrite[] = textElements.map(
    (element): UnitElementTextWrite => ({
      theme_element_id: element.id,
      value: textValues[element.id] ?? "",
    }),
  );

  useEffect((): (() => void) => {
    return (): void => {
      for (const draft of imageDraftsRef.current) {
        releaseUnitImageDraft(draft);
      }
    };
  }, []);

  useEffect((): (() => void) => {
    if (source === null) {
      return (): void => {
        return;
      };
    }

    let isCancelled: boolean = false;
    const themeId: string = source.theme_id;

    const loadTheme = async (): Promise<void> => {
      setThemeReady(false);

      try {
        const loadedTheme: ThemeReadResponse = await fetchThemeById(themeId);

        if (isCancelled) {
          return;
        }

        setTheme(loadedTheme);
        setThemeError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setTheme(null);
        setThemeError(caughtError);
      } finally {
        if (!isCancelled) {
          setThemeReady(true);
        }
      }
    };

    void loadTheme();

    return (): void => {
      isCancelled = true;
    };
  }, [source?.id, source?.theme_id]);

  useEffect((): void => {
    setUnitName(unit?.name ?? "");

    if (theme === null) {
      setTextValues({});

      return;
    }

    setTextValues(textDraftsForTheme(theme, unit));
  }, [unit?.id, theme]);

  useEffect((): void => {
    const imagesSection: HTMLElement | null = document.getElementById("unit-images");

    if (imagesSection !== null) {
      imagesSection.scrollIntoView({ block: "start" });
    }
  }, [unit?.id]);

  const handleSave = async (submitEvent: FormEvent<HTMLFormElement>): Promise<void> => {
    submitEvent.preventDefault();

    if (!canWrite || source === null || theme === null) {
      return;
    }

    const imageError: string | null = unit === null && needsImage
      ? firstUnitImageDraftError(imageDrafts)
      : null;

    if (imageError !== null) {
      setShowImageErrors(true);
      setSaveError(new Error(imageError));

      return;
    }

    if (unit === null && needsImage && imageDrafts.length === 0) {
      setShowImageErrors(true);
      setSaveError(new Error("This theme needs an image on the unit."));

      return;
    }

    if (unitName.trim() === "") {
      setSaveError(new Error("Name is required."));

      return;
    }

    const unitWriteRequest: UnitWriteRequest = {
      name: unitName.trim(),
      texts: textWrites,
    };

    setIsSaving(true);
    setSaveError(null);
    setShowImageErrors(false);

    try {
      const imagePayloads: UnitImageCreatePayload[] = imageDrafts.map(
        (draft: UnitImageDraft): UnitImageCreatePayload => ({
          kind: draft.kind,
          file: draft.file,
          url: draft.url,
          license: draft.imageLicense,
          source: draft.imageSource,
          license_note: draft.licenseNote,
        }),
      );
      let savedUnit: UnitReadResponse;

      if (unit === null && needsImage) {
        savedUnit = await createUnitWithImages(source.id, unitWriteRequest, imagePayloads);
      } else if (unit === null) {
        savedUnit = await createSourceUnit(source.id, unitWriteRequest);
      } else {
        savedUnit = await patchSourceUnit(source.id, unit.id, unitWriteRequest);
      }

      const message: string = unit === null ? "Created the unit." : "Saved the unit.";

      for (const draft of imageDrafts) {
        releaseUnitImageDraft(draft);
      }

      setImageDrafts([]);
      onSaved(savedUnit, message);
    } catch (caughtError: unknown) {
      setSaveError(caughtError);
    } finally {
      setIsSaving(false);
    }
  };

  const pageTitle: string = unit === null ? "New unit" : "Unit";
  const pageLede: string = (
    "The fields follow this source's theme. Preview shows the unit on that theme."
  );

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>{pageTitle}</h1>
          <p className="lede">
            {source === null ? "Album" : source.name}
            . {pageLede}
          </p>
        </div>
        <button type="button" onClick={onBack}>
          Back to units
        </button>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      <ErrorBanner error={themeError} />
      <ErrorBanner error={saveError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}
      {source === null ? (
        <p>Loading album…</p>
      ) : unit === null && !canWrite ? (
        <p>This unit is not available.</p>
      ) : !themeReady ? (
        <p>Loading theme…</p>
      ) : theme === null ? (
        <p>This theme is not available.</p>
      ) : (
        <div className="theme-editor-layout">
          <div className="theme-editor-main">
            {unit === null || !needsImage ? null : (
              <section id="unit-images" className="unit-images">
                <h2>Image</h2>
                <p className="field-hint">
                  This theme uses one image on the unit.
                </p>
                {unit.images.length === 0 ? <p>No image on this unit yet.</p> : null}
                {unit.images.map((image: UnitImageReadResponse): ReactElement => (
                  <ImageMetadataEditor
                    key={image.id}
                    sourceId={source.id}
                    unitId={unit.id}
                    image={image}
                    canWrite={canWrite}
                    onChanged={(message: string): void => {
                      onImagesChanged(message);
                    }}
                  />
                ))}
                {canWrite && unit.images.length === 0 ? (
                  <ImageIntakeForm
                    sourceId={source.id}
                    unitId={unit.id}
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
              {unit === null && needsImage ? (
                <NewUnitImages
                  drafts={imageDrafts}
                  showFieldErrors={showImageErrors}
                  onDraftsChange={setImageDrafts}
                />
              ) : null}
              <label>
                Name
                <input
                  id="unit-name"
                  value={unitName}
                  disabled={!canWrite}
                  onChange={(changeEvent): void => {
                    setUnitName(changeEvent.target.value);
                  }}
                />
              </label>
              <p className="field-hint">The id stays the same. The name is what you call this unit.</p>
              {unit === null ? null : (
                <p className="field-hint">Id {unit.id}</p>
              )}
              {textElements.map((element: ThemeElementReadResponse): ReactElement => (
                <label key={element.id}>
                  {labelForTextElement(element, textElements)}
                  <textarea
                    id={`unit-text-${element.id}`}
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
              {canWrite ? (
                <div className="button-row">
                  <button id="save-unit" type="submit" disabled={isSaving}>
                    {isSaving ? "Saving…" : "Save unit"}
                  </button>
                  {unit === null ? null : (
                    <button
                      type="button"
                      className="danger"
                      onClick={(): void => {
                        setPendingDelete(true);
                      }}
                    >
                      Delete unit
                    </button>
                  )}
                </div>
              ) : null}
            </form>
          </div>
          <UnitLivePreview
            sourceId={source.id}
            unitId={unit?.id ?? null}
            texts={textWrites}
          />
        </div>
      )}
      {pendingDelete && source !== null && unit !== null ? (
        <DeleteConfirmDialog
          headingId="delete-editor-unit-heading"
          title="Delete this unit?"
          body="Delete is blocked while a theme or an artifact still stores one of its images, and the unit stays."
          confirmLabel="Delete unit"
          onCancel={(): void => {
            setPendingDelete(false);
          }}
          onConfirm={async (): Promise<void> => {
            await deleteSourceUnit(source.id, unit.id);
            setPendingDelete(false);
            onUnitDeleted();
          }}
        />
      ) : null}
    </section>
  );
}

interface ImageIntakeFormProps {
  sourceId: string;
  unitId: string;
  onChanged: (message: string) => void;
}

function ImageIntakeForm({
  sourceId,
  unitId,
  onChanged,
}: ImageIntakeFormProps): ReactElement {

  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [previewUrls, setPreviewUrls] = useState<string[]>([]);
  const [uploadLicense, setUploadLicense] = useState<UnitImageLicense>("cc0");
  const [uploadSource, setUploadSource] = useState<string>("");
  const [uploadNote, setUploadNote] = useState<string>("");
  const [uploadAlt, setUploadAlt] = useState<string>("");
  const [uploadError, setUploadError] = useState<unknown>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [importUrl, setImportUrl] = useState<string>("");
  const [importLicense, setImportLicense] = useState<UnitImageLicense>("cc0");
  const [importSource, setImportSource] = useState<string>("");
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
      await uploadUnitImages(
        sourceId,
        unitId,
        selectedFiles,
        uploadLicense,
        uploadSource,
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

    const provenance: string = importSource.trim() === "" ? importUrl.trim() : importSource.trim();

    try {
      await importUnitImage(sourceId, unitId, {
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
              id="unit-image-files"
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
            <div id="unit-image-preview" className="pending-thumbs">
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
            licenseId="unit-image-license"
            sourceId="unit-image-source"
            noteId="unit-image-note"
            imageLicense={uploadLicense}
            imageSource={uploadSource}
            licenseNote={uploadNote}
            onLicenseChange={setUploadLicense}
            onSourceChange={setUploadSource}
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
            disabled={isUploading || selectedFiles.length === 0 || uploadSource.trim() === ""}
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

                if (importSource.trim() === "" || importSource === importUrl) {
                  setImportSource(nextUrl);
                }
              }}
            />
          </label>
          <p>The server downloads the file once. Source records the provenance, and defaults to that URL.</p>
          <LicenseFields
            licenseId="import-image-license"
            sourceId="import-image-source"
            noteId="import-image-note"
            imageLicense={importLicense}
            imageSource={importSource}
            licenseNote={importNote}
            onLicenseChange={setImportLicense}
            onSourceChange={setImportSource}
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
  imageLicense: UnitImageLicense;
  imageSource: string;
  licenseNote: string;
  onLicenseChange: (imageLicense: UnitImageLicense) => void;
  onSourceChange: (imageSource: string) => void;
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
  onSourceChange,
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
          id={sourceId}
          value={imageSource}
          onChange={(changeEvent): void => {
            onSourceChange(changeEvent.target.value);
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
  unitId: string;
  image: UnitImageReadResponse;
  canWrite: boolean;
  onChanged: (message: string) => void;
}

function ImageMetadataEditor({
  sourceId,
  unitId,
  image,
  canWrite,
  onChanged,
}: ImageMetadataEditorProps): ReactElement {

  const [altText, setAltText] = useState<string>(image.alt_text ?? "");
  const [imageLicense, setImageLicense] = useState<UnitImageLicense>(image.license);
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
      await patchUnitImageMetadata(sourceId, unitId, image.id, {
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
        src={unitImageDisplayUrl(sourceId, unitId, image)}
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
              setImageLicense(changeEvent.target.value as UnitImageLicense);
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
          body="Delete is blocked while a theme or an artifact stores this image, and the row stays. A unit also has to keep an image, free text, or a field."
          confirmLabel="Delete image"
          onCancel={(): void => {
            setPendingDelete(false);
          }}
          onConfirm={async (): Promise<void> => {
            await deleteUnitImage(sourceId, unitId, image.id);
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

function findUnit(
  source: SourceReadResponse | null,
  unitId: string | null,
): UnitReadResponse | null {

  if (source === null || unitId === null) {
    return null;
  }

  const foundUnit: UnitReadResponse | undefined = source.units.find(
    (unit: UnitReadResponse): boolean => unit.id === unitId,
  );

  return foundUnit ?? null;
}

function unitExcerpt(unit: UnitReadResponse): string {

  for (const elementText of unit.texts) {
    const trimmedValue: string = elementText.value.trim();

    if (trimmedValue !== "") {
      return trimmedValue;
    }
  }

  const firstImage: UnitImageReadResponse | undefined = unit.images[0];

  if (firstImage !== undefined) {
    return firstImage.relative_path;
  }

  return "Empty unit";
}
