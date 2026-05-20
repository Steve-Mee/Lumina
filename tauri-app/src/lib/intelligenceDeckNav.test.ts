import { describe, expect, it } from "vitest";

import {
  INTELLIGENCE_PRIMARY_TABS,
  isOpsTab,
  opsTabLabel,
  resolveOpsSections,
} from "@/lib/intelligenceDeckNav";

describe("intelligenceDeckNav", () => {
  it("primary tabs are brief and performance only", () => {
    expect([...INTELLIGENCE_PRIMARY_TABS]).toEqual(["brief", "performance"]);
  });

  it("isOpsTab classifies ops vs primary tabs", () => {
    expect(isOpsTab("monitor")).toBe(true);
    expect(isOpsTab("liveActivity")).toBe(true);
    expect(isOpsTab("evolutionApprovals")).toBe(true);
    expect(isOpsTab("brief")).toBe(false);
    expect(isOpsTab("performance")).toBe(false);
  });

  it("opsTabLabel returns compact menu labels", () => {
    expect(opsTabLabel("monitor")).toBe("Monitor");
    expect(opsTabLabel("liveActivity")).toBe("Activity");
    expect(opsTabLabel("evolutionApprovals")).toBe("Approvals");
    expect(opsTabLabel("realOps")).toBe("REAL Ops");
  });

  it("resolveOpsSections includes Capital in REAL mode", () => {
    const realSections = resolveOpsSections("REAL");
    expect(realSections.some((section) => section.id === "real")).toBe(true);
    expect(
      realSections.flatMap((section) => section.tabs),
    ).toContain("realOps");
  });

  it("resolveOpsSections excludes Capital in SIM mode", () => {
    const simSections = resolveOpsSections("SIM");
    expect(simSections.some((section) => section.id === "real")).toBe(false);
    expect(
      simSections.flatMap((section) => section.tabs),
    ).not.toContain("realOps");
  });
});
