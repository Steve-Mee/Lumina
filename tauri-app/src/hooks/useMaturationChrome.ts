import { useEffect, useMemo, useState } from "react";

import type { MaturationPhaseId } from "@/components/birth/GenesisMaturityLadder";
import { fetchMaturationProgress } from "@/lib/maturationClient";
import { resolveChromeMaturationPhase } from "@/lib/maturationPhaseChrome";
import { useBirthStore } from "@/store/birthStore";
import { useOnboardingStore } from "@/store/onboardingStore";

export interface MaturationChromeState {
  phase: MaturationPhaseId;
  eligible: boolean;
  blockers: string[];
  error: string | null;
  /** True when phase is driven by local journey (wizard/birth), not API. */
  localJourney: boolean;
}

/**
 * Shared maturation spine for chrome ladder across wizard, birth, and deck.
 */
export function useMaturationChrome(): MaturationChromeState {
  const appPhase = useOnboardingStore((s) => s.phase);
  const birthSurface = useBirthStore((s) => s.birthSurface);
  const birthUiPhase = useBirthStore((s) => s.uiPhase);

  const [apiPhase, setApiPhase] = useState<string | null>(null);
  const [eligible, setEligible] = useState(false);
  const [blockers, setBlockers] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const localJourney = appPhase === "wizard" || appPhase === "birth";

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    const load = () => {
      void fetchMaturationProgress()
        .then((payload) => {
          if (cancelled) return;
          setApiPhase(String(payload.current_phase || ""));
          setEligible(Boolean(payload.real_trading_eligible));
          setBlockers(
            Array.isArray(payload.real_trading_blockers) ? payload.real_trading_blockers : [],
          );
          setError(null);
        })
        .catch((err) => {
          if (!cancelled) {
            setError(err instanceof Error ? err.message : "Maturity status unavailable");
          }
        });
    };

    load();
    // Deck: light poll so promotion moves the spine without full page refresh.
    if (!localJourney) {
      timer = window.setInterval(load, 15_000);
    }
    return () => {
      cancelled = true;
      if (timer != null) window.clearInterval(timer);
    };
  }, [localJourney]);

  const phase = useMemo(
    () =>
      resolveChromeMaturationPhase({
        appPhase,
        birthSurface,
        birthUiPhase,
        apiPhase,
      }),
    [appPhase, birthSurface, birthUiPhase, apiPhase],
  );

  return {
    phase,
    eligible,
    blockers,
    error: localJourney ? null : error,
    localJourney,
  };
}
