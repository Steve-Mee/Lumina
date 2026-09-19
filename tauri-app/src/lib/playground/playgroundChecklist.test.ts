import { describe, expect, it } from "vitest";

import { buildPlaygroundChecklist } from "@/lib/playground/playgroundChecklist";

describe("playgroundChecklist", () => {
  it("allMet only when pass_now and every gate is in exit_proofs", () => {
    const incomplete = buildPlaygroundChecklist({
      pass_now: false,
      missing: ["n_P=12 < 150"],
      learned: { n_p: 12, exit_proofs: ["sim_envelope_sealed"] },
    });
    expect(incomplete.allMet).toBe(false);
    expect(incomplete.requirements.some((row) => row.id === "n_P>=150" && !row.met)).toBe(true);

    const proofs = [
      "birth_freeze_intact",
      "awakening_child_loaded",
      "sim_envelope_sealed",
      "deck_live",
      "mode_sim_fail_closed",
      "first_honest_fill",
      "policy_only",
      "n_P>=150",
      "occupancy_in_band",
      "process_r",
      "economic_viability",
      "envelope_not_breached",
    ];
    const complete = buildPlaygroundChecklist({
      pass_now: true,
      missing: [],
      learned: { n_p: 160, exit_proofs: proofs },
    });
    expect(complete.allMet).toBe(true);
    expect(complete.metCount).toBe(complete.totalCount);
  });
});
