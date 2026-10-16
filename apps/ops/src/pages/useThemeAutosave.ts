import { useCallback, useEffect, useRef, useState } from "react";

import {
  IDLE_AUTOSAVE_STATE,
  createThemeAutosaveController,
  type AutosaveReadiness,
  type ThemeAutosaveActions,
  type ThemeAutosaveController,
  type ThemeAutosaveControllerOptions,
  type ThemeAutosaveState,
} from "./themeAutosave";

export interface ThemeAutosaveBinding<T> extends ThemeAutosaveActions {
  state: ThemeAutosaveState;
  schedule: (value: T) => void;
  noteSaved: (value: T) => void;
}

/**
 * Hold one autosave controller for the lifetime of the editor.
 *
 * Leaving the page flushes a pending save. Closing the tab warns when the
 * latest edit is still dirty. Strict Mode replays the effect without
 * disposing the controller, so an open theme is not saved twice.
 *
 * @param options - Delay, validation, and the persist function
 * @returns Status plus schedule, flush, and retry
 */
export function useThemeAutosave<T>(
  options: ThemeAutosaveControllerOptions<T>,
): ThemeAutosaveBinding<T> {

  const optionsRef: { current: ThemeAutosaveControllerOptions<T> } = useRef(options);
  optionsRef.current = options;
  const controllerRef: { current: ThemeAutosaveController<T> | null } = useRef(null);
  const lifeRef: { current: number } = useRef(0);
  const [state, setState] = useState<ThemeAutosaveState>(IDLE_AUTOSAVE_STATE);

  if (controllerRef.current === null) {
    controllerRef.current = createThemeAutosaveController(controllerOptions(optionsRef));
  }

  controllerRef.current.updateOptions(controllerOptions(optionsRef));

  useEffect((): (() => void) => {
    const controller: ThemeAutosaveController<T> | null = controllerRef.current;

    if (controller === null) {
      return (): void => {
        return;
      };
    }

    const generation: number = lifeRef.current + 1;
    lifeRef.current = generation;
    const unsubscribe: () => void = controller.subscribe((): void => {
      setState(controller.getState());
    });
    setState(controller.getState());

    const handleBeforeUnload = (event: BeforeUnloadEvent): void => {

      if (!controller.isDirty()) {
        return;
      }

      event.preventDefault();
      event.returnValue = "";
    };

    const handlePageHide = (): void => {
      void controller.flush();
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    window.addEventListener("pagehide", handlePageHide);

    return (): void => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
      window.removeEventListener("pagehide", handlePageHide);
      unsubscribe();
      queueMicrotask((): void => {

        if (lifeRef.current !== generation) {
          return;
        }

        controller.dispose();
      });
    };
  }, []);

  const schedule = useCallback((value: T): void => {
    controllerRef.current?.schedule(value);
  }, []);
  const noteSaved = useCallback((value: T): void => {
    controllerRef.current?.noteSaved(value);
  }, []);
  const flush = useCallback((): Promise<void> => {

    if (controllerRef.current === null) {
      return Promise.resolve();
    }

    return controllerRef.current.flush();
  }, []);
  const retry = useCallback((): Promise<void> => {

    if (controllerRef.current === null) {
      return Promise.resolve();
    }

    return controllerRef.current.retry();
  }, []);
  const abandon = useCallback((): Promise<void> => {

    if (controllerRef.current === null) {
      return Promise.resolve();
    }

    return controllerRef.current.abandon();
  }, []);
  const isDirty = useCallback((): boolean => {

    if (controllerRef.current === null) {
      return false;
    }

    return controllerRef.current.isDirty();
  }, []);

  const binding: ThemeAutosaveBinding<T> = {
    state,
    schedule,
    noteSaved,
    flush,
    retry,
    abandon,
    isDirty,
  };

  return binding;
}

function controllerOptions<T>(
  optionsRef: { current: ThemeAutosaveControllerOptions<T> },
): ThemeAutosaveControllerOptions<T> {

  const options: ThemeAutosaveControllerOptions<T> = {
    delayMs: optionsRef.current.delayMs,
    readiness: (value: T): AutosaveReadiness => {
      return optionsRef.current.readiness(value);
    },
    fingerprint: (value: T): string => {
      return optionsRef.current.fingerprint(value);
    },
    save: (value: T): Promise<void> => {
      return optionsRef.current.save(value);
    },
    formatError: (error: unknown): string => {
      return optionsRef.current.formatError(error);
    },
  };

  return options;
}
