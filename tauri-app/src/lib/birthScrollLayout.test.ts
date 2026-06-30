import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const birthPhaseCssSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../styles/birthPhase.css"),
  "utf8",
);

const birthPhaseSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/birth/BirthPhaseScreen.tsx"),
  "utf8",
);

const birthMissionControlSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/birth/BirthMissionControl.tsx"),
  "utf8",
);

const birthStageIntelSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/birth/BirthStageIntelColumn.tsx"),
  "utf8",
);

const birthStageDetailsSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/birth/BirthStageDetailsPanel.tsx"),
  "utf8",
);

const birthAdvancedPanelSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/birth/BirthAdvancedPanel.tsx"),
  "utf8",
);

describe("birthScrollLayout", () => {
  it("uses a three-column mission grid on large screens", () => {
    expect(birthPhaseCssSource).toMatch(
      /\.birth-mission-grid[\s\S]*@media \(min-width: 1024px\)[\s\S]*grid-template-columns:[\s\S]*minmax\(120px, 14%\)[\s\S]*minmax\(280px, 36%\)[\s\S]*minmax\(320px, 1fr\)/,
    );
    expect(birthPhaseSource).toContain("BirthStageIntelColumn");
  });

  it("scrolls only the stage intel column body when content overflows", () => {
    expect(birthPhaseCssSource).toMatch(/\.birth-stage-intel-column__body[\s\S]*overflow-y:\s*auto/);
    expect(birthPhaseCssSource).toMatch(/\.birth-stage-intel-column__body[\s\S]*min-height:\s*0/);
    expect(birthPhaseCssSource).not.toContain(".birth-mission-control__scroll");
    expect(birthMissionControlSource).not.toContain("birth-mission-control__scroll");
  });

  it("keeps stage scorecard always visible without collapsible toggle in running layout", () => {
    expect(birthMissionControlSource).not.toContain("BirthStageDetailsPanel");
    expect(birthStageIntelSource).toContain("BirthStageScorecard");
    expect(birthStageIntelSource).not.toContain("ChevronDown");
    expect(birthStageIntelSource).not.toContain("aria-expanded");
    expect(birthStageDetailsSource).toContain("birth-stage-details__toggle");
  });

  it("keeps advanced panel content out of nested scroll containers", () => {
    expect(birthStageDetailsSource).not.toContain("overflow-y-auto");
    expect(birthStageDetailsSource).not.toContain("max-h-[");
    expect(birthAdvancedPanelSource).not.toContain("max-h-[min(40dvh");
    expect(birthAdvancedPanelSource).not.toMatch(
      /birth-advanced-panel--controlled[\s\S]*overflow-y-auto/,
    );
  });

  it("styles a visible scrollbar track on the stage intel scroll port", () => {
    expect(birthPhaseCssSource).toContain(".birth-stage-intel-column__body::-webkit-scrollbar-track");
    expect(birthPhaseCssSource).toMatch(
      /\.birth-stage-intel-column__body[\s\S]*scrollbar-gutter:\s*stable/,
    );
    expect(birthPhaseCssSource).toMatch(
      /\.birth-stage-intel-column__body[\s\S]*scrollbar-width:\s*auto/,
    );
  });
});
