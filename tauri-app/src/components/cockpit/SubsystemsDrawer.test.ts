import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { drawerBadgeClass, pendingHighlightClass } from "@/lib/modePresentation";

describe("SubsystemsDrawer presentation", () => {
  it("uses gold pending highlight in REAL mode", () => {
    expect(pendingHighlightClass("REAL")).toContain("c9b896");
    expect(pendingHighlightClass("SIM")).toContain("amber");
  });

  it("uses mode-aware drawer badge colors", () => {
    expect(drawerBadgeClass("mode", "REAL")).toContain("real-chrome-accent");
    expect(drawerBadgeClass("warn", "REAL")).toContain("amber");
    expect(drawerBadgeClass("mode", "SIM")).toContain("amber");
  });

  it("portals the airlock out of Command Deck glass", () => {
    const source = readFileSync(
      join(dirname(fileURLToPath(import.meta.url)), "SubsystemsDrawer.tsx"),
      "utf8",
    );
    expect(source).toContain("createPortal");
    expect(source).toContain("getLuminaOverlayRoot");
  });
});
