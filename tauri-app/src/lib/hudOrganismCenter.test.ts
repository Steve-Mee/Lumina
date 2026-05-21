import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const commandHudSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/cockpit/CommandHud.tsx"),
  "utf8",
);
const organismCenterSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/cockpit/HudOrganismCenter.tsx"),
  "utf8",
);
const cockpitCss = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../styles/cockpit.css"),
  "utf8",
);

describe("HudOrganismCenter contract", () => {
  it("CommandHud renders organism pulse instead of labeled metric tiles", () => {
    expect(commandHudSource).toContain("HudOrganismCenter");
    expect(commandHudSource).not.toContain("HudSignalArc");
    expect(commandHudSource).not.toMatch(/<HudSignal[\s/>]/);
  });

  it("organism center defers labeled readout to hover/focus", () => {
    expect(organismCenterSource).toContain("hud-organism-center__readout");
    expect(organismCenterSource).toContain("onMouseEnter");
    expect(organismCenterSource).toContain("useOrganismEnvelope");
  });

  it("CommandHud passes hero readout to PresenceRail for rail deferral", () => {
    expect(commandHudSource).toContain("heroReadout={heroReadout}");
    expect(commandHudSource).toContain('heroLayout.heroPrimary === "fortress"');
  });

  it("organism center opens Performance annex on activate", () => {
    expect(organismCenterSource).toContain("onActivate");
    expect(commandHudSource).toContain('setActiveRightTab("performance")');
  });

  it("cockpit CSS defines organism center pulse layer", () => {
    expect(cockpitCss).toContain(".hud-organism-center__pulse");
    expect(cockpitCss).toContain("--hud-pulse-fill");
  });
});
