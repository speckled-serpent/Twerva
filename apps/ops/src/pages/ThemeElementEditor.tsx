import { useEffect, useRef, useState, type FormEvent, type ReactElement } from "react";

import {
  createThemeElement,
  deleteThemeElement,
  fetchThemeById,
  patchThemeElement,
} from "../api/client";
import type {
  ThemeElementAlignment,
  ThemeElementBand,
  ThemeElementContentKind,
  ThemeElementCreateRequest,
  ThemeElementPatchRequest,
  ThemeElementReadResponse,
  ThemeElementTextSource,
  ThemeReadResponse,
} from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { useCanWriteOps } from "../session/OpsSessionContext";
import { ThemeAssetAlbumField } from "./ThemeAssetAlbumField";
import { ThemeFontFamilyField } from "./ThemeFontFamilyField";
import { normalizeHexColor } from "./themeColors";
import { DEFAULT_FONT_FAMILY } from "./themeFonts";

export interface ThemeElementEditorProps {
  theme: ThemeReadResponse;
  onThemeUpdated: (updatedTheme: ThemeReadResponse) => void;
  onLocalElementsChange?: (nextElements: ThemeElementReadResponse[]) => void;
  onPreviewElementsChange?: (
    elements: ThemeElementCreateRequest[] | null,
    draftError: string | null,
  ) => void;
}

interface TextSourceOption {
  value: ThemeElementTextSource;
  label: string;
}

interface BandOption {
  value: ThemeElementBand;
  label: string;
}

interface ElementDraft {
  band: ThemeElementBand;
  contentKind: ThemeElementContentKind;
  rectangleColor: string;
  rectangleOpacity: string;
  rectangleRadius: string;
  textSource: ThemeElementTextSource;
  fontFamily: string;
  fontSize: string;
  fontColor: string;
  bold: boolean;
  italic: boolean;
  underline: boolean;
  strikethrough: boolean;
  fontWeight: string;
  alignment: ThemeElementAlignment;
  imageAssetRef: string;
}

const TEXT_SOURCE_OPTIONS: TextSourceOption[] = [
  { value: "title", label: "Title" },
  { value: "interest_heading", label: "Interest heading" },
  { value: "overview_bullets", label: "Overview bullets" },
  { value: "canonical_url", label: "Public URL" },
];

const BAND_OPTIONS: BandOption[] = [
  { value: "top", label: "Top" },
  { value: "middle", label: "Middle" },
  { value: "bottom", label: "Bottom" },
];

/**
 * Add, edit, delete, reorder, and move theme elements. No placement fields.
 *
 * When `onLocalElementsChange` is set, edits stay in memory for Create Theme.
 *
 * @param props - The open theme and a callback after each saved change
 * @returns The element editor under the frame form
 */
