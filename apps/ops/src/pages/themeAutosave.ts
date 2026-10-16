export const THEME_AUTOSAVE_DELAY_MS: number = 700;

export type ThemeAutosavePhase = "idle" | "pending" | "saving" | "saved" | "error";

export interface ThemeAutosaveState {
  phase: ThemeAutosavePhase;
  message: string;
  canRetry: boolean;
}

export type AutosaveReadiness =
  | { kind: "skip" }
  | { kind: "invalid"; message: string }
  | { kind: "ready" };

export interface ThemeAutosaveControllerOptions<T> {
  delayMs: number;
  readiness: (value: T) => AutosaveReadiness;
  fingerprint: (value: T) => string;
  save: (value: T) => Promise<void>;
  formatError: (error: unknown) => string;
  scheduleTimer?: (callback: () => void | Promise<void>, delayMs: number) => () => void;
}

export interface ThemeAutosaveActions {
  flush: () => Promise<void>;
  retry: () => Promise<void>;
  abandon: () => Promise<void>;
  isDirty: () => boolean;
}

export interface ThemeAutosaveController<T> extends ThemeAutosaveActions {
  updateOptions: (options: ThemeAutosaveControllerOptions<T>) => void;
  schedule: (value: T) => void;
  noteSaved: (value: T) => void;
  getState: () => ThemeAutosaveState;
  subscribe: (listener: () => void) => () => void;
  dispose: () => void;
}

export const IDLE_AUTOSAVE_STATE: ThemeAutosaveState = {
  phase: "idle",
  message: "",
  canRetry: false,
};

const SAVING_MESSAGE: string = "Saving…";
const SAVED_MESSAGE: string = "Saved";

/**
 * Debounced saver. One request at a time, and a newer edit replaces anything
 * still waiting. A failed payload is not sent again until the value changes
 * or the operator retries.
 *
 * @param options - Delay, validation, and the persist function
 * @returns A controller the editor can schedule, flush, and subscribe to
 */
