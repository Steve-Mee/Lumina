import { describe, expect, it } from "vitest";

import type { BirthStatusPayload } from "@/lib/birthClient";
import {
  buildMilestones,
  extractPpoProgress,
  extractSimProgress,
  isBirthComplete,
  isBirthFailed,
  isBirthRunning,
  resolveActiveMilestone,
  resolveBirthHeadline,
} from "@/lib/birthPhaseModel";

describe("birthPhaseModel", () => {
  it("maps detected stage to dna milestone", () => {
    expect(resolveActiveMilestone({ stage: "detected" }, "running")).toBe("dna");
  });

  it("maps loading_data to fitness milestone", () => {
    expect(resolveActiveMilestone({ stage: "loading_data" }, "running")).toBe("fitness");
  });

  it("maps parallel_simulation to strategies milestone", () => {
    expect(
      resolveActiveMilestone({ stage: "parallel_simulation", phase: "parallel_simulation" }, "running"),
    ).toBe("strategies");
  });

  it("maps ppo_training to refinement milestone", () => {
    expect(resolveActiveMilestone({ stage: "ppo_training" }, "running")).toBe("refinement");
  });

  it("maps completed status to awakening milestone", () => {
    expect(resolveActiveMilestone({ stage: "completed" }, "completed")).toBe("awakening");
  });

  it("builds milestone states with prior steps complete", () => {
    const milestones = buildMilestones({ stage: "ppo_training" }, "running");
    expect(milestones.find((m) => m.id === "dna")?.state).toBe("complete");
    expect(milestones.find((m) => m.id === "refinement")?.state).toBe("active");
    expect(milestones.find((m) => m.id === "awakening")?.state).toBe("pending");
  });

  it("uses awakening headline when birth is complete", () => {
    const milestones = buildMilestones({ stage: "completed" }, "completed");
    expect(resolveBirthHeadline(milestones, "completed")).toBe("Neural organism online");
  });

  it("detects birth completion from status and artifacts", () => {
    const payload: BirthStatusPayload = {
      status: "completed",
      artifacts_ok: true,
      progress: { stage: "completed" },
    };
    expect(isBirthComplete(payload)).toBe(true);
  });

  it("does not treat completed without artifacts as complete when explicitly false", () => {
    const payload: BirthStatusPayload = {
      status: "completed",
      artifacts_ok: false,
    };
    expect(isBirthComplete(payload)).toBe(false);
  });

  it("detects running and failed states", () => {
    expect(isBirthRunning({ status: "running" })).toBe(true);
    expect(isBirthFailed({ status: "error" })).toBe(true);
    expect(isBirthFailed({ status: "interrupted" })).toBe(true);
  });

  it("extracts simulation progress from trades", () => {
    const sim = extractSimProgress({ trades_done: 500, target_trades: 1000 });
    expect(sim.done).toBe(500);
    expect(sim.target).toBe(1000);
    expect(sim.pct).toBe(50);
  });

  it("extracts PPO progress with batch label", () => {
    const ppo = extractPpoProgress({ ppo_steps_cumulative: 12000, ppo_batch_count: 3 });
    expect(ppo.steps).toBe(12000);
    expect(ppo.label).toContain("batch 3");
  });
});
