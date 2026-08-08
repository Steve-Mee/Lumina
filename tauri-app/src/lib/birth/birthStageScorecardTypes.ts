export type StageScorecardHealth = "advancing" | "working" | "stale";

export interface StageScorecardModel {
  stageLabel: string;
  goalLabel: string;
  tradesDone: number;
  tradesRequired: number;
  tradesPct: number;
  metricLabel: string;
  metricValue: number | null;
  metricTarget: number | null;
  metricMin: number | null;
  metricMax: number | null;
  metricPct: number;
  passCriteriaId: string;
  subPhase: string;
  subPhaseLabel: string;
  patternsMined: number;
  learningAttempt: number;
  explorationActive: boolean;
  stageWallRemainingSec: number | null;
  stageRangeRoundTrips: number | null;
  heartbeatSec: number | null;
  health: StageScorecardHealth;
  healthHint: string;
  isCurriculum: boolean;
  blockerLabel: string | null;
  blockerDetail: string | null;
  provisionalPass: boolean;
  volumeGateStatus: "PASSED" | "PENDING" | null;
  winrateTrendSlope: number | null;
  retriesThisStage: number;
  adaptationTier: number | null;
  maxAdaptationTiers: number | null;
  maxStageRetries: number | null;
  autoRecoveryActive: boolean;
  adaptationEnabled: boolean;
  wallBehavior: string | null;
  escalationLevel: number | null;
  lastAdaptationReason: string | null;
  lastAdaptationChunk: number | null;
  lastAdaptationSummary: string | null;
  evolutionPhase: string | null;
  evolutionStep: number | null;
  evolutionStepLabel: string | null;
  evolutionActionsTotal: number | null;
  evolutionActionsCompleted: number | null;
  evolutionPhantomSteps: number | null;
  evolutionActionsRemaining: number | null;
  plateauElapsedSec: number | null;
  tradesBeyondGate: number | null;
  evolutionRolloutsThisStep: number | null;
  evolutionRolloutsMax: number | null;
  stallRemediationCycle: number | null;
  stallRemediationStep: number | null;
  stallRemediationMaxSteps: number | null;
  stallRemediationMaxCycles: number | null;
  recommendedRecoveryAction: string | null;
  holdTrapDetected: boolean;
  stage1WinrateGate: number | null;
  stage1WinrateRecommended: number | null;
  stagePassGateTrades: number | null;
  stageBudgetTrades: number | null;
  plateauMinStageTrades: number | null;
  plateauQuarantineActive: boolean;
  plateauQuarantineRolloutsRemaining: number | null;
  plateauQuarantineTradesRemaining: number | null;
  plateauQuarantineTradesRemainingCount: number | null;
  rollingWinrate500: number | null;
  /** true_window | partial_window | lifetime_fallback */
  rollingWinrateSource: string | null;
  rollingWindowTradesCovered: number | null;
  hygieneWrFloor: number | null;
  hygieneWrLifetime: number | null;
  hygieneWrRolling: number | null;
  hygieneWrEffective: number | null;
  /** lifetime | rolling | neither */
  hygieneWrSource: string | null;
  rollingWrEligible: boolean | null;
  /** Stage hold ratio (hold_signals/total_signals) — stage3 gate hold≤max */
  stageHoldRatio: number | null;
  stageHoldMax: number | null;
  /**
   * Position flat ratio (stage-2 range activity band 30–70%).
   * Prefer stage_range_flat_ratio; hold_ratio fallback when range telemetry is thin.
   */
  stageRangeFlatRatio: number | null;
  stageRangeFlatMin: number | null;
  stageRangeFlatMax: number | null;
  simTicksProcessedCumulative: number | null;
  wallClockRolloutSecAvg: number | null;
  wallClockTradesPerMin: number | null;
  evolutionLastActionApplied: boolean | null;
  evolutionLastActionDetail: string | null;
  dataDaysLoaded: number | null;
  dataManifestDaysLoaded: number | null;
  adaptationCycling: boolean;
  autonomousRecoveryRatePct: number | null;
  regimeDistributionSummary: string | null;
}
