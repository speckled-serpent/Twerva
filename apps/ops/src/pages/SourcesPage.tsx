import { useEffect, useState, type FormEvent, type ReactElement } from "react";

import {
  createSourceItem,
  generateCarouselArtifact,
  listBrands,
  listClusters,
  listSourceItems,
} from "../api/client";
import type {
  ArtifactReadResponse,
  BrandReadResponse,
  ClusterReadResponse,
  SourceItemReadResponse,
} from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import { useCanWriteOps } from "../session/OpsSessionContext";

/**
 * Sources page: list source items, create one, generate a carousel draft.
 *
 * @returns The Sources page
 */
export function SourcesPage(): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [sourceItems, setSourceItems] = useState<SourceItemReadResponse[]>([]);
  const [brands, setBrands] = useState<BrandReadResponse[]>([]);
  const [clusters, setClusters] = useState<ClusterReadResponse[]>([]);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [isBusy, setIsBusy] = useState<boolean>(false);

  const [brandId, setBrandId] = useState<string>("");
  const [title, setTitle] = useState<string>("");
  const [interestHeading, setInterestHeading] = useState<string>("");
  const [overviewBulletsText, setOverviewBulletsText] = useState<string>("");
  const [canonicalUrl, setCanonicalUrl] = useState<string>("");
  const [externalKey, setExternalKey] = useState<string>("");

  const [generateSourceItemId, setGenerateSourceItemId] = useState<string>("");
  const [generateClusterId, setGenerateClusterId] = useState<string>("");

  const reloadLists = async (): Promise<void> => {

    const loadedSourceItems: SourceItemReadResponse[] = await listSourceItems();
    const loadedBrands: BrandReadResponse[] = await listBrands();
    const loadedClusters: ClusterReadResponse[] = await listClusters();

    setSourceItems(loadedSourceItems);
    setBrands(loadedBrands);
    setClusters(loadedClusters);

    if (brandId === "" && loadedBrands.length > 0) {
      setBrandId(loadedBrands[0].id);
    }

    if (generateSourceItemId === "" && loadedSourceItems.length > 0) {
      setGenerateSourceItemId(loadedSourceItems[0].id);
    }
  };

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadPage = async (): Promise<void> => {

      try {
        const loadedSourceItems: SourceItemReadResponse[] = await listSourceItems();
        const loadedBrands: BrandReadResponse[] = await listBrands();
        const loadedClusters: ClusterReadResponse[] = await listClusters();

        if (isCancelled) {
          return;
        }

        setSourceItems(loadedSourceItems);
        setBrands(loadedBrands);
        setClusters(loadedClusters);
        setLoadError(null);

        if (loadedBrands.length > 0) {
          setBrandId(loadedBrands[0].id);
        }

        if (loadedSourceItems.length > 0) {
          setGenerateSourceItemId(loadedSourceItems[0].id);
        }
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setLoadError(caughtError);
      }
    };

    void loadPage();

    return (): void => {
      isCancelled = true;
    };
  }, []);

  const handleCreateSourceItem = async (formEvent: FormEvent): Promise<void> => {

    formEvent.preventDefault();
    setIsBusy(true);
    setActionError(null);
    setStatusMessage("");

    const overviewBullets: string[] = overviewBulletsText
      .split("\n")
      .map((bulletLine: string): string => bulletLine.trim())
      .filter((bulletLine: string): boolean => bulletLine.length > 0);

    try {
      const createdSourceItem: SourceItemReadResponse = await createSourceItem({
        brand_id: brandId,
        title,
        interest_heading: interestHeading === "" ? null : interestHeading,
        overview_bullets: overviewBullets,
        canonical_url: canonicalUrl === "" ? null : canonicalUrl,
        external_key: externalKey === "" ? null : externalKey,
      });

      setStatusMessage(`Created source item ${createdSourceItem.id}`);
      setTitle("");
      setInterestHeading("");
      setOverviewBulletsText("");
      setCanonicalUrl("");
      setExternalKey("");
      setGenerateSourceItemId(createdSourceItem.id);
      await reloadLists();
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setIsBusy(false);
    }
  };

  const handleGenerateCarousel = async (formEvent: FormEvent): Promise<void> => {

    formEvent.preventDefault();
    setIsBusy(true);
    setActionError(null);
    setStatusMessage("");

    try {
      const createdArtifact: ArtifactReadResponse = await generateCarouselArtifact({
        source_item_id: generateSourceItemId,
        cluster_id: generateClusterId === "" ? null : generateClusterId,
      });

      setStatusMessage(
        `Generated draft artifact ${createdArtifact.id} (status ${createdArtifact.status}). Open Queue to review.`,
      );
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <section>
      <h1>Sources</h1>
      <p className="lede">
        List source items, create one if seed is empty, then generate a carousel draft.
      </p>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      <ErrorBanner error={actionError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}

      <h2>Generate carousel</h2>
      <form className="stack-form" onSubmit={(formEvent: FormEvent): void => {
        void handleGenerateCarousel(formEvent);
      }}>
        <label>
          Source item
          <select
            value={generateSourceItemId}
            onChange={(changeEvent): void => {
              setGenerateSourceItemId(changeEvent.target.value);
            }}
            required
          >
            <option value="">Select a source item</option>
            {sourceItems.map((sourceItem: SourceItemReadResponse): ReactElement => (
              <option key={sourceItem.id} value={sourceItem.id}>
                {sourceItem.title} ({sourceItem.id})
              </option>
            ))}
          </select>
        </label>
        <label>
          Cluster (optional — used later by schedule)
          <select
            value={generateClusterId}
            onChange={(changeEvent): void => {
              setGenerateClusterId(changeEvent.target.value);
            }}
          >
            <option value="">No cluster</option>
            {clusters.map((cluster: ClusterReadResponse): ReactElement => (
              <option key={cluster.id} value={cluster.id}>
                {cluster.slug} / {cluster.name} ({cluster.id})
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={!canWrite || isBusy || generateSourceItemId === ""}>
          {isBusy ? "Working…" : "Generate carousel"}
        </button>
      </form>

      <h2>Create source item</h2>
      <form className="stack-form" onSubmit={(formEvent: FormEvent): void => {
        void handleCreateSourceItem(formEvent);
      }}>
        <label>
          Brand
          <select
            value={brandId}
            onChange={(changeEvent): void => {
              setBrandId(changeEvent.target.value);
            }}
            required
          >
            <option value="">Select a brand</option>
            {brands.map((brand: BrandReadResponse): ReactElement => (
              <option key={brand.id} value={brand.id}>
                {brand.slug} ({brand.id})
              </option>
            ))}
          </select>
        </label>
        <label>
          Title
          <input
            value={title}
            onChange={(changeEvent): void => {
              setTitle(changeEvent.target.value);
            }}
            required
          />
        </label>
        <label>
          Interest heading
          <input
            value={interestHeading}
            onChange={(changeEvent): void => {
              setInterestHeading(changeEvent.target.value);
            }}
          />
        </label>
        <label>
          Overview bullets (one per line)
          <textarea
            rows={4}
            value={overviewBulletsText}
            onChange={(changeEvent): void => {
              setOverviewBulletsText(changeEvent.target.value);
            }}
          />
        </label>
        <label>
          Canonical URL
          <input
            value={canonicalUrl}
            onChange={(changeEvent): void => {
              setCanonicalUrl(changeEvent.target.value);
            }}
          />
        </label>
        <label>
          External key (optional unique per brand)
          <input
            value={externalKey}
            onChange={(changeEvent): void => {
              setExternalKey(changeEvent.target.value);
            }}
          />
        </label>
        <button type="submit" disabled={!canWrite || isBusy || brandId === ""}>
          Create source item
        </button>
      </form>

      <h2>Source items</h2>
      {loadError !== null ? null : sourceItems.length === 0 ? (
        <p>No source items. Seed the API (`python -m app.seed`) or create one above.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Title</th>
              <th>Type</th>
              <th>External key</th>
              <th>ID</th>
            </tr>
          </thead>
          <tbody>
            {sourceItems.map((sourceItem: SourceItemReadResponse): ReactElement => (
              <tr key={sourceItem.id}>
                <td>{sourceItem.title}</td>
                <td>{sourceItem.source_type}</td>
                <td>{sourceItem.external_key ?? "—"}</td>
                <td className="mono">{sourceItem.id}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
