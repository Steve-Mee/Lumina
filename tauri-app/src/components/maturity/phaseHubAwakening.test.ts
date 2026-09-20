import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { awakeningTilesFromLearned } from "@/components/maturity/phaseHubAwakening";

describe("awakening hub tiles", () => {
  it("leads with Doel Ogen open and n_B / 500", () => {
    const tiles = awakeningTilesFromLearned({
      n_b: 150,
      lift: 0.02,
      wr: 0.41,
      birth_oos_wr: 0.39,
      occupancy: 0.33,
      stable_class: "INCONCLUSIVE",
      twin_watch_n: 0,
    });
    expect(tiles[0]?.label).toBe("Doel");
    expect(tiles[0]?.value).toBe("Ogen open");
    expect(tiles[1]?.value).toBe("150 / 500");
  });

  it("footnotes B+later OOS when the exam continued after Birth B", () => {
    const tiles = awakeningTilesFromLearned({
      n_b: 150,
      exam_kind: "holdout_B_plus_continuation",
      exam_n: 185000,
      kept: true,
    });
    const nB = tiles.find((tile) => tile.label === "n_B");
    expect(nB?.footnote).toContain("B+later OOS");
    expect(nB?.footnote).toContain("185,000");
    expect(nB?.footnote).toContain("child kept");
  });

  it("AwakeningMission keeps goal, progress, and performance regions", () => {
    const src = readFileSync(
      join(dirname(fileURLToPath(import.meta.url)), "AwakeningMission.tsx"),
      "utf8",
    );
    expect(src).toContain('aria-label="Awakening goal"');
    expect(src).toContain('aria-label="Awakening live progress"');
    expect(src).toContain('aria-label="Awakening performance"');
  });
});
