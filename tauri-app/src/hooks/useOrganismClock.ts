import { useOrganismShellVars } from "@/hooks/useOrganismShellVars";
import { useOrganismClockSnapshot } from "@/hooks/useOrganismClockSnapshot";
import type { RefObject } from "react";

import { readOrganismClock } from "@/lib/breatheCurve";
import type { TradingMode } from "@/store/coreStore";

export { readOrganismClock };

/** Applies CSS vars on shell root via shared organism clock store. */
export function useOrganismClock(
  shellRef: RefObject<HTMLElement | null>,
  mode: TradingMode,
  reducedMotion: boolean,
  clockFrozen = false,
): void {
  useOrganismShellVars(shellRef, mode, reducedMotion, clockFrozen);
}

/** Snapshot hook for R3F scenes — phase/envelope from singleton clock. */
export function useOrganismClockFrame(mode: TradingMode, reducedMotion: boolean) {
  return useOrganismClockSnapshot(mode, reducedMotion);
}
