import { useEffect, useState, type ReactElement } from "react";

import { fetchHealthStatus } from "./api/client";
import type { HealthReadResponse } from "./api/types";
import { NavBar, type OpsPageId } from "./components/NavBar";
import { AccountsPage } from "./pages/AccountsPage";
import { QueuePage } from "./pages/QueuePage";
import { ResultsPage } from "./pages/ResultsPage";
import { SchedulePage } from "./pages/SchedulePage";
import { SourcesPage } from "./pages/SourcesPage";

/**
 * Thin ops console: nav plus one page at a time (no router).
 *
 * @returns The ops shell
 */
export function App(): ReactElement {

  const [activePageId, setActivePageId] = useState<OpsPageId>("sources");
  const [healthLabel, setHealthLabel] = useState<string>("API: checking…");

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadHealth = async (): Promise<void> => {

      try {
        const healthReadResponse: HealthReadResponse = await fetchHealthStatus();

        if (isCancelled) {
          return;
        }

        setHealthLabel(`API: ${healthReadResponse.status}`);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        const errorText: string =
          caughtError instanceof Error ? caughtError.message : String(caughtError);

        setHealthLabel(`API: unreachable (${errorText})`);
      }
    };

    void loadHealth();

    return (): void => {
      isCancelled = true;
    };
  }, []);

  return (
    <div className="ops-console-shell">
      <NavBar
        activePageId={activePageId}
        onNavigate={(pageId: OpsPageId): void => {
          setActivePageId(pageId);
        }}
        healthLabel={healthLabel}
      />
      <main className="ops-main">{renderActivePage(activePageId)}</main>
    </div>
  );
}

function renderActivePage(activePageId: OpsPageId): ReactElement {

  if (activePageId === "sources") {
    return <SourcesPage />;
  }

  if (activePageId === "queue") {
    return <QueuePage />;
  }

  if (activePageId === "schedule") {
    return <SchedulePage />;
  }

  if (activePageId === "accounts") {
    return <AccountsPage />;
  }

  return <ResultsPage />;
}
