import { describe, expect, it } from "vitest";

import type { BirthStatusPayload } from "@/lib/birthClient";
import {
  buildCompactMilestones,
  buildMilestones,
  extractPpoProgress,
  extractSimProgress,
  extractStageScorecard,
  isBirthCertificateFailed,
  isBirthComplete,
  isBirthFailed,
  isBirthInterrupted,
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

  it("maps mid-curriculum ppo_training phase to strategies milestone", () => {
    expect(
      resolveActiveMilestone(
        { stage: "training_running", phase: "ppo_training" },
        "running",
      ),
    ).toBe("strategies");
  });

  it("maps ppo_polish phase to refinement milestone", () => {
    expect(
      resolveActiveMilestone({ stage: "ppo_training", phase: "ppo_polish" }, "running"),
    ).toBe("refinement");
  });

  it("maps oos_evaluation phase to refinement milestone", () => {
    expect(
      resolveActiveMilestone({ stage: "training_running", phase: "oos_evaluation" }, "running"),
    ).toBe("refinement");
  });

  it("maps completed status to awakening milestone", () => {
    expect(resolveActiveMilestone({ stage: "completed" }, "completed")).toBe("awakening");
  });

  it("builds milestone states with prior steps complete", () => {
    const milestones = buildMilestones({ stage: "ppo_training", phase: "ppo_polish" }, "running");
    expect(milestones.find((m) => m.id === "dna")?.state).toBe("complete");
    expect(milestones.find((m) => m.id === "refinement")?.state).toBe("active");
    expect(milestones.find((m) => m.id === "awakening")?.state).toBe("pending");
  });

  it("uses awakening headline when birth is complete", () => {
    const milestones = buildMilestones({ stage: "completed" }, "completed");
    expect(resolveBirthHeadline(milestones, "completed", { stage: "completed" }, true)).toBe(
      "Birth Certificate v2 issued",
    );
  });

  it("uses certificate headline when completed without certificate", () => {
    const milestones = buildMilestones({ stage: "completed" }, "completed");
    expect(resolveBirthHeadline(milestones, "completed", { stage: "completed" }, false)).toBe(
      "Birth Certificate v2 required",
    );
  });

  it("does not treat running status as certificate failed when cert is invalid", () => {
    expect(
      isBirthCertificateFailed({ status: "running", certificate_ok: false }),
    ).toBe(false);
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

  it("detects running, interrupted, and failed states", () => {
    expect(isBirthRunning({ status: "running" })).toBe(true);
    expect(isBirthFailed({ status: "error" })).toBe(true);
    expect(isBirthFailed({ status: "interrupted" })).toBe(false);
    expect(isBirthInterrupted({ status: "interrupted" })).toBe(true);
  });

  it("extracts simulation progress from trades", () => {
    const sim = extractSimProgress({ trades_done: 500, target_trades: 1000 });
    expect(sim.done).toBe(500);
    expect(sim.target).toBe(1000);
    expect(sim.pct).toBe(50);
  });

  it("prefers stage_target_trades during curriculum stage", () => {
    const sim = extractSimProgress({
      trades_done: 188,
      stage_trades: 62,
      target_trades: 10_000,
      stage_target_trades: 100,
      curriculum_stage: "stage1_trend",
    });
    expect(sim.done).toBe(62);
    expect(sim.target).toBe(100);
    expect(sim.pct).toBeCloseTo(62);
  });

  it("infers winrate criteria from curriculum stage when scorecard fields missing", () => {
    const scorecard = extractStageScorecard({
      curriculum_stage: "stage1_trend",
      stage_trades: 190,
      stage_target_trades: 100,
      stage_wins: 76,
      phase: "ppo_training",
      timestamp: "2026-06-12T12:00:06.000Z",
    });
    expect(scorecard?.metricLabel).toBe("Winrate");
    expect(scorecard?.metricValue).toBeCloseTo(76 / 190, 3);
    expect(scorecard?.metricTarget).toBe(0.45);
  });

  it("shows syncing state when stage wins are not yet on progress payload", () => {
    const scorecard = extractStageScorecard({
      curriculum_stage: "stage1_trend",
      stage_trades: 190,
      stage_target_trades: 100,
      phase: "ppo_training",
    });
    expect(scorecard?.metricLabel).toBe("Winrate");
    expect(scorecard?.metricValue).toBeNull();
  });

  it("extracts stage scorecard with winrate and health", () => {
    const now = Date.parse("2026-06-12T12:00:10.000Z");
    const scorecard = extractStageScorecard(
      {
        curriculum_stage: "stage1_trend",
        curriculum_index: 1,
        curriculum_total: 3,
        stage_display_name: "Trend",
        stage_trades: 62,
        stage_target_trades: 100,
        stage_winrate: 0.41,
        pass_criteria_id: "trend_winrate",
        pass_criteria_label: ">=100 trades · winrate >=45%",
        pass_metric_label: "Winrate",
        pass_metric_target: 0.45,
        sub_phase: "curriculum_research",
        sub_phase_label: "Oracle research",
        patterns_mined: 1240,
        learning_attempt: 12,
        is_advancing: true,
        timestamp: "2026-06-12T12:00:06.000Z",
      },
      now,
    );
    expect(scorecard?.stageLabel).toBe("Stage 1/3 · Trend");
    expect(scorecard?.tradesDone).toBe(62);
    expect(scorecard?.metricValue).toBeCloseTo(0.41);
    expect(scorecard?.heartbeatSec).toBe(4);
    expect(scorecard?.health).toBe("advancing");
  });

  it("extracts stage wall remaining seconds for HUD", () => {
    const scorecard = extractStageScorecard({
      curriculum_stage: "stage2_range",
      stage_trades: 120,
      stage_target_trades: 300,
      pass_criteria_id: "range_roundtrip",
      pass_metric_min: 0.3,
      pass_metric_max: 0.7,
      stage_range_flat_ratio: 0.55,
      stage_range_round_trips: 12,
      phase: "curriculum_learning",
      stage_wall_remaining_sec: 5400,
      exploration_active: true,
    });
    expect(scorecard?.stageWallRemainingSec).toBe(5400);
    expect(scorecard?.explorationActive).toBe(true);
    expect(scorecard?.passCriteriaId).toBe("range_roundtrip");
    expect(scorecard?.metricValue).toBeCloseTo(0.55);
    expect(scorecard?.stageRangeRoundTrips).toBe(12);
  });

  it("marks scorecard stale after long silence", () => {
    const now = Date.parse("2026-06-12T12:15:00.000Z");
    const scorecard = extractStageScorecard(
      {
        curriculum_stage: "stage1_trend",
        stage_trades: 62,
        stage_target_trades: 100,
        timestamp: "2026-06-12T12:00:00.000Z",
        is_advancing: false,
      },
      now,
    );
    expect(scorecard?.health).toBe("stale");
  });

  it("builds compact milestones with upcoming count", () => {
    const compact = buildCompactMilestones(
      { stage: "training_running", phase: "curriculum_learning" },
      "running",
    );
    expect(compact.items.length).toBeLessThanOrEqual(3);
    expect(compact.items.some((m) => m.state === "active")).toBe(true);
    expect(compact.upcomingCount).toBeGreaterThanOrEqual(0);
  });

  it("extracts PPO progress with batch label", () => {
    const ppo = extractPpoProgress({ ppo_steps_cumulative: 12000, ppo_batch_count: 3 });
    expect(ppo.steps).toBe(12000);
    expect(ppo.label).toContain("batch 3");
  });
});
