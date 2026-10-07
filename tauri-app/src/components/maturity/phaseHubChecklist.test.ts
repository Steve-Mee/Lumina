import { describe, expect, it } from "vitest";

import {
  hubExamAttempted,
  hubExamStatusLine,
  resolveHubChecklist,
} from "@/components/maturity/phaseHubChecklist";
import type { MaturityHubPayload } from "@/lib/maturationClient";

function hub(partial: Record<string, unknown>): MaturityHubPayload {
  return {
    advance_mode: "manual",
    active_phase: null,
    completed_phases: ["genesis", "birth"],
    next_phase: "awakening",
    focus_phase: "awakening",
    phase_records: {},
    pending_advance: null,
    last_completed: "birth",
    learned: {},
    focus_learned: {},
    focus_status: "pending",
    exit_eval: { ok: false, missing: [] },
    phase_specs: {},
    can_start_next: true,
    real_requires_human: true,
    birth_exit_exited: true,
    ready_for_real: false,
    real_eligible: false,
    ...partial,
  } as MaturityHubPayload;
}

describe("phaseHubChecklist", () => {
  it("idle Awakening does not paint missing gates as a failed exam", () => {
    const payload = hub({
      exit_eval: {
        ok: false,
        missing: [
          "birth_freeze_violated",
          "n_B=0 < 500",
          "baseline_book_missing",
          "stable_class=INCONCLUSIVE",
        ],
      },
      focus_learned: { n_b: 0, stable_class: "INCONCLUSIVE" },
    });
    expect(hubExamAttempted(payload)).toBe(false);
    const list = resolveHubChecklist(payload);
    expect(list.allMet).toBe(false);
    expect(list.overallTone).toBe("default");
    const freeze = list.requirements.find((row) => row.id === "birth_freeze_intact");
    expect(freeze?.met).toBe(false);
    expect(freeze?.current).toBe("Birth plant frozen");
    expect(freeze?.tone).toBe("default");
    const proof = list.requirements.find((row) => row.id === "baseline_book");
    expect(proof?.need).toMatch(/parent ledger/i);
    expect(list.requirements.some((row) => row.id === "evolution_proof_passed")).toBe(false);
    const idleLine = hubExamStatusLine(payload, { running: false, retry: false });
    expect(idleLine).toMatch(/not a failed exam/i);
    expect(idleLine).not.toMatch(/gates below/i);
  });

  it("failed attempt keeps engine blockers visible and fail-closed", () => {
    const payload = hub({
      focus_status: "failed",
      last_result: { ok: false, missing: ["baseline_book_missing"] },
      exit_eval: { ok: false, missing: ["baseline_book_missing", "n_B=12 < 500"] },
      focus_learned: {
        n_b: 12,
        parent_replay_present: false,
        exit_proofs: ["birth_freeze_intact"],
        freeze_ok: true,
      },
    });
    expect(hubExamAttempted(payload)).toBe(true);
    const list = resolveHubChecklist(payload);
    const nb = list.requirements.find((row) => row.id === "n_B>=500");
    expect(nb?.met).toBe(false);
    expect(nb?.current).toContain("12");
    const proof = list.requirements.find((row) => row.id === "baseline_book");
    expect(proof?.met).toBe(false);
    expect(proof?.current).toBe("no");
    expect(proof?.need).toBe("parent ledger on disk");
    expect(hubExamStatusLine(payload, { running: false, retry: true })).toMatch(/did not pass/i);
  });

  it("pass_now paints complete only from engine ok", () => {
    const payload = hub({
      focus_status: "completed",
      exit_eval: { ok: true, missing: [] },
      focus_learned: {
        n_b: 520,
        exit_proofs: [
          "birth_freeze_intact",
          "policy_only",
          "n_B>=500",
          "occupancy_in_band",
          "process_r",
          "baseline_book",
          "STABLE",
          "baseline_is_plant",
          "constitution_clear",
          "twin_watch",
          "recovery_ok",
          "regime_visibility",
        ],
      },
    });
    const list = resolveHubChecklist(payload);
    expect(list.allMet).toBe(true);
    expect(hubExamStatusLine(payload, { running: false, retry: false })).toMatch(/complete/i);
  });
});
