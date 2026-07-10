import { useCallback, useRef } from "react";

/** Ignore outside-dismiss briefly after opening a dialog from the same pointer gesture. */
const POINTER_DISMISS_GUARD_MS = 400;

type DismissEvent = { preventDefault: () => void };

/**
 * Radix Dialog can close immediately when opened from a button click: the pointer-up
 * lands on the new overlay. Arm the guard before open (ideally with rAF-deferred setOpen).
 */
export function usePointerDismissGuard() {
  const guardUntilRef = useRef(0);

  const armPointerDismissGuard = useCallback(() => {
    guardUntilRef.current = Date.now() + POINTER_DISMISS_GUARD_MS;
  }, []);

  const shouldSuppressPointerDismiss = useCallback(() => {
    return Date.now() < guardUntilRef.current;
  }, []);

  const consumePointerDismiss = useCallback(
    (event: DismissEvent) => {
      if (shouldSuppressPointerDismiss()) {
        event.preventDefault();
      }
    },
    [shouldSuppressPointerDismiss],
  );

  const runAfterPointerRelease = useCallback((action: () => void) => {
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(action);
    });
  }, []);

  return {
    armPointerDismissGuard,
    shouldSuppressPointerDismiss,
    consumePointerDismiss,
    runAfterPointerRelease,
    dialogDismissGuardProps: {
      onPointerDownOutside: consumePointerDismiss,
      onInteractOutside: consumePointerDismiss,
    },
  };
}
