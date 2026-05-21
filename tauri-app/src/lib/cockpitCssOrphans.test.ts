import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const cockpitCss = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../styles/cockpit.css"),
  "utf8",
);

const pulseLanguage = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "./pulseLanguage.ts"),
  "utf8",
);

describe("cockpit.css orphan selectors", () => {
  it("does not define removed command-hud-engine-dot rules", () => {
    expect(cockpitCss).not.toContain(".command-hud-engine-dot--sim");
  });

  it("does not define removed presence-strip rules", () => {
    expect(cockpitCss).not.toContain(".presence-strip[data-mode");
  });

  it("does not define removed deck-status-rail rules", () => {
    expect(cockpitCss).not.toContain(".deck-status-rail");
  });

  it("does not define removed deck-welcome-banner rules", () => {
    expect(cockpitCss).not.toContain(".deck-welcome-banner--sim");
  });

  it("does not define removed status-warn-banner rules", () => {
    expect(cockpitCss).not.toContain(".status-warn-banner");
  });

  it("aligns pulseLanguage with CSS presence dot selectors", () => {
    expect(pulseLanguage).toContain("presenceDotClass");
    expect(pulseLanguage).toContain("livingCoreHaloAnimationClass");
    expect(pulseLanguage).not.toContain("presenceDotAnimationClass");
    expect(pulseLanguage).not.toContain("immersiveHaloClass");
    expect(cockpitCss).toContain("presence-pulse-sim");
    expect(cockpitCss).toContain("presence-breathe-real");
  });

  it("defines birth wizard styles in birthWizard.css not birthPhase monitor sheet", () => {
    const birthPhaseCss = readFileSync(
      join(dirname(fileURLToPath(import.meta.url)), "../styles/birthPhase.css"),
      "utf8",
    );
    const birthWizardCss = readFileSync(
      join(dirname(fileURLToPath(import.meta.url)), "../styles/birthWizard.css"),
      "utf8",
    );
    expect(birthWizardCss).toContain(".birth-launch-btn");
    expect(birthPhaseCss).not.toContain(".birth-launch-btn");
    expect(birthPhaseCss).toContain(".birth-phase-pulse");
    expect(birthPhaseCss).toContain(".birth-phase-helix-stage");
    expect(birthPhaseCss).toContain("overflow-x: hidden");
    expect(birthPhaseCss).toContain(".birth-milestone--drawer");
  });
});
