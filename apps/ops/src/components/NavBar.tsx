import type { ReactElement } from "react";

export type OpsPageId = "sources" | "queue" | "schedule" | "accounts" | "results";

export interface NavBarProps {
  activePageId: OpsPageId;
  onNavigate: (pageId: OpsPageId) => void;
  healthLabel: string;
  signedInUsername: string;
  onLogout: () => void;
  isLoggingOut: boolean;
}

interface NavItem {
  pageId: OpsPageId;
  label: string;
}

const NAV_ITEMS: NavItem[] = [
  { pageId: "sources", label: "Sources" },
  { pageId: "queue", label: "Queue" },
  { pageId: "schedule", label: "Schedule" },
  { pageId: "accounts", label: "Accounts" },
  { pageId: "results", label: "Results" },
];

/**
 * Top nav for the five Phase 1.8 ops pages plus operator logout.
 *
 * @param props - Active page, navigate callback, health, session
 * @returns The ops header
 */
export function NavBar({
  activePageId,
  onNavigate,
  healthLabel,
  signedInUsername,
  onLogout,
  isLoggingOut,
}: NavBarProps): ReactElement {

  return (
    <header className="ops-header">
      <div className="ops-header-title-row">
        <strong>Twerva ops</strong>
        <span className="ops-header-meta">
          <span className="ops-health">{healthLabel}</span>
          <span className="ops-signed-in">{signedInUsername}</span>
          <button
            type="button"
            className="ops-logout-button"
            disabled={isLoggingOut}
            onClick={(): void => {
              onLogout();
            }}
          >
            {isLoggingOut ? "Signing out…" : "Log out"}
          </button>
        </span>
      </div>
      <nav className="ops-nav" aria-label="Ops pages">
        {NAV_ITEMS.map((navItem: NavItem): ReactElement => {
          const isActive: boolean = navItem.pageId === activePageId;

          return (
            <button
              key={navItem.pageId}
              type="button"
              className={isActive ? "ops-nav-button is-active" : "ops-nav-button"}
              onClick={(): void => {
                onNavigate(navItem.pageId);
              }}
            >
              {navItem.label}
            </button>
          );
        })}
      </nav>
    </header>
  );
}