export function ThemeElementEditor({
  theme,
  onThemeUpdated,
  onLocalElementsChange,
  onPreviewElementsChange,
}: ThemeElementEditorProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [addDraft, setAddDraft] = useState<ElementDraft>(emptyElementDraft());
  const [cardDrafts, setCardDrafts] = useState<Record<string, ElementDraft>>({});
  const [actionError, setActionError] = useState<unknown>(null);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const previewCallbackRef = useRef(onPreviewElementsChange);
  const lastPreviewKeyRef = useRef<string | null>(null);
  previewCallbackRef.current = onPreviewElementsChange;
  const fieldsDisabled: boolean = !canWrite || busyKey !== null;
  const isLocal: boolean = onLocalElementsChange !== undefined;

  const reloadTheme = async (): Promise<ThemeReadResponse> => {

    const reloadedTheme: ThemeReadResponse = await fetchThemeById(theme.id);

    onThemeUpdated(reloadedTheme);

    return reloadedTheme;
  };

  const publishLocalElements = (nextElements: ThemeElementReadResponse[]): void => {

    if (onLocalElementsChange === undefined) {
      return;
    }

    onLocalElementsChange(nextElements);
  };

  const handleAddElement = async (formEvent: FormEvent): Promise<void> => {

    formEvent.preventDefault();

    if (!canWrite) {
      return;
    }

    setBusyKey("add");
    setActionError(null);
    setStatusMessage("");

    try {
      const createRequest: ThemeElementCreateRequest = elementRequestFromDraft(addDraft);

      if (isLocal) {
        const createdElement: ThemeElementReadResponse = localElementFromRequest(
          theme.id,
          theme.elements,
          createRequest,
        );

        publishLocalElements([...theme.elements, createdElement]);
        setAddDraft(emptyElementDraft());
        setStatusMessage("Element added. It is stored when you create the theme.");
      } else {
        await createThemeElement(theme.id, createRequest);
        await reloadTheme();
        setAddDraft(emptyElementDraft());
        setStatusMessage("Element added.");
      }
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setBusyKey(null);
    }
  };

  const handleLocalSave = (elementId: string, draft: ElementDraft): void => {

    const currentElement: ThemeElementReadResponse | undefined = theme.elements.find(
      (element: ThemeElementReadResponse): boolean => element.id === elementId,
    );

    if (currentElement === undefined) {
      return;
    }

    const request: ThemeElementCreateRequest = elementRequestFromDraft(draft);
    const updatedElement: ThemeElementReadResponse = applyRequestToElement(
      currentElement,
      request,
    );

    publishLocalElements(
      placeSavedLocalElement(theme.elements, currentElement, updatedElement),
    );
  };

  const handleLocalDelete = (elementId: string): void => {

    publishLocalElements(deleteLocalElement(theme.elements, elementId));
  };

  const handleLocalMove = (elementId: string, nextSortOrder: number): void => {

    publishLocalElements(moveLocalElement(theme.elements, elementId, nextSortOrder));
  };

  const handleCardDraftChange = (elementId: string, draft: ElementDraft): void => {

    setCardDrafts((currentDrafts: Record<string, ElementDraft>): Record<string, ElementDraft> => {
      const previousDraft: ElementDraft | undefined = currentDrafts[elementId];

      if (previousDraft !== undefined && JSON.stringify(previousDraft) === JSON.stringify(draft)) {
        return currentDrafts;
      }

      return { ...currentDrafts, [elementId]: draft };
    });
  };

  useEffect((): void => {
    const previewCallback = previewCallbackRef.current;

    if (previewCallback === undefined) {
      return;
    }

    try {
      const requests: ThemeElementCreateRequest[] = previewRequestsFromElements(
        theme.elements,
        cardDrafts,
      );
      const previewKey: string = `${theme.id}:${JSON.stringify(requests)}`;

      if (previewKey === lastPreviewKeyRef.current) {
        return;
      }

      lastPreviewKeyRef.current = previewKey;
      previewCallback(requests, null);
    } catch (caughtError: unknown) {
      const message: string = caughtError instanceof Error
        ? caughtError.message
        : String(caughtError);
      const previewKey: string = `${theme.id}:error:${message}`;

      if (previewKey === lastPreviewKeyRef.current) {
        return;
      }

      lastPreviewKeyRef.current = previewKey;
      previewCallback(null, message);
    }
  }, [theme.id, theme.elements, cardDrafts]);

  return (
    <section className="summary-block">
      <h2>Elements</h2>
      <p className="field-hint">
        Full-width rows in Top, Middle, or Bottom. A blank rectangle color is clear.
        Image paths are typed, not uploaded.
      </p>
      <ErrorBanner error={actionError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}

      <form
        className="stack-form"
        onSubmit={(formEvent: FormEvent): void => {
          void handleAddElement(formEvent);
        }}
      >
        <fieldset className="form-fieldset" disabled={fieldsDisabled}>
          <legend>Add element</legend>
          <ElementFields
            draft={addDraft}
            onDraftChange={setAddDraft}
            idPrefix="add-element"
          />
        </fieldset>
        <div className="button-row">
          <button type="submit" disabled={fieldsDisabled}>
            {busyKey === "add" ? "Adding…" : "Add element"}
          </button>
        </div>
      </form>

      {BAND_OPTIONS.map((bandOption: BandOption): ReactElement => {
        const bandElements: ThemeElementReadResponse[] = elementsInBand(
          theme.elements,
          bandOption.value,
        );

        return (
          <div key={bandOption.value}>
            <h3>{bandOption.label}</h3>
            {bandElements.length === 0 ? (
              <p className="empty-hint">No elements in this band.</p>
            ) : (
              bandElements.map(
                (element: ThemeElementReadResponse, elementIndex: number): ReactElement => (
                  <ThemeElementCard
                    key={`${element.id}:${element.updated_at}:${element.band}:${element.sort_order}`}
                    themeId={theme.id}
                    element={element}
                    elementIndex={elementIndex}
                    bandLength={bandElements.length}
                    fieldsDisabled={fieldsDisabled}
                    isBusy={busyKey === element.id}
                    onError={setActionError}
                    onReload={async (message: string): Promise<void> => {
                      setStatusMessage(message);

                      if (!isLocal) {
                        await reloadTheme();
                      }
                    }}
                    onBusy={(isBusy: boolean): void => {
                      setBusyKey(isBusy ? element.id : null);
                    }}
                    onLocalSave={isLocal ? handleLocalSave : undefined}
                    onLocalDelete={isLocal ? handleLocalDelete : undefined}
                    onLocalMove={isLocal ? handleLocalMove : undefined}
                    onDraftChange={handleCardDraftChange}
                  />
                ),
              )
            )}
          </div>
        );
      })}
    </section>
  );
}

interface ThemeElementCardProps {
  themeId: string;
  element: ThemeElementReadResponse;
  elementIndex: number;
  bandLength: number;
  fieldsDisabled: boolean;
  isBusy: boolean;
  onError: (error: unknown) => void;
  onReload: (message: string) => Promise<void>;
  onBusy: (isBusy: boolean) => void;
  onLocalSave?: (elementId: string, draft: ElementDraft) => void;
  onLocalDelete?: (elementId: string) => void;
  onLocalMove?: (elementId: string, nextSortOrder: number) => void;
  onDraftChange: (elementId: string, draft: ElementDraft) => void;
}

