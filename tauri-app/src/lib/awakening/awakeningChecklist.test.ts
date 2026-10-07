import { describe, expect, it } from "vitest";

import {
  FIRST_WATCH_GATES,
  buildAwakeningChecklist,
} from "@/lib/awakening/awakeningChecklist";

const FIRST_WATCH_PROOFS = FIRST_WATCH_GATES.map((gate) => gate.id);

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

  it("lists the First Watch AND, not child-beats-parent or paired CI", () => {
    const list = buildAwakeningChecklist({ pass_now: false, learned: {} });
    expect(list.requirements.map((row) => row.id)).toEqual(FIRST_WATCH_PROOFS);
    expect(list.requirements.some((row) => row.id === "evolution_proof_passed")).toBe(false);
    expect(list.requirements.some((row) => row.id === "prefer_better_edge")).toBe(false);
    expect(list.requirements.some((row) => row.id === "no_substitution")).toBe(false);
    expect(list.mission).toMatch(/no learn/i);
    expect(list.stageTitle).toBe("First Watch");
  });

  it("allMet only when pass_now and every First Watch gate is in proofs", () => {
    const list = buildAwakeningChecklist({
      pass_now: true,
      learned: {
        n_b: 600,
        occupancy: 0.4,
        exit_proofs: FIRST_WATCH_PROOFS,
        twin_watch_n: 2,
        child_weight_sha: "aa",
        init_weight_sha: "aa",
        constitution_violations: 0,
        constitution_blocks: 0,
        parent_replay_present: true,
      },
    });
    expect(list.allMet).toBe(true);
    expect(list.metCount).toBe(12);
    expect(list.totalCount).toBe(12);
  });

  it("does not claim allMet when the plant sha is missing from proofs", () => {
    const withoutPlant = FIRST_WATCH_PROOFS.filter((id) => id !== "baseline_is_plant");
    const list = buildAwakeningChecklist({
      pass_now: true,
      learned: { exit_proofs: withoutPlant, n_b: 600 },
    });
    expect(list.allMet).toBe(false);
    expect(list.requirements.find((row) => row.id === "baseline_is_plant")?.met).toBe(false);
  });

  it("does not claim allMet when pass_now is false or missing remains", () => {
    const open = buildAwakeningChecklist({
      pass_now: false,
      missing: ["twin_watch_missing"],
      learned: { exit_proofs: FIRST_WATCH_PROOFS, freeze_ok: true },
    });
    expect(open.allMet).toBe(false);
    expect(open.overallTone).toBe("danger");
  });

  it("missing n_B and twin watch stay em dash, never invented zero", () => {
    const list = buildAwakeningChecklist({
      pass_now: false,
      learned: { occupancy: null },
    });
    expect(list.requirements.find((row) => row.id === "n_B>=500")?.current).toBe("—");
    expect(list.requirements.find((row) => row.id === "twin_watch")?.current).toBe("—");
    expect(list.requirements.find((row) => row.id === "constitution_clear")?.current).toBe("—");
    expect(list.requirements.find((row) => row.id === "baseline_is_plant")?.current).toBe("—");
  });

  it("records plant match and constitution from measured fields", () => {
    const list = buildAwakeningChecklist({
      pass_now: false,
      learned: {
        child_weight_sha: "plantsha",
        init_weight_sha: "plantsha",
        constitution_violations: 0,
        constitution_blocks: 0,
        parent_replay_present: true,
        exit_proofs: ["baseline_is_plant", "constitution_clear", "baseline_book"],
      },
    });
    expect(list.requirements.find((row) => row.id === "baseline_is_plant")?.current).toBe("plant");
    expect(list.requirements.find((row) => row.id === "constitution_clear")?.current).toBe("clear");
    expect(list.requirements.find((row) => row.id === "baseline_book")?.current).toBe("yes");
    expect(list.requirements.find((row) => row.id === "baseline_is_plant")?.need).toBe(
      "weight sha = Birth plant",
    );
  });
});
