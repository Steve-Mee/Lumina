import { describe, expect, it } from "vitest";

import {
  citadelFieldEnvelopeScale,
  commandGhostClass,
  commandPrimaryClass,
  modeAccentCssVars,
  modeLabelClass,
  modeMotionScale,
  modePanelClass,
  modeSpring,
  modeTextTier2Class,
  modeTitleClass,
  modeTransition,
  modeValueClass,
  drawerBadgeClass,
  modeSwitchTooltip,
  reasoningSpineTitleClass,
  distressPanelClass,
  pendingHighlightClass,
  realDialogBodyClass,
  realDialogTitleClass,
  realOverlayClass,
  realOverlayPanelClass,
  warnOverlayClass,
  warnOverlayPanelClass,
} from "@/lib/modePresentation";

describe("modePresentation", () => {
  it("modeMotionScale is lower in REAL", () => {
    expect(modeMotionScale("SIM")).toBe(1);
    expect(modeMotionScale("REAL")).toBeLessThan(1);
  });

  it("modePanelClass differs by mode", () => {
    expect(modePanelClass("SIM")).toBe("mode-panel-sim");
    expect(modePanelClass("REAL")).toBe("mode-panel-real");
  });

  it("modeAccentCssVars exposes deck tokens", () => {
    const sim = modeAccentCssVars("SIM") as Record<string, string>;
    const real = modeAccentCssVars("REAL") as Record<string, string>;
    expect(sim["--deck-accent"]).toContain("mode-sim-accent");
    expect(real["--deck-accent"]).toContain("mode-real-accent");
    expect(sim["--deck-accent"]).not.toBe(real["--deck-accent"]);
  });

  it("tier text classes desaturate REAL accents", () => {
    expect(modeTitleClass("SIM")).toContain("cyan");
    expect(modeTitleClass("REAL")).toContain("slate");
    expect(modeLabelClass("REAL")).toContain("slate");
    expect(modeValueClass("SIM")).toContain("cyan");
    expect(modeValueClass("REAL")).toContain("c9b896");
  });

  it("modeTextTier2Class maps semantic tiers", () => {
    expect(modeTextTier2Class("SIM")).toContain("mode-text-tier2-sim");
    expect(modeTextTier2Class("REAL", true)).toBe("mode-text-tier2-muted");
  });

  it("citadelFieldEnvelopeScale boosts SIM breath amplitude", () => {
    expect(citadelFieldEnvelopeScale("SIM")).toBeGreaterThan(citadelFieldEnvelopeScale("REAL"));
  });

  it("modeSpring softens stiffness in REAL", () => {
    const sim = modeSpring("SIM");
    const real = modeSpring("REAL");
    expect(real.stiffness).toBeLessThan(sim.stiffness);
  });

  it("command button classes differ by mode", () => {
    expect(commandPrimaryClass("SIM")).toContain("cyan");
    expect(commandPrimaryClass("REAL")).toContain("slate");
    expect(commandGhostClass("SIM")).toContain("cyan");
    expect(commandGhostClass("REAL")).toContain("slate");
  });

  it("modeTransition returns zero duration when reduced motion", () => {
    expect(modeTransition("SIM", true)).toEqual({ duration: 0 });
    expect(modeTransition("SIM", false)).toBeTruthy();
  });

  it("real overlay helpers use slate/gold not alarm amber", () => {
    expect(realOverlayClass()).toContain("slate");
    expect(realOverlayPanelClass()).toContain("lumina-glass--overlay");
    expect(realDialogTitleClass()).toContain("slate");
    expect(realDialogBodyClass()).toContain("slate");
  });

  it("warn overlay helpers use status-warn tokens", () => {
    expect(warnOverlayClass()).toContain("status-warn");
    expect(warnOverlayPanelClass()).toContain("lumina-glass--overlay");
  });

  it("reasoningSpineTitleClass uses gold in REAL and cyan in SIM", () => {
    expect(reasoningSpineTitleClass("REAL")).toContain("c9b896");
    expect(reasoningSpineTitleClass("SIM")).toContain("cyan");
  });

  it("distressPanelClass uses glass overlay tokens", () => {
    expect(distressPanelClass()).toContain("lumina-glass--overlay");
    expect(distressPanelClass("error")).toContain("ef4444");
  });

  it("pendingHighlightClass uses gold in REAL and amber in SIM", () => {
    expect(pendingHighlightClass("REAL")).toContain("c9b896");
    expect(pendingHighlightClass("SIM")).toContain("amber");
  });

  it("drawerBadgeClass and modeSwitchTooltip are mode-aware", () => {
    expect(drawerBadgeClass("mode", "REAL")).toContain("real-chrome-accent");
    expect(drawerBadgeClass("warn", "SIM")).toContain("amber");
    expect(modeSwitchTooltip("REAL")).toBe("Capital Protection");
    expect(modeSwitchTooltip("SIM")).toBe("Hyper Evolution");
  });
});
