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
  it("uses a constrained body with internal panel scroll (no page scroll)", () => {
    expect(birthMissionControlSource).toContain("birth-mission-control__body");
    expect(birthMissionControlSource).toMatch(
      /birth-mission-control__body min-h-0 flex-1 overflow-x-hidden overflow-y-auto/,
    );
    expect(birthMissionControlSource).not.toContain("birth-mission-control__scroll");
    expect(birthMissionControlSource).not.toContain("birth-mission-control__primary");
    expect(birthMissionControlSource).toContain("BirthMetricsStrip");
    expect(birthMissionControlSource).toContain("embedded");
  });

  it("uses vault-grade toolbar and status chips (parity with Operator vault / Risk envelope)", () => {
    expect(birthMissionControlSource).toContain("birth-mission-control__toolbar");
    expect(birthMissionControlSource).toContain("risk-envelope-panel__toolbar");
    expect(birthMissionControlSource).toContain("birth-mission-status-strip");
    expect(birthMissionControlSource).toContain("risk-envelope-status-chip");
    expect(birthMissionControlSource).toContain("HISTORY");
    expect(birthMissionControlSource).toContain("REGIME");
    expect(birthMissionControlSource).toContain("POLICY");
    expect(birthMissionControlSource).toContain("LANES");
    expect(birthMissionControlSource).toContain("Fitness landscape");
    expect(birthMissionControlSource).toContain("risk-envelope-field-card");
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

  it("hosts Stop birth in the panel toolbar when showStopControl is set", () => {
    expect(birthMissionControlSource).toContain("showStopControl");
    expect(birthMissionControlSource).toContain("BirthControlDock");
    expect(birthMissionControlSource).toContain("birth-control-dock--panel");
    expect(birthMissionControlSource).toContain("birth-mission-control__toolbar-actions");
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