function ThemeElementCard({
  themeId,
  element,
  elementIndex,
  bandLength,
  fieldsDisabled,
  isBusy,
  onError,
  onReload,
  onBusy,
  onLocalSave,
  onLocalDelete,
  onLocalMove,
  onDraftChange,
}: ThemeElementCardProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [draft, setDraft] = useState<ElementDraft>(draftFromElement(element));

  useEffect((): void => {
    onDraftChange(element.id, draft);
  }, [draft, element.id, onDraftChange]);
  const canMoveEarlier: boolean = canWrite && elementIndex > 0 && draft.band === element.band;
  const canMoveLater: boolean = (
    canWrite
    && elementIndex < bandLength - 1
    && draft.band === element.band
  );

  const handleSave = async (formEvent: FormEvent): Promise<void> => {

    formEvent.preventDefault();

    if (!canWrite) {
      return;
    }

    onBusy(true);
    onError(null);

    try {
      if (onLocalSave !== undefined) {
        onLocalSave(element.id, draft);
        await onReload("Element updated. It is stored when you create the theme.");

        return;
      }

      const patchRequest: ThemeElementPatchRequest = elementRequestFromDraft(draft);
      await patchThemeElement(themeId, element.id, patchRequest);
      await onReload("Element saved.");
    } catch (caughtError: unknown) {
      onError(caughtError);
    } finally {
      onBusy(false);
    }
  };

  const handleDelete = async (): Promise<void> => {

    if (!canWrite) {
      return;
    }

    onBusy(true);
    onError(null);

    try {
      if (onLocalDelete !== undefined) {
        onLocalDelete(element.id);
        await onReload("Element removed. It is stored when you create the theme.");

        return;
      }

      await deleteThemeElement(themeId, element.id);
      await onReload("Element deleted.");
    } catch (caughtError: unknown) {
      onError(caughtError);
    } finally {
      onBusy(false);
    }
  };

  const handleMove = async (nextSortOrder: number): Promise<void> => {

    if (!canWrite) {
      return;
    }

    onBusy(true);
    onError(null);

    try {
      if (onLocalMove !== undefined) {
        onLocalMove(element.id, nextSortOrder);
        await onReload("Element moved. It is stored when you create the theme.");

        return;
      }

      await patchThemeElement(themeId, element.id, { sort_order: nextSortOrder });
      await onReload("Element moved.");
    } catch (caughtError: unknown) {
      onError(caughtError);
    } finally {
      onBusy(false);
    }
  };

  return (
    <form
      className="card stack-form"
      onSubmit={(formEvent: FormEvent): void => {
        void handleSave(formEvent);
      }}
    >
      <fieldset className="form-fieldset" disabled={fieldsDisabled}>
        <legend>
          {bandLabel(element.band)} {elementIndex + 1} of {bandLength}
          {" · "}
          {element.content_kind === "text" ? "Text" : "Image"}
        </legend>
        <ElementFields
          draft={draft}
          onDraftChange={setDraft}
          idPrefix={`element-${element.id}`}
        />
      </fieldset>
      <div className="button-row">
        <button type="submit" disabled={fieldsDisabled}>
          {isBusy ? "Saving…" : "Save element"}
        </button>
        <button
          type="button"
          disabled={!canMoveEarlier || fieldsDisabled}
          onClick={(): void => {
            void handleMove(element.sort_order - 1);
          }}
        >
          Move earlier
        </button>
        <button
          type="button"
          disabled={!canMoveLater || fieldsDisabled}
          onClick={(): void => {
            void handleMove(element.sort_order + 1);
          }}
        >
          Move later
        </button>
        <button
          type="button"
          className="danger"
          disabled={fieldsDisabled}
          onClick={(): void => {
            void handleDelete();
          }}
        >
          Delete element
        </button>
      </div>
    </form>
  );
}

interface ElementFieldsProps {
  draft: ElementDraft;
  onDraftChange: (nextDraft: ElementDraft) => void;
  idPrefix: string;
}

