import { describe, expect, it } from "vitest";

import {
  resolveBirthScreenPhaseHeader,
  resolveDeckPhaseHeader,
  resolveWizardPhaseHeader,
} from "@/lib/luminaPhasePresentation";

describe("luminaPhasePresentation", () => {
  it("maps wizard steps to centered phase headers", () => {
    expect(resolveWizardPhaseHeader("welcome").title).toBe("Welcome");
    expect(resolveWizardPhaseHeader("birth").title).toBe("Neural Genesis");
    expect(resolveWizardPhaseHeader("birth", true).status).toBe("Activation sequence engaged");
  });

  it("maps birth surfaces to phase headers", () => {
    expect(
      resolveBirthScreenPhaseHeader({
        genesisMode: true,
        missionMode: false,
        awakening: false,
        activating: false,
        interrupted: false,
        certificateFailed: false,
        stageStalledActive: false,
        milestones: [],
        phaseSubtitle: "",
      }).title,
    ).toBe("Neural Genesis");

    expect(
      resolveBirthScreenPhaseHeader({
        genesisMode: false,
        missionMode: true,
        awakening: false,
        activating: false,
        interrupted: false,
        certificateFailed: false,
        stageStalledActive: false,
        milestones: [{ id: "strategies", label: "Curriculum training", headline: "", state: "active" }],
        phaseSubtitle: "Training in progress",
      }).title,
    ).toBe("Curriculum training");
  });

  it("maps deck modes to command deck headers", () => {
    expect(resolveDeckPhaseHeader("SIM").title).toBe("SIM Operations");
    expect(resolveDeckPhaseHeader("REAL").title).toBe("REAL Operations");
  });
});
