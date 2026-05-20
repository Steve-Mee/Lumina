import { describe, expect, it } from "vitest";

import { modeTransition } from "@/lib/modePresentation";

describe("useModeMotion", () => {
  it("REAL transition stiffness is lower than SIM", () => {
    const sim = modeTransition("SIM", false);
    const real = modeTransition("REAL", false);
    expect(sim).toBeDefined();
    expect(real).toBeDefined();
    expect((real as { stiffness: number }).stiffness).toBeLessThan(
      (sim as { stiffness: number }).stiffness,
    );
  });

  it("luxury spring is softer than default in REAL", () => {
    const standard = modeTransition("REAL", false, false);
    const luxury = modeTransition("REAL", false, true);
    expect((luxury as { stiffness: number }).stiffness).toBeLessThan(
      (standard as { stiffness: number }).stiffness,
    );
  });

  it("returns zero duration when reduced motion is enabled", () => {
    expect(modeTransition("SIM", true)).toEqual({ duration: 0 });
  });
});