export function createThemeAutosaveController<T>(
  options: ThemeAutosaveControllerOptions<T>,
): ThemeAutosaveController<T> {

  const optionsRef: { current: ThemeAutosaveControllerOptions<T> } = { current: options };
  const listeners: Set<() => void> = new Set();
  let state: ThemeAutosaveState = IDLE_AUTOSAVE_STATE;
  let latestValue: T | null = null;
  let latestReadiness: AutosaveReadiness = { kind: "skip" };
  let latestFingerprint: string | null = null;
  let savedFingerprint: string | null = null;
  let blockedFingerprint: string | null = null;
  let blockedMessage: string = "";
  let didSave: boolean = false;
  let clearTimer: (() => void) | null = null;
  let inFlight: Promise<void> | null = null;
  let abandoned: boolean = false;
  let stopped: boolean = false;
  let disposed: boolean = false;

  const notify = (): void => {

    listeners.forEach((listener: () => void): void => {
      listener();
    });
  };

  const setState = (nextState: ThemeAutosaveState): void => {

    if (
      state.phase === nextState.phase
      && state.message === nextState.message
      && state.canRetry === nextState.canRetry
    ) {
      return;
    }

    state = nextState;
    notify();
  };

  const cancelTimer = (): void => {

    if (clearTimer === null) {
      return;
    }

    clearTimer();
    clearTimer = null;
  };

  const savedState = (): ThemeAutosaveState => {

    if (!didSave) {
      return IDLE_AUTOSAVE_STATE;
    }

    return {
      phase: "saved",
      message: SAVED_MESSAGE,
      canRetry: false,
    };
  };

  const applyReadiness = (value: T): AutosaveReadiness => {

    latestValue = value;

    try {
      latestReadiness = optionsRef.current.readiness(value);
    } catch (caughtError: unknown) {
      latestReadiness = {
        kind: "invalid",
        message: optionsRef.current.formatError(caughtError),
      };
    }

    if (latestReadiness.kind === "ready") {
      try {
        latestFingerprint = optionsRef.current.fingerprint(value);
      } catch (caughtError: unknown) {
        latestFingerprint = null;
        latestReadiness = {
          kind: "invalid",
          message: optionsRef.current.formatError(caughtError),
        };
      }

      return latestReadiness;
    }

    latestFingerprint = null;

    return latestReadiness;
  };

  const needsSave = (): boolean => {

    if (abandoned || latestValue === null || latestReadiness.kind !== "ready") {
      return false;
    }

    if (latestFingerprint === null || latestFingerprint === savedFingerprint) {
      return false;
    }

    if (latestFingerprint === blockedFingerprint) {
      return false;
    }

    return true;
  };

  const showSettledState = (): void => {

    if (latestReadiness.kind === "invalid") {
      setState({
        phase: "error",
        message: latestReadiness.message,
        canRetry: false,
      });

      return;
    }

    if (latestFingerprint !== null && latestFingerprint === blockedFingerprint) {
      setState({
        phase: "error",
        message: blockedMessage,
        canRetry: true,
      });

      return;
    }

    if (latestFingerprint !== null && latestFingerprint === savedFingerprint) {
      setState(savedState());

      return;
    }

    if (latestReadiness.kind === "skip") {
      setState(savedState());
    }
  };

  const runSave = async (): Promise<void> => {

    if (inFlight !== null) {
      await inFlight;

      if (needsSave()) {
        await runSave();
      } else {
        showSettledState();
      }

      return;
    }

    if (latestValue !== null) {
      applyReadiness(latestValue);
    }

    if (!needsSave() || latestValue === null || latestFingerprint === null) {
      showSettledState();

      return;
    }

    const valueAtSend: T = latestValue;
    const fingerprintAtSend: string = latestFingerprint;

    cancelTimer();

    let releaseFlight: () => void = (): void => {
      return;
    };
    const flight: Promise<void> = new Promise((resolve: () => void): void => {
      releaseFlight = resolve;
    });
    inFlight = flight;
    setState({
      phase: "saving",
      message: SAVING_MESSAGE,
      canRetry: false,
    });

    const savePromise: Promise<void> = (async (): Promise<void> => {

      try {
        await optionsRef.current.save(valueAtSend);
        savedFingerprint = fingerprintAtSend;
        blockedFingerprint = null;
        blockedMessage = "";
        didSave = true;
      } catch (caughtError: unknown) {
        const stillCurrent: boolean = latestFingerprint === fingerprintAtSend
          && latestReadiness.kind === "ready";

        if (stillCurrent) {
          blockedFingerprint = fingerprintAtSend;
          blockedMessage = optionsRef.current.formatError(caughtError);
        }
      } finally {
        releaseFlight();
      }
    })();

    try {
      await savePromise;
    } finally {
      if (inFlight === flight) {
        inFlight = null;
      }
    }

    if (needsSave()) {
      await runSave();

      return;
    }

    showSettledState();
  };

  const flush = async (): Promise<void> => {

    if (abandoned) {
      return;
    }

    cancelTimer();
    await runSave();
  };

  const schedule = (value: T): void => {

    if (stopped || abandoned) {
      return;
    }

    const readiness: AutosaveReadiness = applyReadiness(value);

    cancelTimer();

    if (readiness.kind === "invalid") {
      if (inFlight === null) {
        setState({
          phase: "error",
          message: readiness.message,
          canRetry: false,
        });
      }

      return;
    }

    if (readiness.kind === "skip") {
      if (inFlight === null) {
        setState(savedState());
      }

      return;
    }

    if (latestFingerprint === savedFingerprint) {
      blockedFingerprint = null;
      blockedMessage = "";

      if (inFlight === null) {
        setState(savedState());
      }

      return;
    }

    if (latestFingerprint === blockedFingerprint) {
      if (inFlight === null) {
        setState({
          phase: "error",
          message: blockedMessage,
          canRetry: true,
        });
      }

      return;
    }

    setState({
      phase: "pending",
      message: SAVING_MESSAGE,
      canRetry: false,
    });
    clearTimer = optionsRef.current.scheduleTimer === undefined
      ? defaultScheduleTimer((): Promise<void> => flush(), optionsRef.current.delayMs)
      : optionsRef.current.scheduleTimer(
        (): Promise<void> => flush(),
        optionsRef.current.delayMs,
      );
  };

  const controller: ThemeAutosaveController<T> = {
    updateOptions: (nextOptions: ThemeAutosaveControllerOptions<T>): void => {
      optionsRef.current = nextOptions;
    },
    schedule,
    noteSaved: (value: T): void => {
      let fingerprint: string | null = null;

      try {
        const readiness: AutosaveReadiness = optionsRef.current.readiness(value);

        if (readiness.kind !== "ready") {
          return;
        }

        fingerprint = optionsRef.current.fingerprint(value);
      } catch {
        return;
      }

      savedFingerprint = fingerprint;

      if (latestFingerprint !== fingerprint) {
        return;
      }

      blockedFingerprint = null;
      blockedMessage = "";
      cancelTimer();

      if (inFlight === null) {
        setState(savedState());
      }
    },
    flush,
    retry: async (): Promise<void> => {
      if (abandoned) {
        return;
      }

      blockedFingerprint = null;
      blockedMessage = "";
      await flush();
    },
    abandon: async (): Promise<void> => {
      abandoned = true;
      cancelTimer();
      latestReadiness = { kind: "skip" };
      latestFingerprint = savedFingerprint;

      if (inFlight !== null) {
        await inFlight;
      }

      setState(savedState());
    },
    isDirty: (): boolean => {
      if (abandoned) {
        return false;
      }

      if (clearTimer !== null || inFlight !== null) {
        return true;
      }

      if (latestReadiness.kind === "invalid") {
        return true;
      }

      if (latestReadiness.kind === "ready" && latestFingerprint !== savedFingerprint) {
        return true;
      }

      return false;
    },
    getState: (): ThemeAutosaveState => state,
    subscribe: (listener: () => void): (() => void) => {
      listeners.add(listener);

      return (): void => {
        listeners.delete(listener);
      };
    },
    dispose: (): void => {
      if (disposed) {
        return;
      }

      disposed = true;
      stopped = true;
      cancelTimer();

      if (abandoned) {
        return;
      }

      void flush();
    },
  };

  return controller;
}

