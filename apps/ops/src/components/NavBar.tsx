import type { ReactElement } from "react";

export type OpsPageId = "sources" | "queue" | "schedule" | "accounts" | "results";

export interface NavBarProps {
  activePageId: OpsPageId;
  onNavigate: (pageId: OpsPageId) => void;
  healthLabel: string;
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
 * Top nav for the five Phase 1.8 ops pages.
 *
 * @param props - Active page, navigate callback, health label
 * @returns The ops header
 */
export function NavBar({ activePageId, onNavigate, healthLabel }: NavBarProps): ReactElement {

  return (
    <header className="ops-header">
      <div className="ops-header-title-row">
        <strong>Twerva ops</strong>
        <span className="ops-health">{healthLabel}</span>
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
