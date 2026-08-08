import { useEffect, useRef } from "react";

import { mapAppPhase } from "@/lib/onboardingPhase";
import { useOnboardingStore } from "@/store/onboardingStore";

/**
 * Defense-in-depth: if the deck mounted while backend SSOT says setup/birth,
 * redirect away from Command Deck (e.g. stale phase or manual bypass).
 */
export function useDeckLifecycleGuard(): void {
  const refresh = useOnboardingStore((s) => s.refresh);
  const setPhase = useOnboardingStore((s) => s.setPhase);
  const payload = useOnboardingStore((s) => s.payload);
  const guardedRef = useRef(false);

  useEffect(() => {
    if (guardedRef.current) {
      return;
    }
    guardedRef.current = true;
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!payload?.app_surface) {
      return;
    }

    const operatorDeckActive = useOnboardingStore.getState().operatorDeckActive;
    const expected = mapAppPhase(payload, {
      priorPhase: "cockpit",
      birthPhaseCommitted: false,
      activating: false,
      operatorDeckActive,
    });

    // Allow hub → deck session override; only kick if SSOT is setup/birth.
    if (expected === "wizard" || expected === "birth") {
      setPhase(expected);
      return;
    }
    if (expected === "hub" && !operatorDeckActive) {
      setPhase("hub");
    }
  }, [payload, setPhase]);
}
