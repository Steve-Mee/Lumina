import { useEffect, useState } from "react";

import {
  configureOrganismClock,
  getOrganismClock,
  subscribeOrganismClock,
  type OrganismClockSnapshot,
} from "@/lib/organismClockStore";
import type { TradingMode } from "@/store/coreStore";

const EMPTY: OrganismClockSnapshot = getOrganismClock("SIM");

/** React hook for shared organism phase/envelope (CSS + R3F). */
export function useOrganismClockSnapshot(mode: TradingMode, reducedMotion: boolean): OrganismClockSnapshot {
  const [snapshot, setSnapshot] = useState<OrganismClockSnapshot>(() => getOrganismClock(mode));

  useEffect(() => {
    configureOrganismClock(mode, reducedMotion);
    return subscribeOrganismClock(setSnapshot);
  }, [mode, reducedMotion]);

  return snapshot;
}

export { EMPTY as ORGANISM_CLOCK_EMPTY };
