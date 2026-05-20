import { describe, expect, it } from "vitest";

import {
  birthEffectParams,
  birthClearTimeoutMs,
  birthScaleFactor,
  calmMode,
  dustParticleCount,
  evolutionDustDriftScale,
  evolutionPalette,
  fitnessGlow,
  nodeRadius,
  truncateHash,
} from "@/lib/evolutionArenaTheme";

describe("evolutionArenaTheme", () => {
  it("calmMode is true only for REAL", () => {
    expect(calmMode("SIM")).toBe(false);
    expect(calmMode("REAL")).toBe(true);
  });

  it("evolutionPalette differs by mode", () => {
    expect(evolutionPalette("SIM").primary).toBe("#00f0ff");
    expect(evolutionPalette("REAL").primary).toBe("#94a3b8");
  });

  it("fitnessGlow tiers by fitness threshold", () => {
    const high = fitnessGlow(0.75, "SIM");
    const mid = fitnessGlow(0.6, "SIM");
    const low = fitnessGlow(0.4, "SIM");
    expect(high.core).toBe("#00f0ff");
    expect(mid.core).toBe("#a78bfa");
    expect(low.core).toBe("#64748b");
    expect(fitnessGlow(0.75, "REAL").emissiveIntensity).toBeLessThan(
      fitnessGlow(0.75, "SIM").emissiveIntensity,
    );
  });

  it("birthEffectParams scales with quality and mode", () => {
    const sim = birthEffectParams("SIM", "balanced", 40, 1);
    const real = birthEffectParams("REAL", "balanced", 40, 1);
    expect(real.durationS).toBeGreaterThan(sim.durationS);
    expect(birthEffectParams("SIM", "low", 40, 0.5).particleCount).toBeLessThan(
      sim.particleCount,
    );
  });

  it("birthClearTimeoutMs is longer in REAL", () => {
    expect(birthClearTimeoutMs("REAL")).toBeGreaterThan(birthClearTimeoutMs("SIM"));
  });

  it("dustParticleCount disabled for REAL and low quality", () => {
    expect(dustParticleCount("REAL", "high")).toBe(0);
    expect(dustParticleCount("SIM", "low")).toBe(0);
    expect(dustParticleCount("SIM", "balanced")).toBeGreaterThan(0);
  });

  it("evolutionDustDriftScale is SIM-only", () => {
    expect(evolutionDustDriftScale("SIM")).toBeGreaterThan(0);
    expect(evolutionDustDriftScale("REAL")).toBe(0);
  });

  it("nodeRadius scales with fitness", () => {
    expect(nodeRadius(1)).toBeGreaterThan(nodeRadius(0));
  });

  it("birthScaleFactor ramps new nodes from small to full", () => {
    expect(birthScaleFactor(false, false, 0, 0.8)).toBe(1);
    expect(birthScaleFactor(true, true, 0, 0.8)).toBe(1);
    const mid = birthScaleFactor(true, false, 0.4, 0.8);
    expect(mid).toBeGreaterThan(0.15);
    expect(mid).toBeLessThan(1);
  });

  it("truncateHash shortens long hashes", () => {
    const hash = "a".repeat(64);
    expect(truncateHash(hash)).toContain("…");
    expect(truncateHash("short")).toBe("short");
  });
});
