import { useEffect, useRef } from "react";

import { useBirthStore } from "@/store/birthStore";
import { useOnboardingStore } from "@/store/onboardingStore";

const POLL_MS = 2000;
/** Aggressive retries while waiting for backend after full app restart. */
const COLD_PROBE_ATTEMPTS = 12;
const COLD_PROBE_GAP_MS = 400;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

/**
 * Birth status poll + cold-start session probe.
 *
 * After full app restart the backend may take a moment; until the first status
 * payload arrives, Activate stays locked so a prior birth is not overwritten.
 */
export function useBirthPhaseMonitor() {
  const poll = useBirthStore((s) => s.poll);
  const bootstrapSession = useBirthStore((s) => s.bootstrapSession);
  const markSessionProbeError = useBirthStore((s) => s.markSessionProbeError);
  const appSurfaceReason = useOnboardingStore((s) => s.payload?.app_surface_reason);
  const targetTrades = useOnboardingStore((s) => s.draft.training.training_trades);
  const bootstrapStarted = useRef(false);

  useEffect(() => {
    if (bootstrapStarted.current) {
      return;
    }
    bootstrapStarted.current = true;

    void (async () => {
      let payload = null as Awaited<ReturnType<typeof poll>>;
      for (let attempt = 0; attempt < COLD_PROBE_ATTEMPTS; attempt += 1) {
        payload = await poll();
        if (payload) {
          break;
        }
        // Backend still booting or request aborted — keep probing quickly.
        if (useBirthStore.getState().sessionProbeState === "ready") {
          break;
        }
        await sleep(COLD_PROBE_GAP_MS);
      }

      if (!payload && !useBirthStore.getState().sessionHydrated) {
        markSessionProbeError(
          useBirthStore.getState().pollError ??
            "Birth session status is still loading. Wait or retry — do not activate yet.",
        );
        // One more delayed attempt after cold probe window.
        await sleep(1_000);
        payload = await poll();
      }

      if (payload || useBirthStore.getState().sessionHydrated) {
        await bootstrapSession({
          appSurfaceReason,
          targetTrades,
        });
      } else {
        markSessionProbeError(
          useBirthStore.getState().pollError ??
            "Could not reach the birth service. Check that the backend is running, then retry.",
        );
      }
    })();
  }, [poll, bootstrapSession, markSessionProbeError, appSurfaceReason, targetTrades]);

  useEffect(() => {
    const timer = window.setInterval(() => void poll(), POLL_MS);
    return () => window.clearInterval(timer);
  }, [poll]);
}

export function useBirthFinaleActions() {
  const finaleTimerRef = useRef<number | null>(null);
  return finaleTimerRef;
}
