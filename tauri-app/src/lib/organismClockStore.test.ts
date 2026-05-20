import { describe, expect, it } from "vitest";

import {
  getOrganismClock,
  resetOrganismClockOrigin,
  setOrganismClockMode,
} from "@/lib/organismClockStore";
import { ORGANISM_BREATHE_CYCLE_SIM_SEC } from "@/lib/breatheCurve";

describe("organismClockStore", () => {
  it("returns aligned phase and envelope for same elapsed", () => {
    resetOrganismClockOrigin();
    setOrganismClockMode("SIM");
    const a = getOrganismClock("SIM");
    const b = getOrganismClock("SIM");
    expect(a.phase).toBe(b.phase);
    expect(a.envelope).toBe(b.envelope);
  });

  it("uses different cycle lengths per mode at same elapsed", () => {
    resetOrganismClockOrigin();
    setOrganismClockMode("SIM");
    const sim = getOrganismClock("SIM");
    const real = getOrganismClock("REAL");
    expect(sim.cycleSec).toBe(ORGANISM_BREATHE_CYCLE_SIM_SEC);
    expect(real.cycleSec).toBeGreaterThan(sim.cycleSec);
  });
});
