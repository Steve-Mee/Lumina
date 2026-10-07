import { useMemo } from "react";

import type { MaturationPhaseId } from "@/components/birth/GenesisMaturityLadder";
import { useMaturationChrome } from "@/hooks/useMaturationChrome";
import { normalizeMaturationPhase } from "@/lib/maturationPhaseChrome";
import {
  resolveOrganismMorphology,
  type OrganismMorphology,
} from "@/lib/organism/phaseMorphology";
import { selectCurrentMode, useCoreStore, type TradingMode } from "@/store/coreStore";
import { useOnboardingStore } from "@/store/onboardingStore";

export interface OrganismVisualPhase {
  phase: MaturationPhaseId;
  morph: OrganismMorphology;
  tradingMode: TradingMode;
}

/** Chrome phase + operator mode → display morph. Never writes trading state. */
export function useOrganismVisualPhase(): OrganismVisualPhase {
  const chrome = useMaturationChrome();
  const appSurface = useOnboardingStore((s) => s.payload?.app_surface);
  const tradingMode = useCoreStore(selectCurrentMode);

  return useMemo(() => {
    const fromSurface = normalizeMaturationPhase(appSurface);
    const phase =
      fromSurface && fromSurface !== "setup" && fromSurface !== "genesis"
        ? fromSurface
        : chrome.phase;
    return {
      phase,
      morph: resolveOrganismMorphology(phase, tradingMode),
      tradingMode,
    };
  }, [chrome.phase, appSurface, tradingMode]);
}
