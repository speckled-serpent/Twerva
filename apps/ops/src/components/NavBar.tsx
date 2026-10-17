import { useState, type ReactElement } from "react";

import type { OpsUserRole } from "../api/types";

export type OpsPageId =
  | "campaigns"
  | "new-campaign"
  | "skeletons"
  | "new-skeleton"
  | "carousels"
  | "new-carousel"
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

interface NavGroup {
  label: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Content",
    items: [
      { pageId: "campaigns", label: "Campaigns" },
      { pageId: "skeletons", label: "Skeletons" },
      { pageId: "carousels", label: "Carousels" },
    ],
  },
  {
    label: "Run",
    items: [
      { pageId: "queue", label: "Queue" },
      { pageId: "schedule", label: "Schedule" },
      { pageId: "results", label: "Results" },
    ],
  },
  {
    label: "Setup",
    items: [
      { pageId: "accounts", label: "Accounts" },
      { pageId: "users", label: "Users", adminOnly: true },
    ],
  },
];

/**
 * Map create-form pages back to the list section they belong to.
 *
 * @param activePageId - Page currently shown in the main pane
 * @returns The rail item that should look selected
 */
function railSectionForPage(activePageId: OpsPageId): OpsPageId {

  if (activePageId === "new-campaign") {
    return "campaigns";
  }

  if (activePageId === "new-skeleton") {
    return "skeletons";
  }

  if (activePageId === "new-carousel") {
    return "carousels";
  }

  return activePageId;
}

/**
 * Left rail for ops sections, with account and logout pinned at the bottom.
 *
 * @param props - Active page, navigate callback, health, session
 * @returns The ops navigation rail
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

  const [isNavOpen, setIsNavOpen] = useState<boolean>(false);
  const sectionPageId: OpsPageId = railSectionForPage(activePageId);
  const railClassName: string = isNavOpen ? "ops-rail is-open" : "ops-rail";

  const navigateTo = (pageId: OpsPageId): void => {

    setIsNavOpen(false);
    onNavigate(pageId);
  };

  return (
    <aside className={railClassName}>
      <div className="ops-rail-top">
        <div className="ops-brand-block">
          <strong className="ops-brand">Twerva</strong>
          <span className="ops-brand-sub">ops</span>
        </div>
        <button
          type="button"
          className="ops-rail-toggle"
          aria-expanded={isNavOpen}
          aria-controls="ops-rail-body"
          onClick={(): void => {
            setIsNavOpen((currentlyOpen: boolean): boolean => {
              return !currentlyOpen;
            });
          }}
        >
          {isNavOpen ? "Close" : "Menu"}
        </button>
      </div>
      <div className="ops-rail-body" id="ops-rail-body">
        <nav className="ops-nav" aria-label="Ops pages">
          {NAV_GROUPS.map((navGroup: NavGroup): ReactElement | null => {
            const visibleItems: NavItem[] = navGroup.items.filter((navItem: NavItem): boolean => {
              return navItem.adminOnly !== true || signedInRole === "admin";
            });

            if (visibleItems.length === 0) {
              return null;
            }

            return (
              <div key={navGroup.label} className="ops-nav-group">
                <p className="ops-nav-group-label">{navGroup.label}</p>
                {visibleItems.map((navItem: NavItem): ReactElement => {
                  const isActive: boolean = navItem.pageId === sectionPageId;

                  return (
                    <button
                      key={navItem.pageId}
                      type="button"
                      className={isActive ? "ops-nav-button is-active" : "ops-nav-button"}
                      aria-current={isActive ? "page" : undefined}
                      onClick={(): void => {
                        navigateTo(navItem.pageId);
                      }}
                    >
                      {navItem.label}
                    </button>
                  );
                })}
              </div>
            );
          })}
        </nav>
        <div className="ops-rail-footer">
          <p className="ops-health">{healthLabel}</p>
          <button
            type="button"
            className={sectionPageId === "account" ? "ops-account-button is-active" : "ops-account-button"}
            aria-current={sectionPageId === "account" ? "page" : undefined}
            onClick={(): void => {
              navigateTo("account");
            }}
          >
            <span className="ops-account-copy">
              <span className="ops-account-label">Account</span>
              <span className="ops-signed-in">{signedInUsername}</span>
            </span>
            <span className="ops-role-badge">{signedInRole}</span>
          </button>
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
        </div>
      </div>
    </aside>
  );
}
