import { useEffect, useState, type ReactElement } from "react";

import {
  UNAUTHORIZED_EVENT_NAME,
  fetchCurrentOpsOperator,
  fetchHealthStatus,
  logoutOpsOperator,
} from "./api/client";
import type { HealthReadResponse, OpsUserReadResponse } from "./api/types";
import { NavBar, type OpsPageId } from "./components/NavBar";
import { AccountsPage } from "./pages/AccountsPage";
import { LoginPage } from "./pages/LoginPage";
import { QueuePage } from "./pages/QueuePage";
import { ResultsPage } from "./pages/ResultsPage";
import { SchedulePage } from "./pages/SchedulePage";
import { SourcesPage } from "./pages/SourcesPage";

type SessionState = "checking" | "signed_out" | "signed_in";

/**
 * Thin ops console: session gate, then nav plus one page at a time.
 *
 * @returns The ops shell or the login page
 */
export function App(): ReactElement {

  const [sessionState, setSessionState] = useState<SessionState>("checking");
  const [signedInOperator, setSignedInOperator] = useState<OpsUserReadResponse | null>(
    null,
  );
  const [activePageId, setActivePageId] = useState<OpsPageId>("sources");
  const [healthLabel, setHealthLabel] = useState<string>("API: checking…");
  const [isLoggingOut, setIsLoggingOut] = useState<boolean>(false);

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadCurrentOperator = async (): Promise<void> => {

      try {
        const currentOperator: OpsUserReadResponse = await fetchCurrentOpsOperator();

        if (isCancelled) {
          return;
        }

        setSignedInOperator(currentOperator);
        setSessionState("signed_in");
      } catch {
        if (isCancelled) {
          return;
        }

        setSignedInOperator(null);
        setSessionState("signed_out");
      }
    };

    void loadCurrentOperator();

    const handleUnauthorized = (): void => {
      setSignedInOperator(null);
      setSessionState("signed_out");
    };

    window.addEventListener(UNAUTHORIZED_EVENT_NAME, handleUnauthorized);

    return (): void => {
      isCancelled = true;
      window.removeEventListener(UNAUTHORIZED_EVENT_NAME, handleUnauthorized);
    };
  }, []);

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

  const handleLogout = async (): Promise<void> => {

    setIsLoggingOut(true);

    try {
      await logoutOpsOperator();
    } catch {
      // Cookie clear is best-effort; always return to the login page.
    } finally {
      setIsLoggingOut(false);
      setSignedInOperator(null);
      setSessionState("signed_out");
    }
  };

  if (sessionState === "checking") {
    return (
      <div className="ops-console-shell">
        <main className="ops-main">
          <p className="lede">Checking session…</p>
        </main>
      </div>
    );
  }

  if (sessionState === "signed_out" || signedInOperator === null) {
    return (
      <LoginPage
        onSignedIn={(opsUser: OpsUserReadResponse): void => {
          setSignedInOperator(opsUser);
          setSessionState("signed_in");
        }}
      />
    );
  }

  return (
    <div className="ops-console-shell">
      <NavBar
        activePageId={activePageId}
        onNavigate={(pageId: OpsPageId): void => {
          setActivePageId(pageId);
        }}
        healthLabel={healthLabel}
        signedInUsername={signedInOperator.username}
        isLoggingOut={isLoggingOut}
        onLogout={(): void => {
          void handleLogout();
        }}
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
