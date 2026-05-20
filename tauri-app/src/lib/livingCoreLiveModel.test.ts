import { describe, expect, it } from "vitest";

import {
  buildVisualParamsFromSignals,
  computeVitality,
  normalizeRegimeKey,
  vitalityBucket,
} from "@/lib/livingCoreLiveModel";
import { modePalette } from "@/lib/livingCoreTheme";

const baseSignals = {
  mode: "SIM" as const,
  riskLevel: "NORMAL" as const,
  regime: "UNKNOWN",
  regimeConfidence: null,
  connectionStatus: "connected" as const,
  fallbackMode: false,
  intelligenceHealth: "healthy" as const,
};

describe("livingCoreLiveModel", () => {
  it("normalizes regime strings", () => {
    expect(normalizeRegimeKey("TRENDING")).toBe("TRENDING_UP");
    expect(normalizeRegimeKey("trending_down")).toBe("TRENDING_DOWN");
    expect(normalizeRegimeKey("high volatility")).toBe("HIGH_VOLATILITY");
    expect(normalizeRegimeKey("Ranging")).toBe("RANGING");
    expect(normalizeRegimeKey("")).toBe("UNKNOWN");
  });

  it("floors vitality when disconnected so the core stays visibly alive", () => {
    const vitality = computeVitality({
      ...baseSignals,
      connectionStatus: "disconnected",
    });
    expect(vitality).toBeGreaterThanOrEqual(0.35);
    expect(vitalityBucket(vitality)).toBe("low");
  });

  it("boosts vitality with regime confidence", () => {
    const without = computeVitality({
      ...baseSignals,
      connectionStatus: "reconnecting",
    });
    const withConfidence = computeVitality({
      ...baseSignals,
      connectionStatus: "reconnecting",
      regimeConfidence: 0.9,
    });
    expect(withConfidence).toBeGreaterThan(without);
  });

  it("reduces agitation when vitality is low", () => {
    const healthy = buildVisualParamsFromSignals(modePalette("SIM"), baseSignals);
    const dormant = buildVisualParamsFromSignals(modePalette("SIM"), {
      ...baseSignals,
      connectionStatus: "disconnected",
      intelligenceHealth: "error",
    });
    expect(dormant.agitation).toBeLessThan(healthy.agitation);
    expect(dormant.particleOpacity).toBeLessThan(healthy.particleOpacity);
  });

  it("applies slower motion for REAL mode", () => {
    const sim = buildVisualParamsFromSignals(modePalette("SIM"), baseSignals);
    const real = buildVisualParamsFromSignals(modePalette("REAL"), {
      ...baseSignals,
      mode: "REAL",
    });
    expect(real.helixDrift).toBeLessThan(sim.helixDrift);
    expect(real.breatheSpeed).toBeLessThan(sim.breatheSpeed);
  });
});
