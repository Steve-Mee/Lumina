import { describe, expect, it } from "vitest";

import {
  immersiveHaloClass,
  presenceDotAnimationClass,
  presenceDotClass,
} from "@/lib/pulseLanguage";

describe("pulseLanguage", () => {
  it("maps SIM presence dot to sim modifier", () => {
    expect(presenceDotClass("SIM", false)).toBe("presence-rail__live-dot--sim");
    expect(presenceDotClass("SIM", true)).toContain("presence-rail__live-dot--engine");
  });

  it("maps REAL presence dot to real modifier", () => {
    expect(presenceDotClass("REAL", false)).toBe("presence-rail__live-dot--real");
  });

  it("uses presence-pulse-sim in SIM and breathe in REAL", () => {
    expect(presenceDotAnimationClass("SIM")).toBe("presence-pulse-sim");
    expect(presenceDotAnimationClass("REAL")).toBe("presence-breathe-real");
    expect(immersiveHaloClass("SIM")).toBe("living-core-halo--scan");
    expect(immersiveHaloClass("REAL")).toBe("living-core-halo--breathe");
  });
});
