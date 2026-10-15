import { useEffect, useState, type ReactElement } from "react";

import { fetchThemeFontFamilies } from "../api/client";
import type { ThemeFontFamiliesResponse } from "../api/types";
import {
  FONT_CATEGORIES,
  UNKNOWN_FONT_FAMILY_NOTE,
  filterFontFamilies,
  fontFamilyIsBundled,
  type FontCategory,
  type ThemeFontFamily,
} from "./themeFonts";

export interface ThemeFontFamilyFieldProps {
  fontFamily: string;
  onFontFamilyChange: (nextFontFamily: string) => void;
  idPrefix: string;
  compact?: boolean;
}

let familiesPromise: Promise<ThemeFontFamily[]> | null = null;

/**
 * Load the bundled catalog once. A failed request can be tried again.
 *
 * @returns Families from `GET /api/v1/themes/font-families`
 */
function loadThemeFontFamilies(): Promise<ThemeFontFamily[]> {

  if (familiesPromise !== null) {
    return familiesPromise;
  }

  const pendingFamilies: Promise<ThemeFontFamily[]> = fetchThemeFontFamilies()
    .then((response: ThemeFontFamiliesResponse): ThemeFontFamily[] => response.families)
    .catch((caughtError: unknown): never => {
      familiesPromise = null;

      throw caughtError;
    });
  familiesPromise = pendingFamilies;

  return pendingFamilies;
}

/**
 * Searchable font list. The options are the bundled files, not a free-text name.
 *
 * A stored family that is not in the catalog stays selected and shows a note.
 * The preview still renders, using the server fallback face.
 *
 * @param props - Stored family, change handler, and an id prefix
 * @returns The search box and the family list
 */
export function ThemeFontFamilyField({
  fontFamily,
  onFontFamilyChange,
  idPrefix,
  compact = false,
}: ThemeFontFamilyFieldProps): ReactElement {

  const [families, setFamilies] = useState<ThemeFontFamily[]>([]);
  const [query, setQuery] = useState<string>("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const searchId: string = `${idPrefix}-font-search`;
  const selectId: string = `${idPrefix}-font-family`;
  const filteredFamilies: ThemeFontFamily[] = filterFontFamilies(families, query);
  const trimmedFamily: string = fontFamily.trim();
  const catalogLoaded: boolean = families.length > 0;
  const familyIsKnown: boolean = !catalogLoaded || fontFamilyIsBundled(families, trimmedFamily);
  const showUnknownNote: boolean = catalogLoaded && trimmedFamily !== "" && !familyIsKnown;
  const currentFamily: ThemeFontFamily | undefined = families.find(
    (family: ThemeFontFamily): boolean => family.name === trimmedFamily,
  );
  const listedFamilies: ThemeFontFamily[] = currentFamily !== undefined
    && !filteredFamilies.some(
      (family: ThemeFontFamily): boolean => family.name === currentFamily.name,
    )
    ? [currentFamily, ...filteredFamilies]
    : filteredFamilies;
  const optionCount: number = listedFamilies.length + (showUnknownNote ? 1 : 0) + (
    !catalogLoaded && trimmedFamily !== "" ? 1 : 0
  );
  const listSize: number = Math.min(8, Math.max(optionCount, 1));

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    loadThemeFontFamilies()
      .then((loadedFamilies: ThemeFontFamily[]): void => {
        if (!isCancelled) {
          setFamilies(loadedFamilies);
          setLoadError(null);
        }
      })
      .catch((): void => {
        if (!isCancelled) {
          setLoadError("Font list could not be loaded.");
        }
      });

    return (): void => {
      isCancelled = true;
    };
  }, []);

  if (compact) {
    return (
      <label className="toolbar-field" htmlFor={selectId}>
        <span className="toolbar-caption">Font</span>
        <select
          id={selectId}
          className="toolbar-select"
          value={trimmedFamily}
          aria-label="Font family"
          title="Font family"
          onChange={(changeEvent): void => {
            onFontFamilyChange(changeEvent.target.value);
          }}
        >
          {showUnknownNote ? (
            <option value={trimmedFamily}>{trimmedFamily}</option>
          ) : null}
          {!catalogLoaded && trimmedFamily !== "" ? (
            <option value={trimmedFamily}>{trimmedFamily}</option>
          ) : null}
          {FONT_CATEGORIES.map((category: FontCategory): ReactElement | null => {
            const members: ThemeFontFamily[] = families.filter(
              (family: ThemeFontFamily): boolean => family.category === category.id,
            );

            if (members.length === 0) {
              return null;
            }

            return (
              <optgroup key={category.id} label={category.label}>
                {members.map((family: ThemeFontFamily): ReactElement => (
                  <option key={family.family_id} value={family.name}>
                    {family.name}
                  </option>
                ))}
              </optgroup>
            );
          })}
        </select>
      </label>
    );
  }

  return (
    <>
      <label htmlFor={searchId}>
        Font family
      </label>
      <input
        id={searchId}
        type="search"
        value={query}
        placeholder="Search fonts"
        aria-label="Search fonts"
        spellCheck={false}
        onChange={(changeEvent): void => {
          setQuery(changeEvent.target.value);
        }}
      />
      <select
        id={selectId}
        className="font-family-select"
        size={listSize}
        value={trimmedFamily}
        aria-label="Font family"
        onChange={(changeEvent): void => {
          onFontFamilyChange(changeEvent.target.value);
        }}
      >
        {showUnknownNote ? (
          <option value={trimmedFamily}>{trimmedFamily} (not bundled)</option>
        ) : null}
        {!catalogLoaded && trimmedFamily !== "" ? (
          <option value={trimmedFamily}>{trimmedFamily}</option>
        ) : null}
        {FONT_CATEGORIES.map((category: FontCategory): ReactElement | null => {
          const members: ThemeFontFamily[] = listedFamilies.filter(
            (family: ThemeFontFamily): boolean => family.category === category.id,
          );

          if (members.length === 0) {
            return null;
          }

          return (
            <optgroup key={category.id} label={category.label}>
              {members.map((family: ThemeFontFamily): ReactElement => (
                <option key={family.family_id} value={family.name}>
                  {family.name}
                </option>
              ))}
            </optgroup>
          );
        })}
      </select>
      {showUnknownNote ? (
        <p className="field-hint" id={`${idPrefix}-font-fallback`}>
          {UNKNOWN_FONT_FAMILY_NOTE}
        </p>
      ) : null}
      {loadError !== null ? (
        <p className="field-hint">{loadError}</p>
      ) : null}
    </>
  );
}
