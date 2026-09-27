import { useEffect, useState, type ReactElement } from "react";

import { fetchThemeById, listThemes } from "../api/client";
import type { ThemeReadResponse } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import {
  advertisementTypeLabel,
  formatThemeTemplateKey,
  formatThemeTimestamp,
} from "./themeDisplay";

export interface ThemesPageProps {
  statusMessage: string;
}

/**
 * Themes tab: list saved themes. Selecting a row opens a basic detail view.
 *
 * @param props - Banner shown after create
 * @returns The Themes list or detail
 */
export function ThemesPage({ statusMessage }: ThemesPageProps): ReactElement {

  const [themes, setThemes] = useState<ThemeReadResponse[]>([]);
  const [openedThemeId, setOpenedThemeId] = useState<string | null>(null);
  const [selectedTheme, setSelectedTheme] = useState<ThemeReadResponse | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadList = async (): Promise<void> => {

      try {
        const loadedThemes: ThemeReadResponse[] = await listThemes();

        if (isCancelled) {
          return;
        }

        setThemes(loadedThemes);
        setLoadError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setLoadError(caughtError);
      }
    };

    void loadList();

    return (): void => {
      isCancelled = true;
    };
  }, []);

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    if (openedThemeId === null) {
      setSelectedTheme(null);

      return (): void => {
        isCancelled = true;
      };
    }

    const loadDetail = async (): Promise<void> => {

      try {
        const loadedTheme: ThemeReadResponse = await fetchThemeById(openedThemeId);

        if (isCancelled) {
          return;
        }

        setSelectedTheme(loadedTheme);
        setLoadError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setSelectedTheme(null);
        setLoadError(caughtError);
      }
    };

    void loadDetail();

    return (): void => {
      isCancelled = true;
    };
  }, [openedThemeId]);

  if (openedThemeId !== null) {
    return (
      <ThemeDetailView
        selectedTheme={selectedTheme}
        loadError={loadError}
        statusMessage={statusMessage}
        onBack={(): void => {
          setOpenedThemeId(null);
        }}
      />
    );
  }

  return (
    <ThemeListView
      themes={themes}
      loadError={loadError}
      statusMessage={statusMessage}
      onSelectTheme={(themeId: string): void => {
        setOpenedThemeId(themeId);
      }}
    />
  );
}

interface ThemeListViewProps {
  themes: ThemeReadResponse[];
  loadError: unknown;
  statusMessage: string;
  onSelectTheme: (themeId: string) => void;
}

function ThemeListView({
  themes,
  loadError,
  statusMessage,
  onSelectTheme,
}: ThemeListViewProps): ReactElement {

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>Themes</h1>
          <p className="lede">
            Visual styling for carousels. Open a row for the saved record.
            Create lives on Create Theme.
          </p>
        </div>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}

      {loadError !== null ? null : themes.length === 0 ? (
        <p>No themes yet. Use Create Theme to save a carousel theme.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Advertisement type</th>
              <th>Created</th>
              <th>View</th>
            </tr>
          </thead>
          <tbody>
            {themes.map((theme: ThemeReadResponse): ReactElement => (
              <tr
                key={theme.id}
                className="clickable-row"
                onClick={(): void => {
                  onSelectTheme(theme.id);
                }}
              >
                <td>{theme.name}</td>
                <td>{advertisementTypeLabel(theme.advertisement_type)}</td>
                <td className="mono">{formatThemeTimestamp(theme.created_at)}</td>
                <td>
                  <button
                    type="button"
                    onClick={(clickEvent): void => {
                      clickEvent.stopPropagation();
                      onSelectTheme(theme.id);
                    }}
                  >
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

interface ThemeDetailViewProps {
  selectedTheme: ThemeReadResponse | null;
  loadError: unknown;
  statusMessage: string;
  onBack: () => void;
}

function ThemeDetailView({
  selectedTheme,
  loadError,
  statusMessage,
  onBack,
}: ThemeDetailViewProps): ReactElement {

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>{selectedTheme === null ? "Theme" : selectedTheme.name}</h1>
          <p className="lede">
            Saved theme record. Color and font editors are not on this page.
          </p>
        </div>
        <button type="button" onClick={onBack}>
          Back to list
        </button>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}

      {selectedTheme === null ? (
        loadError === null ? <p>Loading theme…</p> : null
      ) : (
        <dl className="campaign-detail-list">
          <dt>Name</dt>
          <dd>{selectedTheme.name}</dd>
          <dt>Slug</dt>
          <dd className="mono">{selectedTheme.slug}</dd>
          <dt>Advertisement type</dt>
          <dd>{advertisementTypeLabel(selectedTheme.advertisement_type)}</dd>
          <dt>Template</dt>
          <dd className="mono">{formatThemeTemplateKey(selectedTheme.template_key)}</dd>
          <dt>Created</dt>
          <dd className="mono">{formatThemeTimestamp(selectedTheme.created_at)}</dd>
          <dt>Updated</dt>
          <dd className="mono">{formatThemeTimestamp(selectedTheme.updated_at)}</dd>
        </dl>
      )}
    </section>
  );
}