function ElementFields({
  draft,
  onDraftChange,
  idPrefix,
}: ElementFieldsProps): ReactElement {

  return (
    <>
      <label>
        Band
        <select
          value={draft.band}
          onChange={(changeEvent): void => {
            const nextBand: string = changeEvent.target.value;

            if (!isThemeElementBand(nextBand)) {
              return;
            }

            onDraftChange({ ...draft, band: nextBand });
          }}
        >
          {BAND_OPTIONS.map((bandOption: BandOption): ReactElement => (
            <option key={bandOption.value} value={bandOption.value}>
              {bandOption.label}
            </option>
          ))}
        </select>
      </label>
      <label>
        Content
        <select
          value={draft.contentKind}
          onChange={(changeEvent): void => {
            const nextKind: string = changeEvent.target.value;

            if (!isContentKind(nextKind)) {
              return;
            }

            onDraftChange({ ...draft, contentKind: nextKind });
          }}
        >
          <option value="text">Text</option>
          <option value="image">Image</option>
        </select>
      </label>
      <label>
        Rectangle color
        <input
          value={draft.rectangleColor}
          onChange={(changeEvent): void => {
            onDraftChange({ ...draft, rectangleColor: changeEvent.target.value });
          }}
          onBlur={(blurEvent): void => {
            onDraftChange({
              ...draft,
              rectangleColor: normalizeHexColor(blurEvent.currentTarget.value),
            });
          }}
          placeholder="#AABBCC"
          spellCheck={false}
        />
      </label>
      <p className="field-hint">Blank means a clear rectangle.</p>
      <RectangleStyleFields draft={draft} onDraftChange={onDraftChange} />
      {draft.contentKind === "text" ? (
        <TextElementFields
          draft={draft}
          onDraftChange={onDraftChange}
          idPrefix={idPrefix}
        />
      ) : (
        <ThemeAssetAlbumField
          label="Image"
          assetRef={draft.imageAssetRef}
          disabled={false}
          onAssetRefChange={(nextAssetRef: string): void => {
            onDraftChange({ ...draft, imageAssetRef: nextAssetRef });
          }}
        />
      )}
    </>
  );
}

interface TextElementFieldsProps {
  draft: ElementDraft;
  onDraftChange: (nextDraft: ElementDraft) => void;
  idPrefix: string;
}

function TextElementFields({
  draft,
  onDraftChange,
  idPrefix,
}: TextElementFieldsProps): ReactElement {

  const sourceSelectId: string = `${idPrefix}-text-source`;

  return (
    <>
      <label htmlFor={sourceSelectId}>
        Text source
      </label>
      <select
        id={sourceSelectId}
        value={draft.textSource}
        onChange={(changeEvent): void => {
          const nextSource: string = changeEvent.target.value;

          if (!isTextSource(nextSource)) {
            return;
          }

          onDraftChange({ ...draft, textSource: nextSource });
        }}
      >
        {TEXT_SOURCE_OPTIONS.map((sourceOption: TextSourceOption): ReactElement => (
          <option key={sourceOption.value} value={sourceOption.value}>
            {sourceOption.label}
          </option>
        ))}
      </select>
      <ThemeFontFamilyField
        fontFamily={draft.fontFamily}
        idPrefix={idPrefix}
        onFontFamilyChange={(nextFontFamily: string): void => {
          onDraftChange({ ...draft, fontFamily: nextFontFamily });
        }}
      />
      <label>
        Font size
        <input
          type="number"
          min={1}
          step={1}
          value={draft.fontSize}
          onChange={(changeEvent): void => {
            onDraftChange({ ...draft, fontSize: changeEvent.target.value });
          }}
        />
      </label>
      <label>
        Font color
        <input
          value={draft.fontColor}
          onChange={(changeEvent): void => {
            onDraftChange({ ...draft, fontColor: changeEvent.target.value });
          }}
          onBlur={(blurEvent): void => {
            onDraftChange({
              ...draft,
              fontColor: normalizeHexColor(blurEvent.currentTarget.value),
            });
          }}
          placeholder="#112233"
          spellCheck={false}
        />
      </label>
      <label>
        Alignment
        <select
          value={draft.alignment}
          onChange={(changeEvent): void => {
            const nextAlignment: string = changeEvent.target.value;

            if (!isAlignment(nextAlignment)) {
              return;
            }

            onDraftChange({ ...draft, alignment: nextAlignment });
          }}
        >
          <option value="left">Left</option>
          <option value="center">Center</option>
          <option value="right">Right</option>
        </select>
      </label>
      <label>
        Font weight
        <input
          type="number"
          min={1}
          max={1000}
          step={1}
          value={draft.fontWeight}
          onChange={(changeEvent): void => {
            onDraftChange({ ...draft, fontWeight: changeEvent.target.value });
          }}
          placeholder="Optional"
        />
      </label>
      <p className="field-hint">Optional. Blank stores no weight. 1 through 1000.</p>
      <label>
        <input
          type="checkbox"
          checked={draft.bold}
          onChange={(changeEvent): void => {
            onDraftChange({ ...draft, bold: changeEvent.target.checked });
          }}
        />
        Bold
      </label>
      <label>
        <input
          type="checkbox"
          checked={draft.italic}
          onChange={(changeEvent): void => {
            onDraftChange({ ...draft, italic: changeEvent.target.checked });
          }}
        />
        Italic
      </label>
      <label>
        <input
          type="checkbox"
          checked={draft.underline}
          onChange={(changeEvent): void => {
            onDraftChange({ ...draft, underline: changeEvent.target.checked });
          }}
        />
        Underline
      </label>
      <label>
        <input
          type="checkbox"
          checked={draft.strikethrough}
          onChange={(changeEvent): void => {
            onDraftChange({ ...draft, strikethrough: changeEvent.target.checked });
          }}
        />
        Strikethrough
      </label>
    </>
  );
}

