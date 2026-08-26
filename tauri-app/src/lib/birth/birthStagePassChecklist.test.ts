import { describe, expect, it } from "vitest";

import { buildStagePassChecklist } from "@/lib/birth/birthStagePassChecklist";
import type { StageScorecardModel } from "@/lib/birth/birthStageScorecardTypes";

function baseScorecard(
  partial: Partial<StageScorecardModel> & Pick<StageScorecardModel, "passCriteriaId">,
): StageScorecardModel {
  return {
    stageLabel: "Stage 1/5 · Closed loop",
    goalLabel: "test",
    tradesDone: 100,
    tradesRequired: 200,
    tradesPct: 50,
    metricLabel: "EdgeScore",
    metricValue: 0.4,
    metricTarget: null,
    metricMin: null,
    metricMax: null,
    metricPct: 40,
    subPhase: "ppo_training",
    subPhaseLabel: "PPO",
    patternsMined: 0,
    learningAttempt: 1,
    explorationActive: false,
    stageWallRemainingSec: null,
    stageRangeRoundTrips: null,
    heartbeatSec: 2,
    health: "working",
    healthHint: "ok",
    isCurriculum: true,
    blockerLabel: null,
    blockerDetail: null,
    provisionalPass: false,
    volumeGateStatus: "PENDING",
    winrateTrendSlope: 0.01,
    retriesThisStage: 0,
    adaptationTier: null,
    maxAdaptationTiers: null,
    maxStageRetries: null,
    autoRecoveryActive: false,
    adaptationEnabled: true,
    wallBehavior: "adaptive",
    escalationLevel: null,
    lastAdaptationReason: null,
    lastAdaptationChunk: null,
    lastAdaptationSummary: null,
    evolutionPhase: null,
    evolutionStep: null,
    evolutionStepLabel: null,
    evolutionActionsTotal: null,
    evolutionActionsCompleted: null,
    evolutionPhantomSteps: null,
    evolutionActionsRemaining: null,
    plateauElapsedSec: null,
    tradesBeyondGate: null,
    evolutionRolloutsThisStep: null,
    evolutionRolloutsMax: null,
    stallRemediationCycle: null,
    stallRemediationStep: null,
    stallRemediationMaxSteps: null,
    stallRemediationMaxCycles: null,
    recommendedRecoveryAction: null,
    holdTrapDetected: false,
    stage1WinrateGate: null,
    stage1WinrateRecommended: null,
    stagePassGateTrades: 200,
    stageBudgetTrades: 2000,
    plateauMinStageTrades: null,
    plateauQuarantineActive: false,
    plateauQuarantineRolloutsRemaining: null,
    plateauQuarantineTradesRemaining: null,
    plateauQuarantineTradesRemainingCount: null,
    rollingWinrate500: 0.3,
    rollingWinrateSource: "true_window",
    rollingWindowTradesCovered: 100,
    hygieneWrFloor: 0.2,
    hygieneWrLifetime: 0.3,
    hygieneWrRolling: 0.3,
    hygieneWrEffective: 0.3,
    hygieneWrSource: "lifetime",
    rollingWrEligible: true,
    stageHoldRatio: 0.5,
    stageHoldMax: null,
    stageRangeFlatRatio: null,
    stageRangeFlatMin: null,
    stageRangeFlatMax: null,
    simTicksProcessedCumulative: null,
    wallClockRolloutSecAvg: null,
    wallClockTradesPerMin: null,
    evolutionLastActionApplied: null,
    evolutionLastActionDetail: null,
    dataDaysLoaded: 56,
    dataManifestDaysLoaded: null,
    adaptationCycling: false,
    autonomousRecoveryRatePct: null,
    regimeDistributionSummary: null,
    stagePassNow: false,
    medianLossR: null,
    meanR: null,
    occupancy: null,
    edgeVsFirstTouch: null,
    ...partial,
  };
}

