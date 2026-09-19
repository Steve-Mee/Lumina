import { describe, expect, it } from "vitest";

import { buildAwakeningChecklist } from "@/lib/awakening/awakeningChecklist";

describe("awakeningChecklist", () => {
  it("paints gates green only when engine proofs include them", () => {
    const list = buildAwakeningChecklist({
      pass_now: false,
      learned: {
        n_b: 133,
        occupancy: 0.4,
        exit_proofs: ["occupancy_in_band", "birth_freeze_intact"],
        blockers: ["n_B=133 < 500"],
      },
    });
    const occ = list.requirements.find((row) => row.id === "occupancy_in_band");
    const nb = list.requirements.find((row) => row.id === "n_B>=500");
    expect(occ?.met).toBe(true);
    expect(occ?.tone).toBe("ok");
    expect(nb?.met).toBe(false);
    expect(list.allMet).toBe(false);
    expect(nb?.current).toContain("133");
  });

  it("allMet only when pass_now and every gate is in proofs", () => {
    const proofs = [
      "birth_freeze_intact",
      "policy_only",
      "n_B>=500",
      "occupancy_in_band",
      "process_r",
      "prefer_better_edge",
      "prefer_better_mean_r",
      "evolution_proof_passed",
      "STABLE",
      "no_substitution",
      "twin_watch",
      "recovery_ok",
      "regime_visibility",
    ];
    const list = buildAwakeningChecklist({
      pass_now: true,
      learned: { n_b: 600, occupancy: 0.4, exit_proofs: proofs, twin_watch_n: 2 },
    });
    expect(list.allMet).toBe(true);
    expect(list.metCount).toBe(list.totalCount);
  });

  it("does not claim allMet when pass_now is false or missing remains", () => {
    const proofs = [
      "birth_freeze_intact",
      "policy_only",
      "n_B>=500",
      "occupancy_in_band",
      "process_r",
      "prefer_better_edge",
      "prefer_better_mean_r",
      "evolution_proof_passed",
      "STABLE",
      "no_substitution",
      "twin_watch",
      "recovery_ok",
      "regime_visibility",
    ];
    const open = buildAwakeningChecklist({
      pass_now: false,
      missing: ["twin_watch_missing"],
      learned: { exit_proofs: proofs, freeze_ok: true },
    });
    expect(open.allMet).toBe(false);
    expect(open.overallTone).toBe("danger");
  });
});