function emptyElementDraft(): ElementDraft {

  const draft: ElementDraft = {
    band: "top",
    contentKind: "text",
    rectangleColor: "",
    rectangleOpacity: "100",
    rectangleRadius: "0",
    textSource: "title",
    fontFamily: DEFAULT_FONT_FAMILY,
    fontSize: "32",
    fontColor: "#112233",
    bold: false,
    italic: false,
    underline: false,
    strikethrough: false,
    fontWeight: "",
    alignment: "left",
    imageAssetRef: "",
  };

  return draft;
}

function draftFromElement(element: ThemeElementReadResponse): ElementDraft {

  const draft: ElementDraft = {
    band: element.band,
    contentKind: element.content_kind,
    rectangleColor: element.rectangle_color ?? "",
    rectangleOpacity: String(element.rectangle_opacity),
    rectangleRadius: String(element.rectangle_radius),
    textSource: element.text_source ?? "title",
    fontFamily: element.font_family ?? "",
    fontSize: element.font_size === null ? "" : String(element.font_size),
    fontColor: element.font_color ?? "",
    bold: element.bold,
    italic: element.italic,
    underline: element.underline,
    strikethrough: element.strikethrough,
    fontWeight: element.font_weight === null ? "" : String(element.font_weight),
    alignment: element.alignment ?? "left",
    imageAssetRef: element.image_asset_ref ?? "",
  };

  return draft;
}

/**
 * Build the create-body element from a staged row. Sort order is omitted
 * so the server appends; callers send rows in band order.
 *
 * @param element - Staged element from the create form
 * @returns The element payload for POST /api/v1/themes
 */
export function themeElementCreateRequestFromElement(
  element: ThemeElementReadResponse,
): ThemeElementCreateRequest {

  const request: ThemeElementCreateRequest = elementRequestFromDraft(
    draftFromElement(element),
  );

  return request;
}

/**
 * Return create payloads in Top, Middle, Bottom order.
 *
 * Each payload omits sort_order so the server appends and keeps this order.
 *
 * @param elements - Staged elements on the create form
 * @returns Element bodies for one theme create
 */
export function themeElementCreateRequestsInBandOrder(
  elements: ThemeElementReadResponse[],
): ThemeElementCreateRequest[] {

  const bandRank: Record<ThemeElementBand, number> = {
    top: 0,
    middle: 1,
    bottom: 2,
  };
  const orderedElements: ThemeElementReadResponse[] = [...elements].sort(
    (left: ThemeElementReadResponse, right: ThemeElementReadResponse): number => {

      if (left.band !== right.band) {
        return bandRank[left.band] - bandRank[right.band];
      }

      return left.sort_order - right.sort_order;
    },
  );
  const requests: ThemeElementCreateRequest[] = orderedElements.map(
    (element: ThemeElementReadResponse): ThemeElementCreateRequest => {

      return themeElementCreateRequestFromElement(element);
    },
  );

  return requests;
}

export interface ThemePreviewElementState {
  elements: ThemeElementCreateRequest[] | null;
  draftError: string | null;
}

/**
 * Build the preview payload for elements that are already on the theme.
 *
 * Card drafts are not included. A bad font size returns the message and
 * no element list, which is the same result the editor effect reports.
 *
 * @param elements - Saved or staged elements
 * @returns Element bodies for one preview, or a client draft error
 */
export function previewElementStateFromElements(
  elements: ThemeElementReadResponse[],
): ThemePreviewElementState {

  try {
    const requests: ThemeElementCreateRequest[] = previewRequestsFromElements(elements, {});
    const previewState: ThemePreviewElementState = {
      elements: requests,
      draftError: null,
    };

    return previewState;
  } catch (caughtError: unknown) {
    const message: string = caughtError instanceof Error
      ? caughtError.message
      : String(caughtError);
    const previewState: ThemePreviewElementState = {
      elements: null,
      draftError: message,
    };

    return previewState;
  }
}

function previewRequestsFromElements(
  elements: ThemeElementReadResponse[],
  cardDrafts: Record<string, ElementDraft>,
): ThemeElementCreateRequest[] {

  const bandOrder: ThemeElementBand[] = ["top", "middle", "bottom"];
  const requests: ThemeElementCreateRequest[] = [];

  bandOrder.forEach((band: ThemeElementBand): void => {
    const members: ThemeElementReadResponse[] = elements.filter(
      (element: ThemeElementReadResponse): boolean => {
        const draft: ElementDraft = cardDrafts[element.id] ?? draftFromElement(element);

        return draft.band === band;
      },
    );
    const stayed: ThemeElementReadResponse[] = members
      .filter((element: ThemeElementReadResponse): boolean => element.band === band)
      .sort(
        (left: ThemeElementReadResponse, right: ThemeElementReadResponse): number => {

          return left.sort_order - right.sort_order;
        },
      );
    const moved: ThemeElementReadResponse[] = members.filter(
      (element: ThemeElementReadResponse): boolean => element.band !== band,
    );
    const orderedMembers: ThemeElementReadResponse[] = [...stayed, ...moved];

    orderedMembers.forEach((element: ThemeElementReadResponse, index: number): void => {
      const draft: ElementDraft = cardDrafts[element.id] ?? draftFromElement(element);
      const request: ThemeElementCreateRequest = elementRequestFromDraft(draft);
      request.sort_order = index;
      requests.push(request);
    });
  });

  return requests;
}