/**
 * Pick the status the operator should see when several savers are in flight.
 *
 * An error wins, then a save that has not finished, then Saved.
 *
 * @param states - Frame and element saver states
 * @returns One status for the theme header
 */
export function combineAutosaveStates(
  states: readonly ThemeAutosaveState[],
): ThemeAutosaveState {

  const errors: ThemeAutosaveState[] = states.filter(
    (autosaveState: ThemeAutosaveState): boolean => autosaveState.phase === "error",
  );

  if (errors.length > 0) {
    const message: string = errors
      .map((autosaveState: ThemeAutosaveState): string => autosaveState.message)
      .filter((messageText: string): boolean => messageText !== "")
      .join(" ");
    const combinedError: ThemeAutosaveState = {
      phase: "error",
      message,
      canRetry: errors.some(
        (autosaveState: ThemeAutosaveState): boolean => autosaveState.canRetry,
      ),
    };

    return combinedError;
  }

  const isSaving: boolean = states.some(
    (autosaveState: ThemeAutosaveState): boolean => {
      return autosaveState.phase === "saving" || autosaveState.phase === "pending";
    },
  );

  if (isSaving) {
    const savingState: ThemeAutosaveState = {
      phase: "saving",
      message: SAVING_MESSAGE,
      canRetry: false,
    };

    return savingState;
  }

  const isSaved: boolean = states.some(
    (autosaveState: ThemeAutosaveState): boolean => autosaveState.phase === "saved",
  );

  if (isSaved) {
    const savedState: ThemeAutosaveState = {
      phase: "saved",
      message: SAVED_MESSAGE,
      canRetry: false,
    };

    return savedState;
  }

  return IDLE_AUTOSAVE_STATE;
}

/**
 * Flush, then leave. If the latest edit still cannot be stored, ask first.
 *
 * @param flush - Persist any pending valid edit
 * @param isDirty - Whether something unsaved remains after the flush
 * @param onLeave - Navigation to run once the editor can close
 */
export async function leaveAfterAutosave(
  flush: () => Promise<void>,
  isDirty: () => boolean,
  onLeave: () => void,
): Promise<void> {

  await flush();

  if (isDirty()) {
    const confirmed: boolean = window.confirm(
      "The latest edits were not saved. Leave anyway?",
    );

    if (!confirmed) {
      return;
    }
  }

  onLeave();
}

/**
 * Render an API or client failure as the sentence the status line shows.
 *
 * @param error - Caught save failure
 * @returns Operator-facing text
 */
export function formatThemeAutosaveError(error: unknown): string {

  const detailText: string | null = detailTextFromError(error);

  if (detailText !== null) {
    return detailText;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return String(error);
}

function detailTextFromError(error: unknown): string | null {

  if (typeof error !== "object" || error === null || !("detailText" in error)) {
    return null;
  }

  const detailText: unknown = error.detailText;

  if (typeof detailText !== "string") {
    return null;
  }

  return detailText;
}

function defaultScheduleTimer(
  callback: () => void | Promise<void>,
  delayMs: number,
): () => void {

  const timerId: ReturnType<typeof setTimeout> = setTimeout((): void => {
    void callback();
  }, delayMs);

  return (): void => {
    clearTimeout(timerId);
  };
}
