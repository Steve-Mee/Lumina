import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

describe("systemsGoWindow", () => {
  it("defines compact Systems Go size below deck min and restore to conf deck size", async () => {
    const { SYSTEMS_GO_WINDOW, DECK_WINDOW } = await import("./systemsGoWindow");
    expect(SYSTEMS_GO_WINDOW.width).toBeLessThan(DECK_WINDOW.minWidth);
    expect(SYSTEMS_GO_WINDOW.height).toBeGreaterThan(500);
    expect(DECK_WINDOW.width).toBe(1600);
    expect(DECK_WINDOW.height).toBe(1000);
    expect(DECK_WINDOW.minWidth).toBe(1280);
    expect(DECK_WINDOW.minHeight).toBe(720);
  });

  it("ColdStart applies compact size on mount and restores before leaving cover", () => {
    const cold = readFileSync(
      join(root, "components/startup/ColdStartReadiness.tsx"),
      "utf8",
    );
    expect(cold).toContain("applySystemsGoWindowSize");
    expect(cold).toContain("restoreDeckWindowSize");
    // Restore before setNtStartupResolved so Genesis lands full-size
    expect(cold).toMatch(
      /restoreDeckWindowSize\(\)[\s\S]*setNtStartupResolved\(true\)/,
    );
  });

  it("window helper is Tauri-only and never kills NT", () => {
    const src = readFileSync(join(root, "lib/systemsGoWindow.ts"), "utf8");
    expect(src).toContain("isTauri");
    expect(src).toContain("setMinSize");
    expect(src).toContain("setSize");
    expect(src).toContain("center");
    expect(src).not.toContain("closeNinjaTrader");
    expect(src).not.toContain("taskkill");
  });
});
