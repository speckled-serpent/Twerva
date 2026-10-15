import { useEffect, useState, type FormEvent, type ReactElement } from "react";

import {
  createAccount,
  createCluster,
  listAccounts,
  listBrands,
  listClusters,
  steerCluster,
} from "../api/client";
import type {
  AccountReadResponse,
  BrandReadResponse,
  ClusterReadResponse,
  Platform,
  SteerActionName,
  SteerActionReadResponse,
} from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import { useCanWriteOps } from "../session/OpsSessionContext";

const STEER_ACTIONS: SteerActionName[] = ["kill", "pause", "double_down", "resume"];

/**
 * Accounts page: list clusters/accounts, show cadence caps, steer a cluster.
 *
 * @returns The Accounts page
 */
export function AccountsPage(): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [clusters, setClusters] = useState<ClusterReadResponse[]>([]);
  const [accounts, setAccounts] = useState<AccountReadResponse[]>([]);
  const [brands, setBrands] = useState<BrandReadResponse[]>([]);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [isBusy, setIsBusy] = useState<boolean>(false);

  const [clusterBrandId, setClusterBrandId] = useState<string>("");
  const [clusterSlug, setClusterSlug] = useState<string>("");
  const [clusterName, setClusterName] = useState<string>("");

  const [accountClusterId, setAccountClusterId] = useState<string>("");
  const [accountPlatform, setAccountPlatform] = useState<Platform>("instagram");
  const [accountHandle, setAccountHandle] = useState<string>("");
  const [cadenceCapText, setCadenceCapText] = useState<string>("");

  const [steerClusterId, setSteerClusterId] = useState<string>("");
  const [steerReason, setSteerReason] = useState<string>("");

  const reloadLists = async (): Promise<void> => {

    const loadedClusters: ClusterReadResponse[] = await listClusters();
    const loadedAccounts: AccountReadResponse[] = await listAccounts();
    const loadedBrands: BrandReadResponse[] = await listBrands();

    setClusters(loadedClusters);
    setAccounts(loadedAccounts);
    setBrands(loadedBrands);

    if (clusterBrandId === "" && loadedBrands.length > 0) {
      setClusterBrandId(loadedBrands[0].id);
    }

    if (accountClusterId === "" && loadedClusters.length > 0) {
      setAccountClusterId(loadedClusters[0].id);
    }

    if (steerClusterId === "" && loadedClusters.length > 0) {
      setSteerClusterId(loadedClusters[0].id);
    }
  };

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadPage = async (): Promise<void> => {

      try {
        const loadedClusters: ClusterReadResponse[] = await listClusters();
        const loadedAccounts: AccountReadResponse[] = await listAccounts();
        const loadedBrands: BrandReadResponse[] = await listBrands();

        if (isCancelled) {
          return;
        }

        setClusters(loadedClusters);
        setAccounts(loadedAccounts);
        setBrands(loadedBrands);
        setLoadError(null);

        if (loadedBrands.length > 0) {
          setClusterBrandId(loadedBrands[0].id);
        }

        if (loadedClusters.length > 0) {
          setAccountClusterId(loadedClusters[0].id);
          setSteerClusterId(loadedClusters[0].id);
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

  const handleCreateCluster = async (formEvent: FormEvent): Promise<void> => {

    formEvent.preventDefault();
    setIsBusy(true);
    setActionError(null);
    setStatusMessage("");

    try {
      const createdCluster: ClusterReadResponse = await createCluster({
        brand_id: clusterBrandId,
        slug: clusterSlug,
        name: clusterName,
      });

      setStatusMessage(`Created cluster ${createdCluster.slug} (${createdCluster.id})`);
      setClusterSlug("");
      setClusterName("");
      setAccountClusterId(createdCluster.id);
      setSteerClusterId(createdCluster.id);
      await reloadLists();
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setIsBusy(false);
    }
  };

  const handleCreateAccount = async (formEvent: FormEvent): Promise<void> => {

    formEvent.preventDefault();
    setIsBusy(true);
    setActionError(null);
    setStatusMessage("");

    let cadenceCapPerDay: number | null = null;

    if (cadenceCapText.trim() !== "") {
      const parsedCadenceCap: number = Number(cadenceCapText);

      if (!Number.isInteger(parsedCadenceCap) || parsedCadenceCap < 0) {
        setActionError(new Error("cadence_cap_per_day must be a non-negative integer."));
        setIsBusy(false);

        return;
      }

      cadenceCapPerDay = parsedCadenceCap;
    }

    try {
      const createdAccount: AccountReadResponse = await createAccount({
        cluster_id: accountClusterId,
        platform: accountPlatform,
        handle: accountHandle,
        cadence_cap_per_day: cadenceCapPerDay,
      });

      setStatusMessage(`Created account @${createdAccount.handle} (${createdAccount.id})`);
      setAccountHandle("");
      setCadenceCapText("");
      await reloadLists();
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setIsBusy(false);
    }
  };

  const handleSteer = async (action: SteerActionName): Promise<void> => {

    setIsBusy(true);
    setActionError(null);
    setStatusMessage("");

    try {
      const steerAction: SteerActionReadResponse = await steerCluster(steerClusterId, {
        action,
        reason: steerReason === "" ? null : steerReason,
        created_by: "human",
      });

      setStatusMessage(`Steer ${steerAction.action} recorded (${steerAction.id})`);
      await reloadLists();
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>Accounts</h1>
          <p className="lede">
            Clusters and accounts. Cadence cap is per account. Steer is per cluster.
          </p>
        </div>
      </div>
      <ReadOnlyNotice />
      <ErrorBanner error={loadError} />
      <ErrorBanner error={actionError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}

      <h2>Steer</h2>
      <form className="stack-form" onSubmit={(formEvent: FormEvent): void => {
        formEvent.preventDefault();
      }}>
        <label>
          Cluster
          <select
            value={steerClusterId}
            onChange={(changeEvent): void => {
              setSteerClusterId(changeEvent.target.value);
            }}
          >
            <option value="">Select a cluster</option>
            {clusters.map((cluster: ClusterReadResponse): ReactElement => (
              <option key={cluster.id} value={cluster.id}>
                {cluster.slug} · active={String(cluster.is_active)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Reason (optional)
          <input
            value={steerReason}
            onChange={(changeEvent): void => {
              setSteerReason(changeEvent.target.value);
            }}
          />
        </label>
        <div className="button-row">
          {STEER_ACTIONS.map((steerAction: SteerActionName): ReactElement => (
            <button
              key={steerAction}
              type="button"
              disabled={!canWrite || isBusy || steerClusterId === ""}
              onClick={(): void => {
                void handleSteer(steerAction);
              }}
            >
              {steerAction}
            </button>
          ))}
        </div>
      </form>

      <h2>Clusters</h2>
      {loadError !== null ? null : clusters.length === 0 ? (
        <p>No clusters. Create one below (seed does not create a cluster).</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Slug</th>
              <th>Name</th>
              <th>Active</th>
              <th>Sources</th>
              <th>ID</th>
            </tr>
          </thead>
          <tbody>
            {clusters.map((cluster: ClusterReadResponse): ReactElement => (
              <tr key={cluster.id}>
                <td>{cluster.slug}</td>
                <td>{cluster.name}</td>
                <td>{String(cluster.is_active)}</td>
                <td>{cluster.source_item_ids.length}</td>
                <td className="mono">{cluster.id}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2>Accounts</h2>
      {loadError !== null ? null : accounts.length === 0 ? (
        <p>No accounts. Create one below.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Handle</th>
              <th>Platform</th>
              <th>Status</th>
              <th>cadence_cap_per_day</th>
              <th>Cluster</th>
              <th>ID</th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((account: AccountReadResponse): ReactElement => (
              <tr key={account.id}>
                <td>@{account.handle}</td>
                <td>{account.platform}</td>
                <td>{account.status}</td>
                <td>{account.cadence_cap_per_day ?? "—"}</td>
                <td className="mono">{account.cluster_id}</td>
                <td className="mono">{account.id}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2>Create cluster</h2>
      <form className="stack-form" onSubmit={(formEvent: FormEvent): void => {
        void handleCreateCluster(formEvent);
      }}>
        <label>
          Brand
          <select
            value={clusterBrandId}
            onChange={(changeEvent): void => {
              setClusterBrandId(changeEvent.target.value);
            }}
            required
          >
            <option value="">Select a brand</option>
            {brands.map((brand: BrandReadResponse): ReactElement => (
              <option key={brand.id} value={brand.id}>
                {brand.slug}
              </option>
            ))}
          </select>
        </label>
        <label>
          Slug
          <input
            value={clusterSlug}
            onChange={(changeEvent): void => {
              setClusterSlug(changeEvent.target.value);
            }}
            required
          />
        </label>
        <label>
          Name
          <input
            value={clusterName}
            onChange={(changeEvent): void => {
              setClusterName(changeEvent.target.value);
            }}
            required
          />
        </label>
        <button type="submit" disabled={!canWrite || isBusy || clusterBrandId === ""}>
          Create cluster
        </button>
      </form>

      <h2>Create account</h2>
      <form className="stack-form" onSubmit={(formEvent: FormEvent): void => {
        void handleCreateAccount(formEvent);
      }}>
        <label>
          Cluster
          <select
            value={accountClusterId}
            onChange={(changeEvent): void => {
              setAccountClusterId(changeEvent.target.value);
            }}
            required
          >
            <option value="">Select a cluster</option>
            {clusters.map((cluster: ClusterReadResponse): ReactElement => (
              <option key={cluster.id} value={cluster.id}>
                {cluster.slug}
              </option>
            ))}
          </select>
        </label>
        <label>
          Platform
          <select
            value={accountPlatform}
            onChange={(changeEvent): void => {
              setAccountPlatform(changeEvent.target.value as Platform);
            }}
          >
            <option value="instagram">instagram</option>
            <option value="tiktok">tiktok</option>
          </select>
        </label>
        <label>
          Handle
          <input
            value={accountHandle}
            onChange={(changeEvent): void => {
              setAccountHandle(changeEvent.target.value);
            }}
            required
          />
        </label>
        <label>
          cadence_cap_per_day (optional)
          <input
            value={cadenceCapText}
            onChange={(changeEvent): void => {
              setCadenceCapText(changeEvent.target.value);
            }}
          />
        </label>
        <button type="submit" disabled={!canWrite || isBusy || accountClusterId === ""}>
          Create account
        </button>
      </form>
    </section>
  );
}
