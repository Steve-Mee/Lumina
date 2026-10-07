import { describe, expect, it } from "vitest";

import { buildPlaygroundChecklist } from "@/lib/playground/playgroundChecklist";

describe("playgroundChecklist", () => {
  it("allMet only when pass_now and every gate is in exit_proofs", () => {
    const incomplete = buildPlaygroundChecklist({
      pass_now: false,
      missing: ["green_days=1 < 5"],
      learned: { green_days: 1, exit_proofs: ["sim_envelope_sealed"] },
    });
    expect(incomplete.allMet).toBe(false);
    expect(incomplete.requirements.some((row) => row.id === "green_days>=5" && !row.met)).toBe(true);

    const proofs = [
      "birth_freeze_intact",
      "awakening_child_loaded",
      "sim_envelope_sealed",
      "deck_live",
      "mode_sim_fail_closed",
      "policy_only",
      "green_days>=5",
      "envelope_not_breached",
    ];
    const complete = buildPlaygroundChecklist({
      pass_now: true,
      missing: [],
      learned: { n_p: 160, exit_proofs: proofs },
    });
    expect(complete.allMet).toBe(true);
    expect(complete.metCount).toBe(complete.totalCount);
    const baseline = complete.requirements.find((row) => row.id === "awakening_child_loaded");
    expect(baseline?.label).toBe("First Watch baseline");
    expect(baseline?.need).toMatch(/may be Birth plant/i);
  });
});
