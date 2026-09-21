import { useEffect, useState, type ReactElement } from "react";

import {
  UNAUTHORIZED_EVENT_NAME,
  fetchCurrentOpsOperator,
  fetchHealthStatus,
  logoutOpsOperator,
} from "./api/client";
import type { HealthReadResponse, OpsUserReadResponse } from "./api/types";
import { NavBar, type OpsPageId } from "./components/NavBar";
import { AccountPage } from "./pages/AccountPage";
import { AccountsPage } from "./pages/AccountsPage";
import { LoginPage } from "./pages/LoginPage";
import { QueuePage } from "./pages/QueuePage";
import { ResultsPage } from "./pages/ResultsPage";
import { SchedulePage } from "./pages/SchedulePage";
import { CampaignsPage } from "./pages/CampaignsPage";
import { UsersPage } from "./pages/UsersPage";
import { OpsSessionContext, isAdminOpsRole } from "./session/OpsSessionContext";

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
  const [activePageId, setActivePageId] = useState<OpsPageId>("campaigns");
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
    setSignedInOperator(null);
    setSessionState("signed_out");

    try {
      await logoutOpsOperator();
    } catch {
      // Cookie clear is best-effort; the login page is already showing.
    } finally {
      setIsLoggingOut(false);
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

  const canWrite: boolean = isAdminOpsRole(signedInOperator.role);
  const safeActivePageId: OpsPageId =
    activePageId === "users" && !canWrite ? "campaigns" : activePageId;

  return (
    <OpsSessionContext.Provider
      value={{
        currentOperator: signedInOperator,
        canWrite,
      }}
    >
      <div className="ops-console-shell">
        <NavBar
          activePageId={safeActivePageId}
          onNavigate={(pageId: OpsPageId): void => {
            setActivePageId(pageId);
          }}
          healthLabel={healthLabel}
          signedInUsername={signedInOperator.username}
          signedInRole={signedInOperator.role}
          isLoggingOut={isLoggingOut}
          onLogout={(): void => {
            void handleLogout();
          }}
        />
        <main className="ops-main">{renderActivePage(safeActivePageId)}</main>
      </div>
    </OpsSessionContext.Provider>
  );
}

function renderActivePage(activePageId: OpsPageId): ReactElement {

  if (activePageId === "campaigns") {
    return <CampaignsPage />;
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

  if (activePageId === "account") {
    return <AccountPage />;
  }

  if (activePageId === "users") {
    return <UsersPage />;
  }

  return <ResultsPage />;
}
