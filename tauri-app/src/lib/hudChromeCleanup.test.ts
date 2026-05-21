import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const commandHudSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/cockpit/CommandHud.tsx"),
  "utf8",
);
const nerveTapSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/cockpit/HudNerveTap.tsx"),
  "utf8",
);

describe("HUD chrome cleanup", () => {
  it("HUD chrome cleanup merges overflow into nerve tap", () => {
    expect(nerveTapSource).toContain("deck-overflow-menu");
    expect(nerveTapSource).toContain("onMenuClose");
    expect(commandHudSource).toContain("menu={");
    expect(commandHudSource).not.toContain("overflowRef");
  });

  it("CommandHud exposes contextual annex micro-hint", () => {
    expect(commandHudSource).toContain("resolveHudAnnexHintCopy");
    expect(commandHudSource).toContain("command-hud-annex-hint");
    expect(commandHudSource).toContain("metricsHintPulse");
  });

  it("hud hero layout no longer exposes vestigial secondary slot", () => {
    const layoutSource = readFileSync(
      join(dirname(fileURLToPath(import.meta.url)), "../lib/hudSignalLayout.ts"),
      "utf8",
    );
    expect(layoutSource).not.toMatch(/secondary:\s*null/);
    expect(layoutSource).not.toContain("secondary: HudContextualConfig");
  });
});
