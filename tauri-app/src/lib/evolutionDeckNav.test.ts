import { describe, expect, it } from "vitest";

import {
  EVOLUTION_OPS_SECTIONS,
  EVOLUTION_PRIMARY_TABS,
  evolutionOpsTabLabel,
  isEvolutionOpsTab,
  primaryEvolutionTabLabel,
} from "@/lib/evolutionDeckNav";

describe("evolutionDeckNav", () => {
  it("primary tabs contain only evolution hero", () => {
    expect(EVOLUTION_PRIMARY_TABS).toEqual(["evolution"]);
    expect(primaryEvolutionTabLabel("evolution")).toBe("Evolution Queue");
  });

  it("ops tabs are ppo and readiness", () => {
    expect(EVOLUTION_OPS_SECTIONS[0]?.tabs).toEqual(["ppo", "readiness"]);
    expect(isEvolutionOpsTab("ppo")).toBe(true);
    expect(isEvolutionOpsTab("evolution")).toBe(false);
    expect(evolutionOpsTabLabel("ppo")).toBe("PPO Evolution");
    expect(evolutionOpsTabLabel("readiness")).toBe("SIM Readiness");
  });
});
