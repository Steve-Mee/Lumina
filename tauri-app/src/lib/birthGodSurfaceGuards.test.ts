import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

function lineCount(relativePath: string): number {
  const text = readFileSync(join(root, relativePath), "utf8");
  return text.split(/\r?\n/).length;
}

/** Baseline 2026-07-04 — phase 3 frontend birth cluster split. */
const BASELINES: Record<string, number> = {
  "lib/birthPhaseModel.ts": 12,
  "lib/birth/birthMilestones.ts": 289,
  "lib/birth/birthStatusPredicates.ts": 140,
  "lib/birth/birthProgressExtract.ts": 72,
  "lib/birth/birthSessionHud.ts": 112,
  "lib/birth/birthStageScorecard.ts": 640,
  "lib/birth/birthActiveProgress.ts": 60,
  "lib/birth/birthModelUtils.ts": 16,
  "store/birthStore.ts": 525,
  "store/birthPollCoordinator.ts": 140,
  "store/birthSurfaceModel.ts": 65,
  "components/birth/BirthPhaseScreen.tsx": 909,
  "lib/birthClient.ts": 501,
};

const FACADE_MARKERS: Record<string, string[]> = {
  "lib/birthPhaseModel.ts": [
    "birthMilestones",
    "birthStatusPredicates",
    "birthStageScorecard",
  ],
  "lib/birthClient.ts": ["birth/birthClientTypes"],
  "store/birthStore.ts": ["birthPollCoordinator", "birthSurfaceModel"],
};

describe("birth god-surface guards", () => {
  for (const [relativePath, ceiling] of Object.entries(BASELINES)) {
    it(`${relativePath} stays at or below ${ceiling} lines`, () => {
      const count = lineCount(relativePath);
      expect(count).toBeLessThanOrEqual(ceiling);
    });
  }

  for (const [relativePath, markers] of Object.entries(FACADE_MARKERS)) {
    it(`${relativePath} delegates to bounded modules`, () => {
      const text = readFileSync(join(root, relativePath), "utf8");
      for (const marker of markers) {
        expect(text).toContain(marker);
      }
    });
  }

  it("birthStageScorecard owns extractStageScorecard implementation", () => {
    const text = readFileSync(join(root, "lib/birth/birthStageScorecard.ts"), "utf8");
    expect(text).toContain("export function extractStageScorecard");
  });
});