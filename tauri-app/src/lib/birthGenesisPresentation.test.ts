import { describe, expect, it } from "vitest";

import {
  isBenignBirthStatusMessage,
  resolveGenesisDeckPresentation,
  sanitizeBirthOperatorMessage,
} from "@/lib/birthGenesisPresentation";

describe("isBenignBirthStatusMessage", () => {
  it("treats idle / post-wipe backend copy as non-attention", () => {
    expect(isBenignBirthStatusMessage("Birth Phase nog niet gestart")).toBe(true);
    expect(isBenignBirthStatusMessage("not started")).toBe(true);
    expect(isBenignBirthStatusMessage("not_started")).toBe(true);
    expect(isBenignBirthStatusMessage("All birth data wiped — ready for a clean start.")).toBe(
      true,
    );
    expect(isBenignBirthStatusMessage("")).toBe(true);
  });

  it("does not swallow real failures", () => {
    expect(isBenignBirthStatusMessage("Connecting to NinjaTrader Fabric failed")).toBe(false);
    expect(isBenignBirthStatusMessage("UnboundLocalError: cannot access local variable")).toBe(
      false,
    );
  });
});

describe("sanitizeBirthOperatorMessage", () => {
  it("maps Python UnboundLocalError to operator language", () => {
    const r = sanitizeBirthOperatorMessage(
      "UnboundLocalError: cannot access local variable 'write_birth_progress' where it is not associated with a value",
    );
    expect(r.operator).toMatch(/internal error/i);
    expect(r.technical).toMatch(/UnboundLocalError/);
    expect(r.operator).not.toMatch(/write_birth_progress/);
  });

  it("passes through human fabric messages", () => {
    const msg =
      "Connecting to NinjaTrader Fabric failed or still not GREEN. Start NinjaTrader.";
    const r = sanitizeBirthOperatorMessage(msg);
    expect(r.operator).toContain("NinjaTrader Fabric");
    expect(r.technical).toBeNull();
  });

  it("handles empty and benign idle", () => {
    expect(sanitizeBirthOperatorMessage("").operator).toBe("");
    expect(sanitizeBirthOperatorMessage(null).operator).toBe("");
    expect(sanitizeBirthOperatorMessage("Birth Phase nog niet gestart").operator).toBe("");
  });
});

describe("resolveGenesisDeckPresentation", () => {
  it("idle clean → activate + awaiting copy", () => {
    const p = resolveGenesisDeckPresentation({
      activating: false,
      sessionInterrupted: false,
      checkpointAvailable: false,
    });
    expect(p.ctaMode).toBe("activate");
    expect(p.toolbarSubtitle).toMatch(/awaiting activation/i);
    expect(p.phaseStatus).toBe("Awaiting activation");
    expect(p.banner.tone).toBe("info");
    expect(p.banner.title).toMatch(/What we need from you/i);
    expect(p.detail).toBeNull();
    expect(p.hasAttention).toBe(false);
    expect(p.showRecoveryTab).toBe(false);
    expect(p.showStartCleanSecondary).toBe(false);
  });

  it("post-wipe idle message does not look like attention / retry", () => {
    const p = resolveGenesisDeckPresentation({
      activating: false,
      sessionInterrupted: false,
      checkpointAvailable: false,
      decisionMode: false,
      statusMessage: "Birth Phase nog niet gestart",
      statusError: null,
      error: null,
      pollError: null,
    });
    expect(p.ctaMode).toBe("activate");
    expect(p.hasAttention).toBe(false);
    expect(p.showRecoveryTab).toBe(false);
    expect(p.showStartCleanSecondary).toBe(false);
    expect(p.detail).toBeNull();
    expect(p.banner.tone).toBe("info");
    expect(p.banner.title).toMatch(/What we need from you/i);
    expect(p.toolbarSubtitle).toMatch(/awaiting activation/i);
    expect(p.phaseStatus).toBe("Awaiting activation");
    // Never dual narrative: needs attention + not started
    expect(p.toolbarSubtitle).not.toMatch(/needs attention/i);
    expect(p.banner.title).not.toMatch(/needs attention/i);
  });

  it("interrupted without checkpoint → decision + Recovery surface (no footer thrash)", () => {
    const p = resolveGenesisDeckPresentation({
      activating: false,
      sessionInterrupted: true,
      checkpointAvailable: false,
    });
    expect(p.ctaMode).toBe("decision");
    expect(p.toolbarSubtitle).toMatch(/choose next step/i);
    expect(p.phaseStatus).toMatch(/stopped/i);
    expect(p.banner.tone).toBe("warn");
    expect(p.banner.title).toMatch(/Recovery/i);
    expect(p.showRecoveryTab).toBe(true);
    expect(p.preferRecoveryTab).toBe(true);
    // Start clean lives under Recovery — not secondary under Activate.
    expect(p.showStartCleanSecondary).toBe(false);
    // No dual charter detail when decision owns the story.
    expect(p.detail).toBeNull();
  });

  it("checkpoint → decision + prefer Recovery (continue path)", () => {
    const p = resolveGenesisDeckPresentation({
      activating: false,
      sessionInterrupted: true,
      checkpointAvailable: true,
    });
    expect(p.ctaMode).toBe("decision");
    expect(p.banner.body).toMatch(/checkpoint|Continue|Recovery/i);
    expect(p.showRecoveryTab).toBe(true);
    expect(p.preferRecoveryTab).toBe(true);
  });

  it("engine error without interrupt → retry + recovery preferred", () => {
    const p = resolveGenesisDeckPresentation({
      activating: false,
      sessionInterrupted: false,
      checkpointAvailable: false,
      decisionMode: true,
      error:
        "UnboundLocalError: cannot access local variable 'write_birth_progress' where it is not associated with a value",
    });
    expect(p.ctaMode).toBe("retry");
    expect(p.hasAttention).toBe(true);
    expect(p.showRecoveryTab).toBe(true);
    expect(p.preferRecoveryTab).toBe(true);
    expect(p.phaseStatus).toMatch(/needs attention/i);
    expect(p.toolbarSubtitle).toMatch(/needs attention/i);
    // Decision surface (decisionMode) owns detail — Recovery tab shows operator line.
    expect(p.detail).toBeNull();
    expect(p.banner.tone).toBe("warn");
    expect(p.toolbarSubtitle).not.toMatch(/awaiting activation/i);
  });

  it("engine error without decisionMode → retry + charter detail", () => {
    const p = resolveGenesisDeckPresentation({
      activating: false,
      sessionInterrupted: false,
      checkpointAvailable: false,
      decisionMode: false,
      error:
        "UnboundLocalError: cannot access local variable 'write_birth_progress' where it is not associated with a value",
    });
    expect(p.ctaMode).toBe("retry");
    expect(p.detail?.operatorLine).toMatch(/internal error/i);
    expect(p.detail?.technicalLine).toMatch(/UnboundLocalError/);
    expect(p.showRecoveryTab).toBe(true);
  });

  it("activating wins over error copy", () => {
    const p = resolveGenesisDeckPresentation({
      activating: true,
      sessionInterrupted: true,
      checkpointAvailable: true,
      error: "previous fail",
    });
    expect(p.ctaMode).not.toBe("decision");
    expect(p.toolbarSubtitle).toMatch(/activation in progress/i);
    expect(p.detail).toBeNull();
    expect(p.showRecoveryTab).toBe(false);
  });
});
