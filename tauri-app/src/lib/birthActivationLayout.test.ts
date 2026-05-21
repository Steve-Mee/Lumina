import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const birthWizardCssSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../styles/birthWizard.css"),
  "utf8",
);

const onboardingCssSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../styles/onboarding.css"),
  "utf8",
);

function cssBlock(source: string, selector: string): string {
  const match = source.match(
    new RegExp(`${selector.replace(".", "\\.")}\\s*\\{[\\s\\S]*?\\}`, "m"),
  );
  return match?.[0] ?? "";
}

describe("birth activation layout CSS", () => {
  it("uses flex-fill screen and grid stack with 2/3 helix and 1/3 genesis rows", () => {
    const screen = cssBlock(birthWizardCssSource, ".birth-activation-screen--anchored");
    expect(screen).toContain("position: relative");
    expect(screen).not.toContain("position: absolute");
    expect(screen).not.toContain("inset: 0");
    expect(screen).toContain("display: flex");
    expect(screen).toContain("flex: 1");
    expect(screen).toContain("flex-direction: column");

    const stack = cssBlock(birthWizardCssSource, ".birth-activation-stack");
    expect(stack).toContain("display: grid");
    expect(stack).toContain("grid-template-rows: minmax(0, 2fr) minmax(0, 1fr)");
    expect(stack).toContain("height: 100%");
    expect(stack).not.toContain("justify-content: flex-end");
    expect(stack).not.toContain("min-height: calc(100dvh");

    const helixArena = cssBlock(birthWizardCssSource, ".birth-activation-helix-arena");
    expect(helixArena).toContain("min-height: 0");
    expect(helixArena).toContain("grid-row: 1");
    expect(helixArena).toContain("overflow: hidden");
    expect(helixArena).toContain("isolation: isolate");
  });

  it("pins deck to bottom row with 2/3 width and centered genesis content", () => {
    expect(birthWizardCssSource).not.toMatch(/\.birth-activation-deck[\s\S]*margin-top: auto/);
    expect(birthWizardCssSource).toMatch(/\.birth-activation-deck[\s\S]*margin-bottom: 0/);
    expect(birthWizardCssSource).not.toMatch(/\.birth-activation-deck[\s\S]*max-height: min\(38dvh/);
    expect(birthWizardCssSource).not.toMatch(/\.birth-activation-deck[\s\S]*align-self: center/);
    expect(birthWizardCssSource).toMatch(/\.birth-activation-deck[\s\S]*grid-row: 2/);
    expect(birthWizardCssSource).toMatch(/\.birth-activation-deck[\s\S]*width: min\(66\.666vw, 100%\)/);
    expect(birthWizardCssSource).toMatch(/\.birth-activation-deck[\s\S]*justify-self: center/);
    expect(birthWizardCssSource).toMatch(
      /\.birth-activation-deck-inner[\s\S]*text-align: center/,
    );
    expect(birthWizardCssSource).toMatch(
      /\.birth-activation-deck-inner[\s\S]*justify-content: flex-start/,
    );
  });

  it("wizard birth column and viewport anchor motion area", () => {
    const column = cssBlock(onboardingCssSource, ".onboarding-birth-column");
    expect(column).toContain("grid-template-rows: auto minmax(0, 1fr)");

    const viewport = cssBlock(onboardingCssSource, ".onboarding-birth-viewport");
    expect(viewport).toContain("position: relative");
    expect(viewport).toContain("min-height: 0");
    expect(viewport).toContain("display: flex");
    expect(viewport).toContain("flex-direction: column");
    expect(viewport).not.toContain("height: 100%");
  });

  it("soft-fades helix slot and allows deck-only scroll", () => {
    expect(birthWizardCssSource).toMatch(/\.birth-activation-screen[\s\S]*overflow-x: clip/);
    expect(birthWizardCssSource).toMatch(/\.birth-activation-helix-slot[\s\S]*mask-image: linear-gradient/);
    expect(birthWizardCssSource).toMatch(/\.birth-activation-helix-slot[\s\S]*overflow: hidden/);
    expect(birthWizardCssSource).toContain(".birth-activation-helix-slot::before");
    expect(birthWizardCssSource).toMatch(/\.birth-activation-deck[\s\S]*overflow-y: auto/);
    expect(birthWizardCssSource).toMatch(/\.birth-activation-deck[\s\S]*overscroll-behavior: contain/);
  });
});
