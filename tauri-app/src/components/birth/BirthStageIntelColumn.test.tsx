import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const birthStageIntelSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "./BirthStageIntelColumn.tsx"),
  "utf8",
);

const birthStageScorecardSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "./BirthStageScorecard.tsx"),
  "utf8",
);

const birthMetricsStripSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "./BirthMetricsStrip.tsx"),
  "utf8",
);

const birthFieldCardSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "./BirthFieldCard.tsx"),
  "utf8",
);

describe("BirthStageIntelColumn", () => {
  it("renders scorecard only when curriculum stage data exists", () => {
    expect(birthStageIntelSource).toContain("BirthStageScorecard");
    expect(birthStageIntelSource).toMatch(/showContent && scorecard \?/);
    expect(birthStageIntelSource).toContain("extractBirthSessionHud");
    expect(birthStageScorecardSource).toContain("extractStageScorecard");
    expect(birthStageScorecardSource).not.toContain("BirthSessionTelemetry");
  });

  it("uses vault-grade toolbar and status chips", () => {
    expect(birthStageIntelSource).toContain("risk-envelope-panel__toolbar");
    expect(birthStageIntelSource).toContain("Stage intelligence");
    expect(birthStageIntelSource).toContain("risk-envelope-status-chip");
    expect(birthStageIntelSource).toContain("GATE");
    expect(birthStageIntelSource).toContain("HEALTH");
    expect(birthStageIntelSource).toContain("RECOVERY");
    expect(birthStageIntelSource).toContain("WALL");
  });

  it("keeps session telemetry in the status column only", () => {
    expect(birthMetricsStripSource).toContain("BirthSessionTelemetry");
    expect(birthMetricsStripSource).toContain("useLiveBirthElapsedSec");
    expect(birthStageIntelSource).not.toContain("BirthSessionTelemetry");
  });

  it("uses the dedicated intel column scroll body", () => {
    expect(birthStageIntelSource).toContain("birth-stage-intel-column__body");
    expect(birthStageIntelSource).not.toContain("birth-mission-control__scroll");
  });
});

describe("BirthStageScorecard field parity", () => {
  it("exposes Stage / Recovery / Evolution tabs with named field cards", () => {
    expect(birthStageScorecardSource).toContain('value="stage"');
    expect(birthStageScorecardSource).toContain('value="recovery"');
    expect(birthStageScorecardSource).toContain('value="evolution"');
    expect(birthStageScorecardSource).toContain("risk-envelope-tabs");
    expect(birthStageScorecardSource).toContain("BirthFieldCard");
    expect(birthStageScorecardSource).toContain('label="Goal"');
    expect(birthStageScorecardSource).toContain('label="Volume gate"');
    expect(birthStageScorecardSource).toContain('label="Plateau clock"');
    expect(birthStageScorecardSource).not.toContain("ProgressBar");
  });

  it("spans Goal and Blocking metric full width with goal/danger tones", () => {
    expect(birthStageScorecardSource).toContain("isGoalMet");
    expect(birthStageScorecardSource).toMatch(
      /label="Goal"[\s\S]*birth-intel-field-span/,
    );
    expect(birthStageScorecardSource).toContain('tone="danger"');
    expect(birthStageScorecardSource).toContain("Pass gate blocked");
    expect(birthFieldCardSource).toContain('"danger"');
    expect(birthFieldCardSource).toContain("data-tone");
  });

  it("reuses Risk Envelope field-card classes", () => {
    expect(birthFieldCardSource).toContain("risk-envelope-field-card");
    expect(birthFieldCardSource).toContain("risk-envelope-field-label");
    expect(birthFieldCardSource).toContain("risk-envelope-field-hint");
  });
});
