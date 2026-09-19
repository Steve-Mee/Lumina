import { describe, expect, it } from "vitest";

import { apprenticeshipTilesFromLearned } from "@/components/maturity/phaseHubApprenticeship";
import { buildApprenticeshipChecklist } from "@/lib/apprenticeship/apprenticeshipChecklist";

describe("apprenticeship hub tiles", () => {
  it("leads with Doel Lopen and green days", () => {
    const tiles = apprenticeshipTilesFromLearned({
      n_d: 2,
      sharpe: 0.11,
      dd_pct: 4,
      recovery_ok: false,
      risk_events: 0,
    });
    expect(tiles[0]?.label).toBe("Doel");
    expect(tiles[0]?.value).toBe("Lopen");
    expect(tiles[1]?.value).toBe("2 / 5");
  });

  it("checklist is not allMet without pass_now", () => {
    const checklist = buildApprenticeshipChecklist({
      pass_now: false,
      missing: ["n_D=2 < 5"],
      learned: {
        exit_proofs: ["birth_freeze_intact"],
        n_d: 2,
        n_a: 40,
      },
    });
    expect(checklist.allMet).toBe(false);
    expect(checklist.requirements.some((row) => row.id === "n_D>=5" && !row.met)).toBe(true);
  });

  it("checklist allMet only when pass_now and every gate is proven", () => {
    const ids = [
      "playground_completed",
      "birth_freeze_intact",
      "playground_child_loaded",
      "sim_envelope_sealed",
      "deck_live",
      "mode_sim_real_guard",
      "n_A>=150",
      "n_D>=5",
      "occupancy_in_band",
      "process_r",
      "risk_discipline",
      "constitution_0",
      "recovery_ok",
    ];
    const checklist = buildApprenticeshipChecklist({
      pass_now: true,
      missing: [],
      learned: { exit_proofs: ids, n_a: 160, n_d: 5, sharpe: 0.4, dd_pct: 6 },
    });
    expect(checklist.allMet).toBe(true);
  });
});