function elementRequestFromDraft(
  draft: ElementDraft,
): ThemeElementCreateRequest {

  const fontWeight: number | null = parseOptionalFontWeight(draft.fontWeight);
  const request: ThemeElementCreateRequest = {
    band: draft.band,
    content_kind: draft.contentKind,
    rectangle_color: normalizeHexColor(draft.rectangleColor),
    rectangle_opacity: parseRectangleOpacity(draft.rectangleOpacity),
    rectangle_radius: parseRectangleRadius(draft.rectangleRadius),
    bold: draft.bold,
    italic: draft.italic,
    underline: draft.underline,
    strikethrough: draft.strikethrough,
    font_weight: fontWeight,
  };

  if (draft.contentKind === "text") {
    request.text_source = draft.textSource;
    request.font_family = draft.fontFamily.trim();
    request.font_size = parseRequiredFontSize(draft.fontSize);
    request.font_color = normalizeHexColor(draft.fontColor);
    request.alignment = draft.alignment;
    request.image_asset_ref = null;

    return request;
  }

  request.text_source = null;
  request.image_asset_ref = draft.imageAssetRef.trim();

  return request;
}

const RECTANGLE_OPACITY_MAX: number = 100;
const RECTANGLE_RADIUS_SLIDER_MAX: number = 540;
const RECTANGLE_RADIUS_MAX: number = 10000;

function RectangleStyleFields({
  draft,
  onDraftChange,
}: {
  draft: ElementDraft;
  onDraftChange: (nextDraft: ElementDraft) => void;
}): ReactElement {

  const opacityNumber: number = Number(draft.rectangleOpacity);
  const radiusNumber: number = Number(draft.rectangleRadius);
  const sliderOpacity: number = Number.isFinite(opacityNumber)
    ? Math.min(RECTANGLE_OPACITY_MAX, Math.max(0, opacityNumber))
    : RECTANGLE_OPACITY_MAX;
  const sliderRadius: number = Number.isFinite(radiusNumber)
    ? Math.min(RECTANGLE_RADIUS_SLIDER_MAX, Math.max(0, radiusNumber))
    : 0;

  return (
    <>
      <div className="slider-field">
        <label className="slider-number-label">
          Rectangle opacity
          <input
            className="slider-number"
            type="number"
            min={0}
            max={RECTANGLE_OPACITY_MAX}
            step={1}
            value={draft.rectangleOpacity}
            aria-label="Rectangle opacity percent"
            onChange={(changeEvent): void => {
              onDraftChange({ ...draft, rectangleOpacity: changeEvent.target.value });
            }}
          />
        </label>
        <input
          className="slider-range"
          type="range"
          min={0}
          max={RECTANGLE_OPACITY_MAX}
          step={1}
          value={sliderOpacity}
          aria-label="Rectangle opacity"
          onChange={(changeEvent): void => {
            onDraftChange({ ...draft, rectangleOpacity: changeEvent.target.value });
          }}
        />
      </div>
      <p className="field-hint">0% is clear. 100% is solid. A blank color still draws nothing.</p>
      <div className="slider-field">
        <label className="slider-number-label">
          Corner radius
          <input
            className="slider-number"
            type="number"
            min={0}
            max={RECTANGLE_RADIUS_MAX}
            step={1}
            value={draft.rectangleRadius}
            aria-label="Rectangle corner radius pixels"
            onChange={(changeEvent): void => {
              onDraftChange({ ...draft, rectangleRadius: changeEvent.target.value });
            }}
          />
        </label>
        <input
          className="slider-range"
          type="range"
          min={0}
          max={RECTANGLE_RADIUS_SLIDER_MAX}
          step={1}
          value={sliderRadius}
          aria-label="Rectangle corner radius"
          onChange={(changeEvent): void => {
            onDraftChange({ ...draft, rectangleRadius: changeEvent.target.value });
          }}
        />
      </div>
      <p className="field-hint">
        Pixels. The preview clamps this to half the shorter side of the box.
      </p>
    </>
  );
}

function parseRectangleOpacity(rawValue: string): number {

  const trimmedValue: string = rawValue.trim();

  if (trimmedValue === "") {
    return 100;
  }

  if (!/^\d+$/.test(trimmedValue)) {
    throw new Error("rectangle_opacity must be an integer from 0 through 100.");
  }

  const opacity: number = Number(trimmedValue);

  if (opacity > RECTANGLE_OPACITY_MAX) {
    throw new Error("rectangle_opacity must be an integer from 0 through 100.");
  }

  return opacity;
}

