import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const tierDoc = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../../../docs/lumina-deck-cinematic-tiers.md"),
  "utf8",
);
const cockpitCss = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../styles/cockpit.css"),
  "utf8",
);

describe("cinematic tier contract sync", () => {
  it("documents HUD organism center and annex deferral", () => {
    expect(tierDoc).toContain("HudOrganismCenter");
    expect(tierDoc).toContain("Performance annex");
  });

  it("documents StatusBar hud glass and REAL ambient mute", () => {
    expect(tierDoc).toContain("status-bar--glass");
    expect(tierDoc).toContain("REAL ambient mute");
    expect(tierDoc).toContain("0.08");
  });

  it("documents evolution directed tableau rules", () => {
    expect(tierDoc).toContain("enableZoom={false}");
    expect(tierDoc).toContain("hover tooltips");
  });

  it("documents Birth T1 activate deck and Living Core breath rules", () => {
    expect(tierDoc).toContain("Birth T1 activate deck");
    expect(tierDoc).toContain("Living Core breath");
    expect(tierDoc).toContain("--organism-envelope");
  });

  it("CSS implements T2 panel mode posture", () => {
    expect(cockpitCss).toContain(".mode-panel-real");
    expect(cockpitCss).toContain(".mode-panel-sim::after");
    expect(cockpitCss).toContain("command-hud-annex-hint");
  });
});
