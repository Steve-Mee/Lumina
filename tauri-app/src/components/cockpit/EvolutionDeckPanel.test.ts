import { describe, expect, it } from "vitest";

import { EVOLUTION_DECK_TAB_SUBTITLES } from "@/components/cockpit/EvolutionDeckPanel";

describe("EvolutionDeckPanel", () => {
  it("defines subtitles for center deck tabs", () => {
    expect(EVOLUTION_DECK_TAB_SUBTITLES.evolution).toContain("mutation");
    expect(EVOLUTION_DECK_TAB_SUBTITLES.ppo).toContain("policy evolution");
    expect(EVOLUTION_DECK_TAB_SUBTITLES.readiness).toContain("SIM");
  });});