function parseRectangleRadius(rawValue: string): number {

  const trimmedValue: string = rawValue.trim();

  if (trimmedValue === "") {
    return 0;
  }

  if (!/^\d+$/.test(trimmedValue)) {
    throw new Error("rectangle_radius must be an integer from 0 through 10000.");
  }

  const radius: number = Number(trimmedValue);

  if (radius > RECTANGLE_RADIUS_MAX) {
    throw new Error("rectangle_radius must be an integer from 0 through 10000.");
  }

  return radius;
}

function parseRequiredFontSize(rawValue: string): number {

  const trimmedValue: string = rawValue.trim();

  if (!/^\d+$/.test(trimmedValue)) {
    throw new Error("font_size must be a positive integer.");
  }

  const fontSize: number = Number(trimmedValue);

  if (fontSize < 1) {
    throw new Error("font_size must be a positive integer.");
  }

  return fontSize;
}

function parseOptionalFontWeight(rawValue: string): number | null {

  const trimmedValue: string = rawValue.trim();

  if (trimmedValue === "") {
    return null;
  }

  if (!/^\d+$/.test(trimmedValue)) {
    throw new Error("font_weight must be from 1 through 1000.");
  }

  const fontWeight: number = Number(trimmedValue);

  return fontWeight;
}

function elementsInBand(
  elements: ThemeElementReadResponse[],
  band: ThemeElementBand,
): ThemeElementReadResponse[] {

  const members: ThemeElementReadResponse[] = elements.filter(
    (element: ThemeElementReadResponse): boolean => element.band === band,
  );
  const orderedMembers: ThemeElementReadResponse[] = [...members].sort(
    (left: ThemeElementReadResponse, right: ThemeElementReadResponse): number => {

      return left.sort_order - right.sort_order;
    },
  );

  return orderedMembers;
}

function bandLabel(band: ThemeElementBand): string {

  const matchingOption: BandOption | undefined = BAND_OPTIONS.find(
    (bandOption: BandOption): boolean => bandOption.value === band,
  );

  if (matchingOption === undefined) {
    return band;
  }

  return matchingOption.label;
}

function isThemeElementBand(value: string): value is ThemeElementBand {

  return value === "top" || value === "middle" || value === "bottom";
}

function isContentKind(value: string): value is ThemeElementContentKind {

  return value === "text" || value === "image";
}

function isTextSource(value: string): value is ThemeElementTextSource {

  return TEXT_SOURCE_OPTIONS.some(
    (sourceOption: TextSourceOption): boolean => sourceOption.value === value,
  );
}

function isAlignment(value: string): value is ThemeElementAlignment {

  return value === "left" || value === "center" || value === "right";
}

function localElementFromRequest(
  themeId: string,
  existingElements: ThemeElementReadResponse[],
  request: ThemeElementCreateRequest,
): ThemeElementReadResponse {

  const bandCount: number = existingElements.filter(
    (element: ThemeElementReadResponse): boolean => element.band === request.band,
  ).length;
  const now: string = new Date().toISOString();
  const createdElement: ThemeElementReadResponse = {
    id: crypto.randomUUID(),
    theme_id: themeId,
    band: request.band,
    sort_order: bandCount,
    content_kind: request.content_kind,
    rectangle_color: emptyToNull(request.rectangle_color),
    rectangle_opacity: request.rectangle_opacity ?? 100,
    rectangle_radius: request.rectangle_radius ?? 0,
    text_source: request.content_kind === "text" ? request.text_source ?? null : null,
    font_family: request.content_kind === "text" ? request.font_family ?? null : null,
    font_size: request.content_kind === "text" ? request.font_size ?? null : null,
    font_color: request.content_kind === "text" ? request.font_color ?? null : null,
    bold: request.bold ?? false,
    italic: request.italic ?? false,
    underline: request.underline ?? false,
    strikethrough: request.strikethrough ?? false,
    font_weight: request.font_weight ?? null,
    alignment: request.content_kind === "text" ? request.alignment ?? null : null,
    image_asset_ref: request.content_kind === "image"
      ? request.image_asset_ref ?? null
      : null,
    created_at: now,
    updated_at: now,
  };

  return createdElement;
}

