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

const birthStageTabSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "./BirthStageScorecardStageTab.tsx"),
  "utf8",
);

const birthRecoveryTabSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "./BirthStageScorecardRecoveryTab.tsx"),
  "utf8",
);

const birthEvolutionTabSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "./BirthStageScorecardEvolutionTab.tsx"),
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
    expect(birthStageIntelSource).toContain("isBirthCurriculumScorecardActive");
    expect(birthStageIntelSource).toContain("Birth preparation");
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
    // Stage tab: compact pass checklist + lean ops tiles (no duplicate gate cards).
    // EdgeScore stays on the fitness landscape — not repeated here.
    expect(birthStageTabSource).toContain("BirthStagePassChecklistCard");
    expect(birthStageTabSource).toContain("buildStagePassChecklist");
    expect(birthStageTabSource).toContain("BirthFieldCard");
    expect(birthStageTabSource).toContain("presentBlockerDetail");
    expect(birthStageTabSource).toContain("BirthBlockerGateCard");
    expect(birthStageTabSource).not.toContain('label="EdgeScore"');
    expect(birthStageTabSource).toContain('label="Champion"');
    expect(birthStageTabSource).toContain('label="Sub-phase"');
    expect(birthStageTabSource).toContain('label="Data window"');
    // Pass-gate metrics (volume / flat / hold / hygiene) live only in Stage goal.
    expect(birthStageTabSource).not.toContain('label="Position flat"');
    expect(birthStageTabSource).not.toContain('label="Hygiene WR"');
    expect(birthStageTabSource).not.toContain("shouldShowPositionFlat");
    expect(birthStageTabSource).not.toContain("shouldShowHoldRatio");
    expect(birthRecoveryTabSource).toContain('label="Volume gate"');
    expect(birthEvolutionTabSource).toContain('label="Plateau clock"');
    expect(birthStageScorecardSource).not.toContain("ProgressBar");
  });

  it("keeps range-stage flat visibility on metrics strip, not as Stage-tab duplicates", () => {
    expect(birthStageTabSource).toContain("BirthStagePassChecklistCard");
    expect(birthStageTabSource).toContain("birth-stage-blocker-compact");
    expect(birthStageTabSource).toContain("presentBlockerDetail");
    expect(birthMetricsStripSource).toContain("range_edgescore");
    expect(birthMetricsStripSource).toContain('label="Position flat"');
    expect(birthFieldCardSource).toContain("data-tone");
    expect(birthFieldCardSource).toContain("CONDITION_VALUE_TEXT_CLASS");
  });

  it("reuses Risk Envelope field-card classes", () => {
    expect(birthFieldCardSource).toContain("risk-envelope-field-card");
    expect(birthFieldCardSource).toContain("risk-envelope-field-label");
    expect(birthFieldCardSource).toContain("risk-envelope-field-hint");
  });
});

describe("BirthStagePassChecklistCard density", () => {
  const checklistCardSource = readFileSync(
    join(dirname(fileURLToPath(import.meta.url)), "./BirthStagePassChecklistCard.tsx"),
    "utf8",
  );
  const birthPhaseCss = readFileSync(
    join(dirname(fileURLToPath(import.meta.url)), "../../styles/birthPhase.css"),
    "utf8",
  );

  it("renders a 2-col board with per-gate green/orange/red chips", () => {
    expect(checklistCardSource).toContain("birth-stage-pass-checklist");
    expect(checklistCardSource).toContain("Stage goal");
    expect(checklistCardSource).toContain("gates clear");
    expect(checklistCardSource).toContain("req.current");
    expect(checklistCardSource).toContain("req.need");
    expect(checklistCardSource).toContain("data-layout");
    expect(checklistCardSource).toContain("BirthReadoutStack");
    // Outer shell neutral; tones apply per row (no whole-card wash).
    expect(checklistCardSource).toContain("data-tone={tone}");
    expect(checklistCardSource).not.toMatch(
      /birth-stage-pass-checklist[\s\S]*?data-tone=\{overallTone/,
    );
    expect(birthPhaseCss).toContain("grid-template-columns: 1fr 1fr");
    expect(birthPhaseCss).toContain(
      '.birth-stage-pass-checklist__row[data-tone="ok"]',
    );
    expect(birthPhaseCss).toContain(
      '.birth-stage-pass-checklist__row[data-tone="warn"]',
    );
    expect(birthPhaseCss).toContain(
      '.birth-stage-pass-checklist__row[data-tone="danger"]',
    );
    // Same type scale as left-column field cards (label 0.55rem, value text-sm).
    expect(birthPhaseCss).toMatch(
      /\.birth-stage-pass-checklist__label\s*\{[^}]*font-size:\s*0\.55rem/s,
    );
    expect(birthPhaseCss).toMatch(
      /\.birth-stage-pass-checklist__value\s*\{[^}]*font-size:\s*0\.875rem/s,
    );
    expect(birthPhaseCss).toContain('data-layout="stack"');
    expect(birthPhaseCss).toContain(".birth-readout-stack");
    expect(birthPhaseCss).toContain("justify-content: space-between");
    expect(birthPhaseCss).toContain(".birth-blocker-gate__value");
  });
});
