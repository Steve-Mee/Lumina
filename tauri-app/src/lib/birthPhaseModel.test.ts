import { describe, expect, it } from "vitest";

import type { BirthStatusPayload } from "@/lib/birthClient";
import {
  buildCompactMilestones,
  buildMilestones,
  extractBirthSessionHud,
  extractPpoProgress,
  extractSimProgress,
  extractStageScorecard,
  formatBirthSessionStartedLabel,
  isBirthCertificateFailed,
  isBirthComplete,
  isBirthFailed,
  isBirthEngineActive,
  isBirthInterrupted,
  isBirthProgressPayloadActive,
  isBirthRunning,
  isBirthStageStalled,
  resolveActiveMilestone,
  resolveBirthHeadline,
  resolveBirthSessionStartedAtMs,
  resolveLiveBirthElapsedSec,
} from "@/lib/birthPhaseModel";

describe("birthPhaseModel", () => {
  it("maps detected stage to dna milestone", () => {
    expect(resolveActiveMilestone({ stage: "detected" }, "running")).toBe("dna");
  });

  it("maps loading_data with loading_history phase to dna milestone", () => {
    expect(
      resolveActiveMilestone({ stage: "loading_data", phase: "loading_history" }, "running"),
    ).toBe("dna");
  });

  it("maps enriching_regimes phase to fitness milestone", () => {
    expect(
      resolveActiveMilestone({ stage: "loading_data", phase: "enriching_regimes" }, "running"),
    ).toBe("fitness");
  });

  it("uses progress message during enriching_regimes", () => {
    const milestones = buildMilestones(
      { stage: "loading_data", phase: "enriching_regimes" },
      "running",
    );
    expect(
      resolveBirthHeadline(milestones, "running", {
        stage: "loading_data",
        phase: "enriching_regimes",
        message: "Regime map bouwen: 2,000/63,940 ticks (64,000 totaal)",
      }),
    ).toBe("Regime map bouwen: 2,000/63,940 ticks (64,000 totaal)");
  });

  it("maps loading_data to fitness milestone when ticks are ready", () => {
    expect(
      resolveActiveMilestone({ stage: "historical_loaded", phase: "ticks_ready" }, "running"),
    ).toBe("fitness");
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

  it("uses progress message during loading_history", () => {
    const milestones = buildMilestones(
      { stage: "loading_data", phase: "loading_history" },
      "running",
    );
    expect(
      resolveBirthHeadline(milestones, "running", {
        stage: "loading_data",
        phase: "loading_history",
        message: "Historische data laden: chunk 3/62 (1200 bars)",
      }),
    ).toBe("Historische data laden: chunk 3/62 (1200 bars)");
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

  it("does not treat idle detected progress as certificate failed when cert is missing", () => {
    expect(
      isBirthCertificateFailed({
        status: "idle",
        certificate_ok: false,
        progress: { stage: "detected", phase: "detected" },
      }),
    ).toBe(false);
  });

  it("does not treat idle not_started as certificate failed when cert is missing", () => {
    expect(
      isBirthCertificateFailed({
        status: "idle",
        certificate_ok: false,
        certificate_reason: "missing_or_invalid_certificate",
        progress: { stage: "not_started", trades_done: 0, target_trades: 5000 },
      }),
    ).toBe(false);
  });

  it("treats completed without certificate as certificate failed", () => {
    expect(
      isBirthCertificateFailed({
        status: "completed",
        certificate_ok: false,
        progress: { stage: "completed", phase: "certificate_failed" },
      }),
    ).toBe(true);
  });

  it("detects active progress during historical load", () => {
    expect(
      isBirthEngineActive({
        status: "idle",
        progress: { stage: "loading_data", phase: "loading_history" },
      }),
    ).toBe(true);
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

  it("detects stage stalled while status is running", () => {
    expect(
      isBirthStageStalled({
        status: "running",
        progress: { phase: "stage_stalled" },
      }),
    ).toBe(true);
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

  it("extracts adaptation HUD fields for scorecard", () => {
    const scorecard = extractStageScorecard({
      curriculum_stage: "stage1_trend",
      stage_trades: 386,
      stage_target_trades: 200,
      stage_winrate: 0.303,
      pass_criteria_id: "trend_winrate",
      pass_metric_target: 0.45,
      phase: "curriculum_learning",
      adaptation_enabled: true,
      wall_behavior: "adaptive",
      volume_gate_status: "PASSED",
      winrate_trend_slope: -0.012,
      retries_this_stage: 1,
      escalation_level: 2,
      last_adaptation: {
        reason: "negative_winrate_trend_after_volume_gate",
        chunk_target: 16,
        escalation: 2,
        winrate: 0.303,
      },
    });
    expect(scorecard?.volumeGateStatus).toBe("PASSED");
    expect(scorecard?.winrateTrendSlope).toBeCloseTo(-0.012);
    expect(scorecard?.retriesThisStage).toBe(1);
    expect(scorecard?.escalationLevel).toBe(2);
    expect(scorecard?.lastAdaptationReason).toBe("Negative winrate trend");
    expect(scorecard?.lastAdaptationChunk).toBe(16);
    expect(scorecard?.lastAdaptationSummary).toContain("chunk 16");
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

  it("extracts session HUD during loading with patterns and session start", () => {
    const startSec = 1_700_000_000;
    const hud = extractBirthSessionHud({
      stage: "loading_data",
      phase: "loading_history",
      message: "Birth Phase: historische ticks laden…",
      birth_start_time: startSec,
      elapsed_sec: 120,
      patterns_mined: 0,
      learning_attempt: 0,
      timestamp: "2026-06-28T08:42:00.000Z",
    });
    expect(hud).not.toBeNull();
    expect(hud?.preCurriculum).toBe(true);
    expect(hud?.patternsMined).toBe(0);
    expect(hud?.learningAttempt).toBe(0);
    expect(hud?.sessionStartedAtMs).toBe(startSec * 1000);
    expect(hud?.sessionStartedLabel).toBe(formatBirthSessionStartedLabel(startSec * 1000));
    expect(isBirthProgressPayloadActive({ stage: "loading_data", phase: "loading_history" })).toBe(
      true,
    );
  });

  it("derives session start from elapsed_sec when birth_start_time missing", () => {
    const ts = Date.parse("2026-06-28T08:42:00.000Z");
    const startMs = resolveBirthSessionStartedAtMs({
      timestamp: "2026-06-28T08:42:00.000Z",
      elapsed_sec: 180,
    });
    expect(startMs).toBe(ts - 180_000);
  });

  it("does not treat progress timestamp as session start when elapsed_sec is zero", () => {
    const startMs = resolveBirthSessionStartedAtMs({
      timestamp: "2026-06-28T08:42:00.000Z",
      elapsed_sec: 0,
    });
    expect(startMs).toBeNull();
  });

  it("resolves live elapsed from birth_start_time between polls", () => {
    const startSec = Math.floor(Date.now() / 1000) - 125;
    const elapsed = resolveLiveBirthElapsedSec(
      {
        stage: "training_running",
        phase: "policy_init",
        birth_start_time: startSec,
        elapsed_sec: 0,
      },
      undefined,
      Date.now(),
    );
    expect(elapsed).not.toBeNull();
    expect(elapsed!).toBeGreaterThanOrEqual(125);
  });

  it("shows session HUD with live counters before curriculum stage is set", () => {
    const hud = extractBirthSessionHud({
      stage: "training_running",
      phase: "policy_init",
      patterns_mined: 512,
      learning_attempt: 5,
      birth_start_time: 1_700_000_000,
      elapsed_sec: 240,
    });
    expect(hud?.patternsMined).toBe(512);
    expect(hud?.learningAttempt).toBe(5);
    expect(hud?.preCurriculum).toBe(true);
  });
});
