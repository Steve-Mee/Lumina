import { describe, expect, it } from "vitest";

import { livingCoreHaloAnimationClass, presenceDotClass } from "@/lib/pulseLanguage";

describe("pulseLanguage", () => {
  it("maps SIM presence dot to sim modifier", () => {
    expect(presenceDotClass("SIM", false)).toBe("presence-rail__live-dot--sim");
    expect(presenceDotClass("SIM", true)).toContain("presence-rail__live-dot--engine");
  });

  it("maps REAL presence dot to real modifier", () => {
    expect(presenceDotClass("REAL", false)).toBe("presence-rail__live-dot--real");
  });

  it("maps living core halo animation by mode", () => {
    expect(livingCoreHaloAnimationClass("SIM")).toBe("living-core-halo--pulse");
    expect(livingCoreHaloAnimationClass("REAL")).toBe("living-core-halo--breathe-slow");
  });
});
