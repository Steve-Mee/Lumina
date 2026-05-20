import { describe, expect, it } from "vitest";

import {
  ANALYTICS_CENTER_TABS,
  ANALYTICS_RIGHT_TABS,
  analyticsAnnexClass,
  analyticsAnnexCssVars,
  isAnalyticsCenterTab,
  isAnalyticsRightTab,
} from "@/lib/analyticsAnnexPresentation";

describe("analyticsAnnexPresentation", () => {
  it("classifies center annex tabs", () => {
    expect(isAnalyticsCenterTab("ppo")).toBe(true);
    expect(isAnalyticsCenterTab("readiness")).toBe(true);
    expect(isAnalyticsCenterTab("evolution")).toBe(false);
    expect([...ANALYTICS_CENTER_TABS]).toEqual(["ppo", "readiness"]);
  });

  it("classifies right annex tabs including performance", () => {
    expect(isAnalyticsRightTab("performance")).toBe(true);
    expect(isAnalyticsRightTab("monitor")).toBe(true);
    expect(isAnalyticsRightTab("brief")).toBe(false);
    expect(ANALYTICS_RIGHT_TABS).toContain("performance");
    expect(ANALYTICS_RIGHT_TABS).toContain("admin");
  });

  it("exposes annex class and css vars", () => {
    expect(analyticsAnnexClass()).toBe("analytics-annex");
    const simVars = analyticsAnnexCssVars("SIM") as Record<string, string>;
    const realVars = analyticsAnnexCssVars("REAL") as Record<string, string>;
    expect(simVars["--annex-fg"]).toBeTruthy();
    expect(simVars["--annex-bg"]).toBeTruthy();
    expect(realVars["--annex-fg"]).not.toBe(simVars["--annex-fg"]);
  });
});
