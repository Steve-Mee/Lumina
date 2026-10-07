import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { MATURATION_STEPS } from "@/components/birth/GenesisMaturityLadder";
import {
  ORGANISM_MORPHOLOGY,
  organismHasAnatomy,
  resolveOrganismMorphology,
} from "@/lib/organism/phaseMorphology";

const morphologySource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "phaseMorphology.ts"),
  "utf8",
);

describe("phaseMorphology visual contract", () => {
  it("covers every maturation step", () => {
    for (const step of MATURATION_STEPS) {
      expect(ORGANISM_MORPHOLOGY[step.id]).toBeDefined();
      expect(ORGANISM_MORPHOLOGY[step.id].evolution).toBeGreaterThan(0);
    }
  });

  it("keeps Birth as a DNA zygote without anatomy", () => {
    const birth = ORGANISM_MORPHOLOGY.birth;
    expect(birth.eyeOpen).toBe(0);
    expect(birth.vaneSpan).toBe(0);
    expect(birth.bodyOpacity).toBe(0);
    expect(birth.armor).toBe(0);
    expect(birth.filamentCount).toBe(0);
    expect(organismHasAnatomy(birth)).toBe(false);
  });

  it("grows evolution monotonically along the ladder", () => {
    const values = MATURATION_STEPS.map((step) => ORGANISM_MORPHOLOGY[step.id].evolution);
    for (let i = 1; i < values.length; i++) {
      expect(values[i]).toBeGreaterThan(values[i - 1]);
    }
  });

  it("opens eyes at Awakening and unfurls vanes by Playground", () => {
    expect(ORGANISM_MORPHOLOGY.awakening.eyeOpen).toBeGreaterThan(0.5);
    expect(ORGANISM_MORPHOLOGY.playground.vaneSpan).toBeGreaterThan(
      ORGANISM_MORPHOLOGY.awakening.vaneSpan,
    );
    expect(ORGANISM_MORPHOLOGY.proving_ground.armor).toBeGreaterThan(0.7);
    expect(ORGANISM_MORPHOLOGY.real.vaneSpan).toBe(1);
    expect(organismHasAnatomy(ORGANISM_MORPHOLOGY.real)).toBe(true);
  });

  it("REAL trading mode selects the adult morph on any phase", () => {
    expect(resolveOrganismMorphology("birth", "REAL")).toEqual(ORGANISM_MORPHOLOGY.real);
    expect(resolveOrganismMorphology("playground", "SIM")).toEqual(
      ORGANISM_MORPHOLOGY.playground,
    );
  });

  it("stays a visual module with no trading or wipe imports", () => {
    expect(morphologySource).not.toContain("maturationClient");
    expect(morphologySource).not.toContain("fetch(");
    expect(morphologySource).not.toContain("lumina_core");
    expect(morphologySource).not.toContain("orderpath");
    expect(morphologySource).not.toContain("PromotionGate");
  });
});
