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

describe("BirthStageIntelColumn", () => {
  it("renders scorecard only when curriculum stage data exists", () => {
    expect(birthStageIntelSource).toContain("BirthStageScorecard");
    expect(birthStageIntelSource).toMatch(/showContent && scorecard \?/);
    expect(birthStageIntelSource).toContain("extractBirthSessionHud");
    expect(birthStageScorecardSource).toContain("extractStageScorecard");
    expect(birthStageScorecardSource).not.toContain("BirthSessionTelemetry");
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
