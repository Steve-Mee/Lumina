import { describe, expect, it } from "vitest";

import { resolveVitality } from "@/lib/organismVitalityModel";

describe("organismVitalityModel", () => {
  it("uses Guarded engine glyph in REAL mode", () => {
    const vitality = resolveVitality({
      connectionStatus: "connected",
      fallbackMode: false,
      sessionActive: true,
      activityStale: false,
      engineAlive: true,
      mode: "REAL",
      phaseLabel: "trade",
    });
    expect(vitality.engineGlyph).toBe("Guarded");
    expect(vitality.primaryLabel).toContain("Live");
  });

  it("uses Live engine glyph in SIM mode", () => {
    const vitality = resolveVitality({
      connectionStatus: "connected",
      fallbackMode: false,
      sessionActive: true,
      activityStale: false,
      engineAlive: true,
      mode: "SIM",
    });
    expect(vitality.engineGlyph).toBe("Live");
  });

  it("returns Standby when disconnected", () => {
    const vitality = resolveVitality({
      connectionStatus: "disconnected",
      fallbackMode: false,
      sessionActive: false,
      activityStale: false,
      engineAlive: false,
      mode: "SIM",
    });
    expect(vitality.tier).toBe("dormant");
    expect(vitality.primaryLabel).toBe("Standby");
  });
});
