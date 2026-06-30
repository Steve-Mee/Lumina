import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const birthMissionControlSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "./BirthMissionControl.tsx"),
  "utf8",
);

const birthStageIntelSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "./BirthStageIntelColumn.tsx"),
  "utf8",
);

const birthAdvancedPanelSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "./BirthAdvancedPanel.tsx"),
  "utf8",
);

describe("BirthMissionControl", () => {
  it("uses a compact status-only body without page scroll on body root", () => {
    expect(birthMissionControlSource).toContain("birth-mission-control__body");
    expect(birthMissionControlSource).toMatch(
      /birth-mission-control__body min-h-0 flex-1 overflow-hidden/,
    );
    expect(birthMissionControlSource).not.toContain("birth-mission-control__scroll");
    expect(birthMissionControlSource).not.toContain("birth-mission-control__primary");
    expect(birthMissionControlSource).toContain("BirthMetricsStrip");
    expect(birthMissionControlSource).toContain("embedded");
  });

  it("uses a two-column KPI grid for the narrower status column", () => {
    expect(birthMissionControlSource).toMatch(/birth-kpi-grid[\s\S]*grid-cols-2/);
    expect(birthMissionControlSource).not.toContain("lg:grid-cols-4");
  });

  it("does not render collapsible stage details or advanced panels", () => {
    expect(birthMissionControlSource).not.toContain("BirthStageDetailsPanel");
    expect(birthMissionControlSource).not.toContain("BirthStageScorecard");
    expect(birthMissionControlSource).not.toContain("BirthAdvancedPanel");
    expect(birthMissionControlSource).not.toContain("BirthRemediationBar");
  });

  it("keeps blocker alert in the status column", () => {
    expect(birthMissionControlSource).toContain("BirthBlockerAlert");
  });
});

describe("BirthStageIntelColumn", () => {
  it("always renders scorecard when progress has stage data", () => {
    expect(birthStageIntelSource).toContain("BirthStageScorecard");
    expect(birthStageIntelSource).toContain("extractStageScorecard");
    expect(birthStageIntelSource).toMatch(/showContent && scorecard \?/);
    expect(birthStageIntelSource).not.toContain("ChevronDown");
  });

  it("hosts remediation and controlled advanced content", () => {
    expect(birthStageIntelSource).toContain("BirthRemediationBar");
    expect(birthStageIntelSource).toContain("BirthAdvancedPanel");
    expect(birthStageIntelSource).toContain("controlled={running}");
    expect(birthAdvancedPanelSource).toContain("if (!openSection)");
    expect(birthAdvancedPanelSource).toContain("birth-advanced-panel__content");
  });
});
