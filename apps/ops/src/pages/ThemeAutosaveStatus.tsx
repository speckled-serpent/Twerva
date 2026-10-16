import type { ReactElement } from "react";

import type { ThemeAutosaveState } from "./themeAutosave";

export interface ThemeAutosaveStatusProps {
  state: ThemeAutosaveState;
  onRetry: () => void;
}

/**
 * Small Saving / Saved / error line. Idle renders nothing.
 *
 * @param props - Combined saver state and the retry handler
 * @returns The status line, or null when there is nothing to report
 */
export function ThemeAutosaveStatus({
  state,
  onRetry,
}: ThemeAutosaveStatusProps): ReactElement | null {

  if (state.phase === "idle" || state.message === "") {
    return null;
  }

  return (
    <p
      className={`autosave-status autosave-status-${state.phase}`}
      role="status"
      aria-live="polite"
      data-autosave-phase={state.phase}
    >
      <span>{state.message}</span>
      {state.canRetry ? (
        <button type="button" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </p>
  );
}
