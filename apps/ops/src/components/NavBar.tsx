import type { ReactElement } from "react";

import type { OpsUserRole } from "../api/types";

export type OpsPageId =
  | "campaigns"
  | "queue"
  | "schedule"
  | "accounts"
  | "results"
  | "account"
  | "users";

export interface NavBarProps {
  activePageId: OpsPageId;
  onNavigate: (pageId: OpsPageId) => void;
  healthLabel: string;
  signedInUsername: string;
  signedInRole: OpsUserRole;
  onLogout: () => void;
  isLoggingOut: boolean;
}

interface NavItem {
  pageId: OpsPageId;
  label: string;
  adminOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { pageId: "campaigns", label: "Campaigns" },
  { pageId: "queue", label: "Queue" },
  { pageId: "schedule", label: "Schedule" },
  { pageId: "accounts", label: "Accounts" },
  { pageId: "results", label: "Results" },
  { pageId: "account", label: "Account" },
  { pageId: "users", label: "Users", adminOnly: true },
];

/**
 * Top nav for ops pages plus operator role and logout.
 *
 * @param props - Active page, navigate callback, health, session
 * @returns The ops header
 */
export function NavBar({
  activePageId,
  onNavigate,
  healthLabel,
  signedInUsername,
  signedInRole,
  onLogout,
  isLoggingOut,
}: NavBarProps): ReactElement {

  const visibleNavItems: NavItem[] = NAV_ITEMS.filter((navItem: NavItem): boolean => {
    return navItem.adminOnly !== true || signedInRole === "admin";
  });

  return (
    <header className="ops-header">
      <div className="ops-header-title-row">
        <strong>Twerva ops</strong>
        <span className="ops-header-meta">
          <span className="ops-health">{healthLabel}</span>
          <span className="ops-signed-in">
            {signedInUsername}
            <span className="ops-role-badge">{signedInRole}</span>
          </span>
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
        {visibleNavItems.map((navItem: NavItem): ReactElement => {
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
