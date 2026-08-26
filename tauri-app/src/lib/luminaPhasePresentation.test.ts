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

  it("prioritizes launching over paused decision copy", () => {
    const header = resolveBirthScreenPhaseHeader({
      genesisMode: true,
      missionMode: false,
      awakening: false,
      activating: true,
      launching: true,
      decisionMode: true,
      interrupted: true,
      certificateFailed: false,
      stageStalledActive: false,
      milestones: [],
      phaseSubtitle: "",
    });
    expect(header.title).toBe("Starting Birth");
    expect(header.status).toMatch(/Verifying systems/i);
  });

  it("maps decision mode to stopped choose-next-step copy", () => {
    const header = resolveBirthScreenPhaseHeader({
      genesisMode: true,
      missionMode: false,
      awakening: false,
      activating: false,
      decisionMode: true,
      interrupted: true,
      certificateFailed: false,
      stageStalledActive: false,
      milestones: [],
      phaseSubtitle: "",
    });
    expect(header.status).toBe("Birth stopped — choose next step");
  });

  it("prefers genesis presentation SSOT over dual idle/stopped narratives", () => {
    const header = resolveBirthScreenPhaseHeader({
      genesisMode: true,
      missionMode: false,
      awakening: false,
      activating: false,
      decisionMode: true,
      interrupted: false,
      genesisAttention: true,
      genesisPhaseStatus: "Birth needs attention — choose next step",
      genesisPhaseTone: "amber",
      certificateFailed: false,
      stageStalledActive: false,
      milestones: [],
      phaseSubtitle: "",
    });
    expect(header.status).toBe("Birth needs attention — choose next step");
    expect(header.tone).toBe("amber");
  });

  it("maps deck modes to command deck headers", () => {
    expect(resolveDeckPhaseHeader("SIM").title).toBe("SIM Operations");
    expect(resolveDeckPhaseHeader("REAL").title).toBe("REAL Operations");
  });
});
