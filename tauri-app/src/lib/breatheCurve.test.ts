import { describe, expect, it } from "vitest";

import {
  asymmetricBreatheEnvelope,
  breathePhaseFromTime,
  getOrganismBreatheCycleSec,
  ORGANISM_BREATHE_CYCLE_REAL_SEC,
  ORGANISM_BREATHE_CYCLE_SIM_SEC,
  readOrganismClock,
  vigilantHeartbeatPulse,
} from "@/lib/breatheCurve";

describe("breatheCurve", () => {
  it("peaks inhale around 60% phase", () => {
    expect(asymmetricBreatheEnvelope(0.59)).toBeGreaterThan(asymmetricBreatheEnvelope(0.3));
    expect(asymmetricBreatheEnvelope(0.59)).toBeGreaterThan(asymmetricBreatheEnvelope(0.9));
  });

  it("wraps phase from elapsed time", () => {
    expect(breathePhaseFromTime(ORGANISM_BREATHE_CYCLE_SIM_SEC)).toBeCloseTo(0, 5);
    expect(breathePhaseFromTime(ORGANISM_BREATHE_CYCLE_SIM_SEC / 2)).toBeCloseTo(0.5, 5);
    expect(
      breathePhaseFromTime(ORGANISM_BREATHE_CYCLE_REAL_SEC, ORGANISM_BREATHE_CYCLE_REAL_SEC),
    ).toBeCloseTo(0, 5);
  });

  it("uses slower REAL cycle than SIM", () => {
    expect(getOrganismBreatheCycleSec("REAL")).toBeGreaterThan(getOrganismBreatheCycleSec("SIM"));
  });

  it("readOrganismClock returns aligned phase and envelope", () => {
    const atMid = readOrganismClock(ORGANISM_BREATHE_CYCLE_SIM_SEC / 2, "SIM");
    expect(atMid.phase).toBeCloseTo(0.5, 5);
    expect(atMid.envelope).toBeCloseTo(asymmetricBreatheEnvelope(0.5), 5);
    expect(atMid.cycleSec).toBe(ORGANISM_BREATHE_CYCLE_SIM_SEC);
  });

  it("produces vigilant heartbeat peaks", () => {
    expect(vigilantHeartbeatPulse(0.48, 6)).toBeGreaterThan(0.5);
  });
});
