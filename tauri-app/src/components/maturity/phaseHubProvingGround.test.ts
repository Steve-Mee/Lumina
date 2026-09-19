import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { provingGroundTilesFromLearned } from "@/components/maturity/phaseHubProvingGround";
import { buildProvingGroundChecklist } from "@/lib/provingGround/provingGroundChecklist";

const GATES = [
  "apprenticeship_completed",
  "birth_freeze_intact",
  "apprenticeship_child_loaded",
  "sim_envelope_sealed",
  "deck_live",
  "mode_sim_fail_closed",
  "n_G>=150",
  "occupancy_in_band",
  "process_r",
  "exam_source_proving",
  "exam_eval_only",
  "exam_folds>=5",
  "certificate_oos_walls",
  "shadow_this_run",
  "promotion_gate_this_run",
  "constitution_0",
  "recovery_ok",
];

describe("proving ground hub tiles", () => {
  it("leads with Doel Rijexamen and n_G", () => {
    const tiles = provingGroundTilesFromLearned({
      n_g: 40,
      oos_wr: 0.41,
      oos_sharpe: 0.22,
      dd_pct: 6,
      shadow_this_run: false,
      promotion_criteria_passed: 1,
    });
    expect(tiles[0]?.label).toBe("Doel");
    expect(tiles[0]?.value).toBe("Rijexamen");
    expect(tiles[1]?.value).toBe("40 / 150");
  });

  it("checklist is not allMet without pass_now", () => {
    const checklist = buildProvingGroundChecklist({
      pass_now: false,
      missing: ["n_G=40 < 150"],
      learned: {
        exit_proofs: ["birth_freeze_intact"],
        n_g: 40,
      },
    });
    expect(checklist.allMet).toBe(false);
    expect(checklist.requirements.some((row) => row.id === "n_G>=150" && !row.met)).toBe(true);
  });

  it("checklist allMet only when pass_now and every gate is proven", () => {
    const checklist = buildProvingGroundChecklist({
      pass_now: true,
      missing: [],
      learned: { exit_proofs: GATES, n_g: 160, promotion_criteria_passed: 4 },
    });
    expect(checklist.allMet).toBe(true);
    expect(checklist.metCount).toBe(GATES.length);
  });
});

describe("proving ground pulse honesty", () => {
  it("life pulse source does not embed BirthOrganismVisual", () => {
    const root = join(dirname(fileURLToPath(import.meta.url)));
    const text = readFileSync(join(root, "ProvingGroundLifePulse.tsx"), "utf8");
    expect(text).not.toContain("BirthOrganismVisual");
    expect(text).not.toContain("birth-organism");
  });
});
