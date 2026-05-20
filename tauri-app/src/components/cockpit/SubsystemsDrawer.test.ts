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
});