function applyRequestToElement(
  element: ThemeElementReadResponse,
  request: ThemeElementCreateRequest,
): ThemeElementReadResponse {

  const updatedElement: ThemeElementReadResponse = {
    ...element,
    band: request.band,
    content_kind: request.content_kind,
    rectangle_color: emptyToNull(request.rectangle_color),
    rectangle_opacity: request.rectangle_opacity ?? 100,
    rectangle_radius: request.rectangle_radius ?? 0,
    text_source: request.content_kind === "text" ? request.text_source ?? null : null,
    font_family: request.content_kind === "text" ? request.font_family ?? null : null,
    font_size: request.content_kind === "text" ? request.font_size ?? null : null,
    font_color: request.content_kind === "text" ? request.font_color ?? null : null,
    bold: request.bold ?? false,
    italic: request.italic ?? false,
    underline: request.underline ?? false,
    strikethrough: request.strikethrough ?? false,
    font_weight: request.font_weight ?? null,
    alignment: request.content_kind === "text" ? request.alignment ?? null : null,
    image_asset_ref: request.content_kind === "image"
      ? request.image_asset_ref ?? null
      : null,
    updated_at: new Date().toISOString(),
  };

  return updatedElement;
}

function placeSavedLocalElement(
  elements: ThemeElementReadResponse[],
  previous: ThemeElementReadResponse,
  updated: ThemeElementReadResponse,
): ThemeElementReadResponse[] {

  if (updated.band === previous.band) {
    const sameBand: ThemeElementReadResponse[] = elements.map(
      (element: ThemeElementReadResponse): ThemeElementReadResponse => {

        if (element.id !== updated.id) {
          return element;
        }

        return { ...updated, sort_order: previous.sort_order };
      },
    );

    return sameBand;
  }

  const withoutMoved: ThemeElementReadResponse[] = elements.filter(
    (element: ThemeElementReadResponse): boolean => element.id !== previous.id,
  );
  const compacted: ThemeElementReadResponse[] = compactBand(withoutMoved, previous.band);
  const destinationLength: number = compacted.filter(
    (element: ThemeElementReadResponse): boolean => element.band === updated.band,
  ).length;
  const movedElement: ThemeElementReadResponse = {
    ...updated,
    sort_order: destinationLength,
  };

  return [...compacted, movedElement];
}

function deleteLocalElement(
  elements: ThemeElementReadResponse[],
  elementId: string,
): ThemeElementReadResponse[] {

  const target: ThemeElementReadResponse | undefined = elements.find(
    (element: ThemeElementReadResponse): boolean => element.id === elementId,
  );

  if (target === undefined) {
    return elements;
  }

  const withoutTarget: ThemeElementReadResponse[] = elements.filter(
    (element: ThemeElementReadResponse): boolean => element.id !== elementId,
  );

  return compactBand(withoutTarget, target.band);
}

function moveLocalElement(
  elements: ThemeElementReadResponse[],
  elementId: string,
  requestedSortOrder: number,
): ThemeElementReadResponse[] {

  const target: ThemeElementReadResponse | undefined = elements.find(
    (element: ThemeElementReadResponse): boolean => element.id === elementId,
  );

  if (target === undefined) {
    return elements;
  }

  const others: ThemeElementReadResponse[] = elements.filter(
    (element: ThemeElementReadResponse): boolean => element.id !== elementId,
  );
  const targetMembers: ThemeElementReadResponse[] = others
    .filter((element: ThemeElementReadResponse): boolean => element.band === target.band)
    .sort(
      (left: ThemeElementReadResponse, right: ThemeElementReadResponse): number => {

        return left.sort_order - right.sort_order;
      },
    );
  const targetIndex: number = requestedSortOrder > targetMembers.length
    ? targetMembers.length
    : requestedSortOrder;
  const placedMembers: ThemeElementReadResponse[] = [...targetMembers];

  placedMembers.splice(targetIndex, 0, target);

  const movedAt: string = new Date().toISOString();
  const compactedMembers: ThemeElementReadResponse[] = placedMembers.map(
    (member: ThemeElementReadResponse, index: number): ThemeElementReadResponse => {

      return {
        ...member,
        sort_order: index,
        updated_at: member.id === elementId ? movedAt : member.updated_at,
      };
    },
  );
  const rest: ThemeElementReadResponse[] = others.filter(
    (element: ThemeElementReadResponse): boolean => element.band !== target.band,
  );

  return [...rest, ...compactedMembers];
}

function compactBand(
  elements: ThemeElementReadResponse[],
  band: ThemeElementBand,
): ThemeElementReadResponse[] {

  const members: ThemeElementReadResponse[] = elements
    .filter((element: ThemeElementReadResponse): boolean => element.band === band)
    .sort(
      (left: ThemeElementReadResponse, right: ThemeElementReadResponse): number => {

        return left.sort_order - right.sort_order;
      },
    );
  const orderById: Map<string, number> = new Map(
    members.map(
      (element: ThemeElementReadResponse, index: number): [string, number] => {

        return [element.id, index];
      },
    ),
  );
  const compacted: ThemeElementReadResponse[] = elements.map(
    (element: ThemeElementReadResponse): ThemeElementReadResponse => {

      const nextOrder: number | undefined = orderById.get(element.id);

      if (nextOrder === undefined) {
        return element;
      }

      return { ...element, sort_order: nextOrder };
    },
  );

  return compacted;
}

function emptyToNull(value: string | null | undefined): string | null {

  if (value === undefined || value === null || value.trim() === "") {
    return null;
  }

  return value;
}
