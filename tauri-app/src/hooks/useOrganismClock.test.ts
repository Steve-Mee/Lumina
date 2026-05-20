import { describe, expect, it } from "vitest";

import { ORGANISM_BREATHE_CYCLE_SIM_SEC } from "@/lib/breatheCurve";
import { readOrganismClock } from "@/hooks/useOrganismClock";

describe("readOrganismClock", () => {
  it("REAL cycle is slower than SIM", () => {
    const sim = readOrganismClock(1, "SIM");
    const real = readOrganismClock(1, "REAL");
    expect(real.cycleSec).toBeGreaterThan(sim.cycleSec);
  });

  it("phase wraps at cycle boundary", () => {
    const start = readOrganismClock(0, "SIM");
    const end = readOrganismClock(ORGANISM_BREATHE_CYCLE_SIM_SEC, "SIM");
    expect(start.phase).toBeCloseTo(0, 5);
    expect(end.phase).toBeCloseTo(0, 5);
  });

  it("envelope peaks near inhale end", () => {
    const inhalePeak = readOrganismClock(ORGANISM_BREATHE_CYCLE_SIM_SEC * 0.59, "SIM");
    const midExhale = readOrganismClock(ORGANISM_BREATHE_CYCLE_SIM_SEC * 0.8, "SIM");
    expect(inhalePeak.envelope).toBeGreaterThan(midExhale.envelope);
  });
});
