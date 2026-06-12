import { useEffect, useRef } from "react";

import { useBirthStore } from "@/store/birthStore";
import { useOnboardingStore } from "@/store/onboardingStore";

const POLL_MS = 2000;

export function useBirthPhaseMonitor() {
  const poll = useBirthStore((s) => s.poll);
  const bootstrapSession = useBirthStore((s) => s.bootstrapSession);
  const appSurfaceReason = useOnboardingStore((s) => s.payload?.app_surface_reason);
  const targetTrades = useOnboardingStore((s) => s.draft.training.training_trades);
  const bootstrapStarted = useRef(false);

  useEffect(() => {
    if (bootstrapStarted.current) {
      return;
    }
    bootstrapStarted.current = true;

    void (async () => {
      await poll();
      await bootstrapSession({
        appSurfaceReason,
        targetTrades,
      });
    })();
  }, [poll, bootstrapSession, appSurfaceReason, targetTrades]);

  useEffect(() => {
    const timer = window.setInterval(() => void poll(), POLL_MS);
    return () => window.clearInterval(timer);
  }, [poll]);
}

export function useBirthFinaleActions() {
  const finaleTimerRef = useRef<number | null>(null);
  return finaleTimerRef;
}
