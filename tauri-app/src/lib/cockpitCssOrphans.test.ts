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

  it("aligns pulseLanguage animation class with CSS or removes pulse-scan-sim", () => {
    const usesLegacy = pulseLanguage.includes("pulse-scan-sim");
    const cssDefinesLegacy = cockpitCss.includes(".pulse-scan-sim");
    expect(usesLegacy).toBe(cssDefinesLegacy);
    expect(pulseLanguage).toContain("presence-pulse-sim");
    expect(cockpitCss).toContain("presence-pulse-sim");
  });
});
