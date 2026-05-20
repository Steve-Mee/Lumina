import { useEffect, type RefObject } from "react";

import { configureOrganismClock, subscribeOrganismClock } from "@/lib/organismClockStore";
import { readOrganismClock } from "@/lib/breatheCurve";
import type { TradingMode } from "@/store/coreStore";

export { readOrganismClock };

function applyOrganismVars(
  element: HTMLElement,
  phase: number,
  envelope: number,
  cycleSec: number,
): void {
  element.style.setProperty("--organism-phase", String(phase));
  element.style.setProperty("--organism-envelope", String(envelope));
  element.style.setProperty("--organism-cycle", `${cycleSec}s`);
}

/** Drives organism breathe CSS vars on any shell root (cockpit or onboarding). */
export function useOrganismShellVars(
  shellRef: RefObject<HTMLElement | null>,
  mode: TradingMode,
  reducedMotion: boolean,
  clockFrozen = false,
): void {
  const motionPaused = reducedMotion || clockFrozen;
  useEffect(() => {
    configureOrganismClock(mode, motionPaused);
    return subscribeOrganismClock(({ phase, envelope, cycleSec }) => {
      const element = shellRef.current;
      if (element) {
        applyOrganismVars(element, phase, envelope, cycleSec);
      }
    });
  }, [shellRef, mode, motionPaused]);
}
