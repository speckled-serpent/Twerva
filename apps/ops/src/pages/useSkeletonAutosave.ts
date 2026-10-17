import { useCallback, useEffect, useRef, useState } from "react";

import {
  IDLE_AUTOSAVE_STATE,
  createSkeletonAutosaveController,
  type AutosaveReadiness,
  type SkeletonAutosaveActions,
  type SkeletonAutosaveController,
  type SkeletonAutosaveControllerOptions,
  type SkeletonAutosaveState,
} from "./skeletonAutosave";

export interface SkeletonAutosaveBinding<T> extends SkeletonAutosaveActions {
  state: SkeletonAutosaveState;
  schedule: (value: T) => void;
  noteSaved: (value: T) => void;
}

/**
 * Hold one autosave controller for the lifetime of the editor.
 *
 * Leaving the page flushes a pending save. Closing the tab warns when the
 * latest edit is still dirty. Strict Mode replays the effect without
 * disposing the controller, so an open skeleton is not saved twice.
 *
 * @param options - Delay, validation, and the persist function
 * @returns Status plus schedule, flush, and retry
 */
export function useSkeletonAutosave<T>(
  options: SkeletonAutosaveControllerOptions<T>,
): SkeletonAutosaveBinding<T> {

  const optionsRef: { current: SkeletonAutosaveControllerOptions<T> } = useRef(options);
  optionsRef.current = options;
  const controllerRef: { current: SkeletonAutosaveController<T> | null } = useRef(null);
  const lifeRef: { current: number } = useRef(0);
  const [state, setState] = useState<SkeletonAutosaveState>(IDLE_AUTOSAVE_STATE);

  if (controllerRef.current === null) {
    controllerRef.current = createSkeletonAutosaveController(controllerOptions(optionsRef));
  }

  controllerRef.current.updateOptions(controllerOptions(optionsRef));

  useEffect((): (() => void) => {
    const controller: SkeletonAutosaveController<T> | null = controllerRef.current;

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

  const binding: SkeletonAutosaveBinding<T> = {
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
  optionsRef: { current: SkeletonAutosaveControllerOptions<T> },
): SkeletonAutosaveControllerOptions<T> {

  const options: SkeletonAutosaveControllerOptions<T> = {
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