describe("buildStagePassChecklist", () => {
  const physicsProgress = {
    entropy_alive: true,
    policy_entropy: 1.2,
    constitution_violations: 0,
    stage_settlement_share: 0.8,
    geometry_net_rr: 1.2,
    e_mech: -0.32,
    median_loss_r: 1.1,
    occupancy: 0.4,
    edge_vs_first_touch: 0.01,
    oos_sharpe: -1.0,
    oos_dd_pct: 10,
  };

  it("stage 1 lists process-R gates, not WR 20%", () => {
    const list = buildStagePassChecklist(
      baseScorecard({
        passCriteriaId: "closed_loop",
        medianLossR: 1.1,
      }),
      physicsProgress,
    );
    expect(list).not.toBeNull();
    const ids = list!.requirements.filter((r) => r.kind === "gate").map((r) => r.id);
    expect(ids).toEqual([
      "volume",
      "process_r",
      "settlement",
      "entropy",
      "constitution",
      "net_rr",
    ]);
    expect(ids).not.toContain("hygiene");
    expect(list!.stageTotal).toBe(5);
    expect(list!.passMode).toBe("process");
    expect(list!.mission).toContain("WR is not a pass gate");
  });

  it("legacy trend_edgescore WR 24.5% without process-R is not Ready to pass", () => {
    const list = buildStagePassChecklist(
      baseScorecard({
        passCriteriaId: "trend_edgescore",
        tradesDone: 200,
        stagePassGateTrades: 200,
        hygieneWrFloor: 0.2,
        hygieneWrLifetime: 0.245,
        hygieneWrEffective: 0.245,
        medianLossR: null,
      }),
      {
        entropy_alive: true,
        policy_entropy: 5.69,
        expectancy_proxy: -0.255,
        constitution_violations: 0,
        stage_hold_ratio: 0.68,
      },
    );
    expect(list).not.toBeNull();
    expect(list!.allMet).toBe(false);
    expect(list!.requirements.find((r) => r.id === "process_r")!.met).toBe(false);
    expect(list!.requirements.find((r) => r.id === "hygiene")).toBeUndefined();
  });

  it("stage 1 physics complete is Ready to pass even at WR 24.5%", () => {
    const list = buildStagePassChecklist(
      baseScorecard({
        passCriteriaId: "closed_loop",
        tradesDone: 200,
        stagePassGateTrades: 200,
        medianLossR: 1.1,
        hygieneWrEffective: 0.245,
      }),
      physicsProgress,
    );
    expect(list!.allMet).toBe(true);
    expect(list!.overallTone).toBe("ok");
    const processR = list!.requirements.find((r) => r.id === "process_r")!;
    expect(processR.current).toBe("1.10R");
    expect(processR.met).toBe(true);
    const netRr = list!.requirements.find((r) => r.id === "net_rr")!;
    expect(netRr.current).toBe("1.20");
    expect(netRr.met).toBe(true);
  });

  it("stage 1 Process-R and Geometry RR stay blank when snapshot keys are missing", () => {
    const list = buildStagePassChecklist(
      baseScorecard({
        passCriteriaId: "closed_loop",
        tradesDone: 700,
        stagePassGateTrades: 150,
        medianLossR: null,
      }),
      {
        entropy_alive: true,
        constitution_violations: 0,
        stage_settlement_share: 1,
      },
    );
    expect(list!.requirements.find((r) => r.id === "process_r")!.current).toBe("—");
    expect(list!.requirements.find((r) => r.id === "net_rr")!.current).toBe("—");
    expect(list!.allMet).toBe(false);
  });

  it("Geometry RR compat-fallback reads after_cost only when SSOT key is absent", () => {
    const list = buildStagePassChecklist(
      baseScorecard({
        passCriteriaId: "closed_loop",
        tradesDone: 200,
        stagePassGateTrades: 150,
        medianLossR: 1.1,
      }),
      {
        entropy_alive: true,
        constitution_violations: 0,
        stage_settlement_share: 0.8,
        geometry_net_rr_after_cost: 1.3975,
      },
    );
    expect(list!.requirements.find((r) => r.id === "net_rr")!.current).toBe("1.40");
  });

  it("Geometry RR SSOT key wins over after_cost alias (no 1.40 paint)", () => {
    const list = buildStagePassChecklist(
      baseScorecard({
        passCriteriaId: "closed_loop",
        tradesDone: 200,
        stagePassGateTrades: 150,
        medianLossR: 1.1,
      }),
      {
        entropy_alive: true,
        constitution_violations: 0,
        stage_settlement_share: 0.8,
        geometry_net_rr: 1.1,
        geometry_net_rr_after_cost: 1.3975,
      },
    );
    expect(list!.requirements.find((r) => r.id === "net_rr")!.current).toBe("1.10");
  });

  it("stage 2 occupancy out of band is not Ready to pass even with rolling 40%", () => {
    const list = buildStagePassChecklist(
      baseScorecard({
        passCriteriaId: "selectivity",
        stageLabel: "Stage 2/5 · Selectivity",
        occupancy: 0.95,
        stageRangeFlatRatio: 0.95,
        stageRangeFlatMin: 0.3,
        stageRangeFlatMax: 0.7,
        tradesDone: 500,
        stagePassGateTrades: 250,
        stageRangeRoundTrips: 40,
        medianLossR: 1.1,
        hygieneWrRolling: 0.4,
        hygieneWrEffective: 0.4,
      }),
      { ...physicsProgress, occupancy: 0.95 },
    );
    expect(list).not.toBeNull();
    const ids = list!.requirements.filter((r) => r.kind === "gate").map((r) => r.id);
    expect(ids).toContain("occupancy");
    expect(ids).toContain("round_trips");
    expect(ids).not.toContain("durable_lifetime");
    expect(ids).not.toContain("hygiene");
    expect(list!.requirements.find((r) => r.id === "occupancy")!.met).toBe(false);
    expect(list!.allMet).toBe(false);
  });

  it("stage 2 rolling 40% with lifetime 29.9% cannot Ready to pass without process-R", () => {
    const list = buildStagePassChecklist(
      baseScorecard({
        passCriteriaId: "range_edgescore",
        stageLabel: "Stage 2/5 · Selectivity",
        occupancy: 0.4,
        stageRangeFlatRatio: 0.4,
        stageRangeFlatMin: 0.3,
        stageRangeFlatMax: 0.7,
        tradesDone: 834,
        stagePassGateTrades: 250,
        stageRangeRoundTrips: 40,
        medianLossR: null,
        hygieneWrLifetime: 0.2986,
        hygieneWrRolling: 0.4,
        hygieneWrEffective: 0.4,
      }),
      {
        ...physicsProgress,
        median_loss_r: undefined,
        stage2_consecutive_rolling_pass_windows: 7,
      },
    );
    expect(list!.allMet).toBe(false);
    expect(list!.requirements.find((r) => r.id === "process_r")!.met).toBe(false);
    expect(list!.mission).not.toContain("durable lifetime");
  });

  it("stage 3 lists occupancy + edge, not hygiene WR gates", () => {
    const list = buildStagePassChecklist(
      baseScorecard({
        passCriteriaId: "mixed_regimes",
        stageLabel: "Stage 3/5 · Mixed regimes",
        occupancy: 0.32,
        stageRangeFlatRatio: 0.32,
        stageRangeFlatMin: 0.25,
        stageRangeFlatMax: 0.75,
        medianLossR: 1.1,
        edgeVsFirstTouch: 0.0,
        tradesDone: 500,
        stagePassGateTrades: 400,
      }),
      { ...physicsProgress, occupancy: 0.32, edge_vs_first_touch: 0 },
    );
    const ids = list!.requirements.filter((r) => r.kind === "gate").map((r) => r.id);
    expect(ids).toContain("occupancy");
    expect(ids).toContain("edge");
    expect(ids).toContain("settlement");
    expect(ids).not.toContain("hygiene");
    expect(ids).not.toContain("durable_lifetime");
    expect(list!.passMode).toBe("process");
    expect(list!.stageTotal).toBe(5);
  });

  it("returns null for polish-only criteria", () => {
    expect(
      buildStagePassChecklist(baseScorecard({ passCriteriaId: "polish_complete" })),
    ).toBeNull();
  });

  it("settlement honesty missing share is dash with default tone", () => {
    const list = buildStagePassChecklist(
      baseScorecard({
        passCriteriaId: "selectivity",
        occupancy: 0.4,
        stageRangeFlatMin: 0.3,
        stageRangeFlatMax: 0.7,
        tradesDone: 500,
        stagePassGateTrades: 250,
        stageRangeRoundTrips: 40,
        medianLossR: 1.1,
      }),
      {
        entropy_alive: true,
        constitution_violations: 0,
        geometry_net_rr: 1.2,
      },
    );
    const settlement = list!.requirements.find((r) => r.id === "settlement")!;
    expect(settlement.current).toBe("—");
    expect(settlement.met).toBe(false);
  });

  it("settlement honesty 80% is green", () => {
    const list = buildStagePassChecklist(
      baseScorecard({
        passCriteriaId: "selectivity",
        occupancy: 0.4,
        stageRangeFlatMin: 0.3,
        stageRangeFlatMax: 0.7,
        tradesDone: 500,
        stagePassGateTrades: 250,
        stageRangeRoundTrips: 40,
        medianLossR: 1.1,
      }),
      physicsProgress,
    );
    const settlement = list!.requirements.find((r) => r.id === "settlement")!;
    expect(settlement.current).toBe("80%");
    expect(settlement.met).toBe(true);
    expect(settlement.tone).toBe("ok");
  });

  it("settlement honesty 30% is danger", () => {
    const list = buildStagePassChecklist(
      baseScorecard({
        passCriteriaId: "selectivity",
        occupancy: 0.4,
        stageRangeFlatMin: 0.3,
        stageRangeFlatMax: 0.7,
        tradesDone: 500,
        stagePassGateTrades: 250,
        stageRangeRoundTrips: 40,
        medianLossR: 1.1,
      }),
      { ...physicsProgress, stage_settlement_share: 0.3 },
    );
    const settlement = list!.requirements.find((r) => r.id === "settlement")!;
    expect(settlement.current).toBe("30%");
    expect(settlement.met).toBe(false);
    expect(settlement.tone).toBe("danger");
  });

  it("settlement honesty falls back to cumulative closes when share is missing", () => {
    const list = buildStagePassChecklist(
      baseScorecard({
        passCriteriaId: "selectivity",
        occupancy: 0.4,
        stageRangeFlatMin: 0.3,
        stageRangeFlatMax: 0.7,
        tradesDone: 500,
        stagePassGateTrades: 250,
        stageRangeRoundTrips: 40,
        medianLossR: 1.1,
      }),
      {
        entropy_alive: true,
        constitution_violations: 0,
        geometry_net_rr: 1.2,
        stage_closes_stop_cum: 555,
        stage_closes_target_cum: 217,
        stage_closes_time_stop_cum: 12,
        stage_closes_flatten_cum: 0,
        stage_closes_unknown_cum: 0,
      },
    );
    const settlement = list!.requirements.find((r) => r.id === "settlement")!;
    expect(settlement.current).toBe("100%");
    expect(settlement.met).toBe(true);
  });

  it("stage 4 viable plant requires skill edge and mean R vs E_mech", () => {
    const list = buildStagePassChecklist(
      baseScorecard({
        passCriteriaId: "viable_plant",
        stageLabel: "Stage 4/5 · Viable plant",
        tradesDone: 120,
        stagePassGateTrades: 100,
        occupancy: 0.4,
        medianLossR: 1.1,
        meanR: -0.2,
        edgeVsFirstTouch: 0.02,
      }),
      { ...physicsProgress, e_mech: -0.32, mean_r: -0.2, edge_vs_first_touch: 0.02 },
    );
    const ids = list!.requirements.filter((r) => r.kind === "gate").map((r) => r.id);
    expect(ids).toContain("edge");
    expect(ids).toContain("mean_r");
    expect(list!.passMode).toBe("skill");
    expect(list!.allMet).toBe(true);
  });

  it("stage 5 probe uses holdout Sharpe and DD, not WR 40%", () => {
    const list = buildStagePassChecklist(
      baseScorecard({
        passCriteriaId: "probe_handoff",
        stageLabel: "Stage 5/5 · Probe",
        tradesDone: 60,
        stagePassGateTrades: 50,
        occupancy: 0.4,
        medianLossR: 1.1,
        edgeVsFirstTouch: -0.02,
      }),
      physicsProgress,
    );
    const ids = list!.requirements.filter((r) => r.kind === "gate").map((r) => r.id);
    expect(ids).toContain("oos_sharpe");
    expect(ids).toContain("oos_dd");
    expect(ids).not.toContain("hygiene");
    expect(list!.allMet).toBe(true);
  });
});
