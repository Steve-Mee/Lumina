import { describe, expect, it } from "vitest";

import { buildStagePassChecklist } from "@/lib/birth/birthStagePassChecklist";
import type { StageScorecardModel } from "@/lib/birth/birthStageScorecardTypes";

function baseScorecard(
  partial: Partial<StageScorecardModel> & Pick<StageScorecardModel, "passCriteriaId">,
): StageScorecardModel {
  return {
    stageLabel: "Stage 1/3 · Trend",
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
    ...partial,
  };
}

describe("buildStagePassChecklist", () => {
  it("stage 1 lists gates + skill diagnostics (survival)", () => {
    const list = buildStagePassChecklist(
      baseScorecard({
        passCriteriaId: "trend_edgescore",
        hygieneWrFloor: 0.2,
        hygieneWrEffective: 0.3,
      }),
      {
        entropy_alive: true,
        policy_entropy: 1.2,
        expectancy_proxy: -0.1,
        constitution_violations: 0,
        stage_hold_ratio: 0.5,
      },
    );
    expect(list).not.toBeNull();
    const ids = list!.requirements.map((r) => r.id);
    expect(ids).toEqual([
      "volume",
      "hygiene",
      "hygiene_skill",
      "hold_band",
      "entropy",
      "expectancy",
      "expectancy_skill",
      "constitution",
    ]);
    expect(ids).not.toContain("flat_band");
    // Gate count only (skill rows excluded)
    expect(list!.totalCount).toBe(6);
    expect(list!.skillTotalCount).toBe(2);
    expect(list!.passMode).toBe("survival");
  });

  it("stage 1 survival pass: skill WR/exp red-free (accent only)", () => {
    // Matches live receipt: wr=24.5%, exp=-0.255, survival PASS
    const list = buildStagePassChecklist(
      baseScorecard({
        passCriteriaId: "trend_edgescore",
        tradesDone: 200,
        stagePassGateTrades: 200,
        hygieneWrFloor: 0.2,
        hygieneWrLifetime: 0.245,
        hygieneWrEffective: 0.245,
        hygieneWrRolling: 0.245,
        stageHoldRatio: 0.68,
        stage1WinrateRecommended: 0.45,
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
    expect(list!.allMet).toBe(true);
    expect(list!.overallTone).toBe("ok");
    const hygiene = list!.requirements.find((r) => r.id === "hygiene")!;
    expect(hygiene.met).toBe(true);
    expect(hygiene.tone).toBe("ok");
    const skillWr = list!.requirements.find((r) => r.id === "hygiene_skill")!;
    expect(skillWr.kind).toBe("skill");
    expect(skillWr.met).toBe(false);
    expect(skillWr.tone).toBe("accent");
    const expGate = list!.requirements.find((r) => r.id === "expectancy")!;
    expect(expGate.met).toBe(true);
    expect(expGate.tone).toBe("ok");
    const skillExp = list!.requirements.find((r) => r.id === "expectancy_skill")!;
    expect(skillExp.met).toBe(false);
    expect(skillExp.tone).toBe("accent");
    // No danger tones on skill diagnostics
    for (const r of list!.requirements.filter((x) => x.kind === "skill")) {
      expect(r.tone).not.toBe("danger");
    }
  });

  it("stage 2 lists flat band instead of hold band / hygiene WR", () => {
    const list = buildStagePassChecklist(
      baseScorecard({
        passCriteriaId: "range_edgescore",
        stageLabel: "Stage 2/3 · Range patience",
        stageRangeFlatRatio: 0.95,
        stageRangeFlatMin: 0.3,
        stageRangeFlatMax: 0.7,
        tradesDone: 500,
        stagePassGateTrades: 300,
      }),
      {
        entropy_alive: true,
        policy_entropy: 2,
        expectancy_proxy: -0.05,
        constitution_violations: 0,
      },
    );
    expect(list).not.toBeNull();
    const ids = list!.requirements.map((r) => r.id);
    expect(ids).toContain("flat_band");
    expect(ids).not.toContain("hold_band");
    expect(ids).not.toContain("hygiene");
    const flat = list!.requirements.find((r) => r.id === "flat_band")!;
    expect(flat.met).toBe(false);
    expect(flat.tone).toBe("danger");
    expect(flat.kind).toBe("gate");
    expect(list!.requirements.find((r) => r.id === "volume")!.met).toBe(true);
  });

  it("stage 3 lists hygiene + hold cap as gates", () => {
    const list = buildStagePassChecklist(
      baseScorecard({
        passCriteriaId: "mixed_edgescore",
        stageLabel: "Stage 3/3 · Mixed",
        stageHoldRatio: 0.5,
        stageHoldMax: 0.7,
        hygieneWrEffective: 0.4,
        hygieneWrFloor: 0.35,
      }),
      {
        entropy_alive: true,
        expectancy_proxy: 0,
        constitution_violations: 0,
      },
    );
    const ids = list!.requirements.map((r) => r.id);
    expect(ids).toContain("hygiene");
    expect(ids).toContain("hold_cap");
    expect(ids).not.toContain("flat_band");
    expect(ids).not.toContain("hold_band");
    expect(list!.requirements.find((r) => r.id === "hygiene")!.kind).toBe("gate");
    expect(list!.passMode).toBe("skill");
  });

  it("returns null for polish-only criteria", () => {
    expect(
      buildStagePassChecklist(baseScorecard({ passCriteriaId: "polish_complete" })),
    ).toBeNull();
  });
});
