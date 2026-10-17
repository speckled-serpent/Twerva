import { useEffect, useState, type ReactElement } from "react";

import {
  UNAUTHORIZED_EVENT_NAME,
  fetchCurrentOpsOperator,
  fetchHealthStatus,
  logoutOpsOperator,
} from "./api/client";
import type {
  CampaignReadResponse,
  HealthReadResponse,
  OpsUserReadResponse,
  CarouselReadResponse,
  SkeletonReadResponse,
} from "./api/types";
import { NavBar, type OpsPageId } from "./components/NavBar";
import { AccountPage } from "./pages/AccountPage";
import { AccountsPage } from "./pages/AccountsPage";
import { CampaignsPage } from "./pages/CampaignsPage";
import { campaignStatusLabel } from "./pages/campaignDisplay";
import { LoginPage } from "./pages/LoginPage";
import { NewCampaignPage } from "./pages/NewCampaignPage";
import { NewCarouselPage } from "./pages/NewCarouselPage";
import { NewSkeletonPage } from "./pages/NewSkeletonPage";
import { QueuePage } from "./pages/QueuePage";
import { ResultsPage } from "./pages/ResultsPage";
import { SchedulePage } from "./pages/SchedulePage";
import { CarouselsPage, type CarouselsOpenRequest } from "./pages/CarouselsPage";
import { SkeletonsPage } from "./pages/SkeletonsPage";
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
  const [openedCampaignId, setOpenedCampaignId] = useState<string | null>(null);
  const [campaignStatusMessage, setCampaignStatusMessage] = useState<string>("");
  const [skeletonStatusMessage, setSkeletonStatusMessage] = useState<string>("");
  const [sourceOpenRequest, setCarouselOpenRequest] = useState<CarouselsOpenRequest | null>(null);
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
      <div className="ops-session-check">
        <p className="lede">Checking session…</p>
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

            if (pageId === "campaigns") {
              setOpenedCampaignId(null);
            }

            if (pageId !== "carousels") {
              setCarouselOpenRequest(null);
            }
          }}
          healthLabel={healthLabel}
          signedInUsername={signedInOperator.username}
          signedInRole={signedInOperator.role}
          isLoggingOut={isLoggingOut}
          onLogout={(): void => {
            void handleLogout();
          }}
        />
        <main className="ops-main">
          {renderActivePage(
            safeActivePageId,
            openedCampaignId,
            campaignStatusMessage,
            skeletonStatusMessage,
            sourceOpenRequest,
            setOpenedCampaignId,
            setCampaignStatusMessage,
            setSkeletonStatusMessage,
            setCarouselOpenRequest,
            setActivePageId,
          )}
        </main>
      </div>
    </OpsSessionContext.Provider>
  );
}

function renderActivePage(
  activePageId: OpsPageId,
  openedCampaignId: string | null,
  campaignStatusMessage: string,
  skeletonStatusMessage: string,
  sourceOpenRequest: CarouselsOpenRequest | null,
  onOpenedCampaignIdChange: (campaignId: string | null) => void,
  onCampaignStatusMessageChange: (statusMessage: string) => void,
  onSkeletonStatusMessageChange: (statusMessage: string) => void,
  onCarouselOpenRequestChange: (openRequest: CarouselsOpenRequest | null) => void,
  onNavigate: (pageId: OpsPageId) => void,
): ReactElement {

  if (activePageId === "campaigns") {
    return (
      <CampaignsPage
        openedCampaignId={openedCampaignId}
        statusMessage={campaignStatusMessage}
        onOpenedCampaignIdChange={onOpenedCampaignIdChange}
        onStatusMessageChange={onCampaignStatusMessageChange}
        onCreateCampaign={(): void => {
          onOpenedCampaignIdChange(null);
          onNavigate("new-campaign");
        }}
      />
    );
  }

  if (activePageId === "new-campaign") {
    return (
      <NewCampaignPage
        onCreated={(createdCampaign: CampaignReadResponse): void => {
          onCampaignStatusMessageChange(
            `Created campaign ${createdCampaign.name} (${campaignStatusLabel(createdCampaign.status)}).`,
          );
          onOpenedCampaignIdChange(createdCampaign.id);
          onNavigate("campaigns");
        }}
        onCancel={(): void => {
          onOpenedCampaignIdChange(null);
          onNavigate("campaigns");
        }}
      />
    );
  }

  if (activePageId === "skeletons") {
    return (
      <SkeletonsPage
        statusMessage={skeletonStatusMessage}
        onCreateSkeleton={(): void => {
          onNavigate("new-skeleton");
        }}
      />
    );
  }

  if (activePageId === "carousels") {
    return (
      <CarouselsPage
        openRequest={sourceOpenRequest}
        onCreateCarousel={(): void => {
          onCarouselOpenRequestChange(null);
          onNavigate("new-carousel");
        }}
      />
    );
  }

  if (activePageId === "new-carousel") {
    return (
      <NewCarouselPage
        onCreated={(createdCarousel: CarouselReadResponse): void => {
          onCarouselOpenRequestChange({
            sourceId: createdCarousel.id,
            statusMessage: `Created carousel ${createdCarousel.name}.`,
          });
          onNavigate("carousels");
        }}
        onCancel={(): void => {
          onNavigate("carousels");
        }}
      />
    );
  }

  if (activePageId === "new-skeleton") {
    return (
      <NewSkeletonPage
        onCreated={(createdSkeleton: SkeletonReadResponse): void => {
          onSkeletonStatusMessageChange(`Created skeleton ${createdSkeleton.name}.`);
        }}
        onCancel={(): void => {
          onNavigate("skeletons");
        }}
      />
    );
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
