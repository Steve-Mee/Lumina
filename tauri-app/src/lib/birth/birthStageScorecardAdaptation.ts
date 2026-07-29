import type { BirthProgressPayload } from "@/lib/birthClient";

const ADAPTATION_REASON_LABELS: Record<string, string> = {
  negative_winrate_trend_after_volume_gate: "Negative winrate trend",
  metrics_not_improving_within_wall: "Metrics stalled after volume gate",
  default_stall_retry: "Standard stall recovery",
};

function humanAdaptationReason(reason: string): string {
  const key = reason.trim();
  return ADAPTATION_REASON_LABELS[key] ?? key.replace(/_/g, " ");
}

export function extractAdaptationFields(progress: BirthProgressPayload | undefined): {
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
  autonomousRecoveryRatePct: number | null;
} {
  const rawGate = String(progress?.volume_gate_status ?? "").trim().toUpperCase();
  const volumeGateStatus =
    rawGate === "PASSED" ? "PASSED" : rawGate === "PENDING" ? "PENDING" : null;
  const winrateTrendSlope =
    progress?.winrate_trend_slope != null && Number.isFinite(Number(progress.winrate_trend_slope))
      ? Number(progress.winrate_trend_slope)
      : null;
  const retriesThisStage = Math.max(0, Number(progress?.retries_this_stage ?? 0) || 0);
  const adaptationTier =
    progress?.adaptation_tier != null && Number.isFinite(Number(progress.adaptation_tier))
      ? Math.max(0, Number(progress.adaptation_tier))
      : null;
  const maxAdaptationTiers =
    progress?.max_adaptation_tiers != null && Number.isFinite(Number(progress.max_adaptation_tiers))
      ? Math.max(1, Number(progress.max_adaptation_tiers))
      : null;
  const maxStageRetries =
    progress?.max_stage_retries != null && Number.isFinite(Number(progress.max_stage_retries))
      ? Math.max(1, Number(progress.max_stage_retries))
      : null;
  const autoRecoveryActive = Boolean(progress?.auto_recovery_active);
  const adaptationEnabled = progress?.adaptation_enabled !== false;
  const wallBehavior = String(progress?.wall_behavior ?? "").trim() || null;
  const escalationLevel =
    progress?.escalation_level != null && Number.isFinite(Number(progress.escalation_level))
      ? Math.max(0, Number(progress.escalation_level))
      : null;

  const last = progress?.last_adaptation;
  let lastAdaptationReason: string | null = null;
  let lastAdaptationChunk: number | null = null;
  let lastAdaptationSummary: string | null = null;
  if (last && typeof last === "object" && !Array.isArray(last)) {
    const reasonRaw = String(last.reason ?? "").trim();
    if (reasonRaw) {
      lastAdaptationReason = humanAdaptationReason(reasonRaw);
    }
    if (last.chunk_target != null && Number.isFinite(Number(last.chunk_target))) {
      lastAdaptationChunk = Number(last.chunk_target);
    }
    if (lastAdaptationReason) {
      const parts = [lastAdaptationReason];
      if (lastAdaptationChunk != null) {
        parts.push(`chunk ${lastAdaptationChunk}`);
      }
      if (adaptationTier != null && maxAdaptationTiers != null) {
        parts.push(`tier ${adaptationTier + 1}/${maxAdaptationTiers}`);
      } else if (escalationLevel != null) {
        parts.push(`L${escalationLevel}`);
      }
      lastAdaptationSummary = parts.join(" · ");
    }
  }

  return {
    volumeGateStatus,
    winrateTrendSlope,
    retriesThisStage,
    adaptationTier,
    maxAdaptationTiers,
    maxStageRetries,
    autoRecoveryActive,
    adaptationEnabled,
    wallBehavior,
    escalationLevel,
    lastAdaptationReason,
    lastAdaptationChunk,
    lastAdaptationSummary,
    autonomousRecoveryRatePct:
      progress?.autonomous_recovery_rate_pct != null &&
      Number.isFinite(Number(progress.autonomous_recovery_rate_pct))
        ? Number(progress.autonomous_recovery_rate_pct)
        : null,
  };
}

/** Plateau / evolution / hygiene telemetry packed onto the stage scorecard model. */
export function extractScorecardProgressExtras(
  progress: BirthProgressPayload | undefined,
  opts: {
    adaptationCycling: boolean;
    dataManifestDaysLoaded: number | null;
    stageHoldRatio: number | null;
    stageHoldMax: number | null;
  },
): {
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
  rollingWinrateSource: string | null;
  rollingWindowTradesCovered: number | null;
  hygieneWrFloor: number | null;
  hygieneWrLifetime: number | null;
  hygieneWrRolling: number | null;
  hygieneWrEffective: number | null;
  hygieneWrSource: string | null;
  rollingWrEligible: boolean | null;
  stageHoldRatio: number | null;
  stageHoldMax: number | null;
  simTicksProcessedCumulative: number | null;
  wallClockRolloutSecAvg: number | null;
  wallClockTradesPerMin: number | null;
  evolutionLastActionApplied: boolean | null;
  evolutionLastActionDetail: string | null;
  dataDaysLoaded: number | null;
  dataManifestDaysLoaded: number | null;
  adaptationCycling: boolean;
  regimeDistributionSummary: string | null;
} {
  return {
    evolutionPhase: String(progress?.evolution_phase ?? "").trim() || null,
    evolutionStep:
      progress?.evolution_step != null && Number.isFinite(Number(progress.evolution_step))
        ? Math.max(0, Number(progress.evolution_step))
        : null,
    evolutionStepLabel: String(progress?.evolution_step_label ?? "").trim() || null,
    evolutionActionsTotal:
      progress?.evolution_actions_total != null &&
      Number.isFinite(Number(progress.evolution_actions_total))
        ? Math.max(0, Number(progress.evolution_actions_total))
        : null,
    evolutionActionsCompleted:
      progress?.evolution_actions_completed != null &&
      Number.isFinite(Number(progress.evolution_actions_completed))
        ? Math.max(0, Number(progress.evolution_actions_completed))
        : null,
    evolutionPhantomSteps:
      progress?.evolution_phantom_steps != null &&
      Number.isFinite(Number(progress.evolution_phantom_steps))
        ? Math.max(0, Number(progress.evolution_phantom_steps))
        : null,
    evolutionActionsRemaining:
      progress?.evolution_actions_remaining != null &&
      Number.isFinite(Number(progress.evolution_actions_remaining))
        ? Math.max(0, Number(progress.evolution_actions_remaining))
        : null,
    plateauElapsedSec:
      progress?.plateau_elapsed_sec != null &&
      Number.isFinite(Number(progress.plateau_elapsed_sec))
        ? Math.max(0, Number(progress.plateau_elapsed_sec))
        : null,
    tradesBeyondGate:
      progress?.trades_beyond_gate != null &&
      Number.isFinite(Number(progress.trades_beyond_gate))
        ? Math.max(0, Number(progress.trades_beyond_gate))
        : null,
    evolutionRolloutsThisStep:
      progress?.plateau_evolution_rollouts_this_step != null &&
      Number.isFinite(Number(progress.plateau_evolution_rollouts_this_step))
        ? Math.max(0, Number(progress.plateau_evolution_rollouts_this_step))
        : null,
    evolutionRolloutsMax:
      progress?.plateau_evolution_rollouts_max != null &&
      Number.isFinite(Number(progress.plateau_evolution_rollouts_max))
        ? Math.max(0, Number(progress.plateau_evolution_rollouts_max))
        : null,
    stallRemediationCycle:
      progress?.stall_remediation_cycle != null &&
      Number.isFinite(Number(progress.stall_remediation_cycle))
        ? Math.max(0, Number(progress.stall_remediation_cycle))
        : null,
    stallRemediationStep:
      progress?.stall_remediation_step != null &&
      Number.isFinite(Number(progress.stall_remediation_step))
        ? Math.max(0, Number(progress.stall_remediation_step))
        : null,
    stallRemediationMaxSteps:
      progress?.stall_remediation_max_steps != null &&
      Number.isFinite(Number(progress.stall_remediation_max_steps))
        ? Math.max(0, Number(progress.stall_remediation_max_steps))
        : null,
    stallRemediationMaxCycles:
      progress?.stall_remediation_max_cycles != null &&
      Number.isFinite(Number(progress.stall_remediation_max_cycles))
        ? Math.max(0, Number(progress.stall_remediation_max_cycles))
        : null,
    recommendedRecoveryAction:
      String(progress?.recommended_recovery_action ?? "").trim() || null,
    holdTrapDetected: Boolean(progress?.hold_trap_detected),
    stage1WinrateGate:
      progress?.stage1_winrate_gate != null &&
      Number.isFinite(Number(progress.stage1_winrate_gate))
        ? Number(progress.stage1_winrate_gate)
        : null,
    stage1WinrateRecommended:
      progress?.stage1_winrate_recommended != null &&
      Number.isFinite(Number(progress.stage1_winrate_recommended))
        ? Number(progress.stage1_winrate_recommended)
        : null,
    stagePassGateTrades:
      progress?.stage_pass_gate_trades != null &&
      Number.isFinite(Number(progress.stage_pass_gate_trades))
        ? Math.max(0, Number(progress.stage_pass_gate_trades))
        : null,
    stageBudgetTrades:
      progress?.stage_budget_trades != null &&
      Number.isFinite(Number(progress.stage_budget_trades))
        ? Math.max(0, Number(progress.stage_budget_trades))
        : null,
    plateauMinStageTrades:
      progress?.plateau_min_stage_trades != null &&
      Number.isFinite(Number(progress.plateau_min_stage_trades))
        ? Math.max(0, Number(progress.plateau_min_stage_trades))
        : null,
    plateauQuarantineActive: Boolean(progress?.plateau_quarantine_active),
    plateauQuarantineRolloutsRemaining:
      progress?.plateau_quarantine_rollouts_remaining != null &&
      Number.isFinite(Number(progress.plateau_quarantine_rollouts_remaining))
        ? Math.max(0, Number(progress.plateau_quarantine_rollouts_remaining))
        : null,
    plateauQuarantineTradesRemaining:
      progress?.plateau_quarantine_trades_remaining != null &&
      Number.isFinite(Number(progress.plateau_quarantine_trades_remaining))
        ? Math.max(0, Number(progress.plateau_quarantine_trades_remaining))
        : null,
    plateauQuarantineTradesRemainingCount:
      progress?.plateau_quarantine_trades_remaining_count != null &&
      Number.isFinite(Number(progress.plateau_quarantine_trades_remaining_count))
        ? Math.max(0, Number(progress.plateau_quarantine_trades_remaining_count))
        : null,
    rollingWinrate500:
      progress?.rolling_winrate_500 != null &&
      Number.isFinite(Number(progress.rolling_winrate_500))
        ? Number(progress.rolling_winrate_500)
        : null,
    rollingWinrateSource: String(progress?.rolling_winrate_source ?? "").trim() || null,
    rollingWindowTradesCovered:
      progress?.rolling_window_trades_covered != null &&
      Number.isFinite(Number(progress.rolling_window_trades_covered))
        ? Math.max(0, Number(progress.rolling_window_trades_covered))
        : null,
    hygieneWrFloor:
      progress?.hygiene_wr_floor != null && Number.isFinite(Number(progress.hygiene_wr_floor))
        ? Number(progress.hygiene_wr_floor)
        : null,
    hygieneWrLifetime:
      progress?.hygiene_wr_lifetime != null &&
      Number.isFinite(Number(progress.hygiene_wr_lifetime))
        ? Number(progress.hygiene_wr_lifetime)
        : progress?.stage_winrate != null && Number.isFinite(Number(progress.stage_winrate))
          ? Number(progress.stage_winrate)
          : null,
    hygieneWrRolling:
      progress?.hygiene_wr_rolling != null &&
      Number.isFinite(Number(progress.hygiene_wr_rolling))
        ? Number(progress.hygiene_wr_rolling)
        : progress?.rolling_winrate_500 != null &&
            Number.isFinite(Number(progress.rolling_winrate_500))
          ? Number(progress.rolling_winrate_500)
          : null,
    hygieneWrEffective:
      progress?.hygiene_wr_effective != null &&
      Number.isFinite(Number(progress.hygiene_wr_effective))
        ? Number(progress.hygiene_wr_effective)
        : null,
    hygieneWrSource: String(progress?.hygiene_wr_source ?? "").trim() || null,
    rollingWrEligible:
      progress?.rolling_wr_eligible != null ? Boolean(progress.rolling_wr_eligible) : null,
    stageHoldRatio: opts.stageHoldRatio,
    stageHoldMax: opts.stageHoldMax,
    simTicksProcessedCumulative:
      progress?.sim_ticks_processed_cumulative != null &&
      Number.isFinite(Number(progress.sim_ticks_processed_cumulative))
        ? Math.max(0, Number(progress.sim_ticks_processed_cumulative))
        : null,
    wallClockRolloutSecAvg:
      progress?.wall_clock_rollout_sec_avg != null &&
      Number.isFinite(Number(progress.wall_clock_rollout_sec_avg))
        ? Number(progress.wall_clock_rollout_sec_avg)
        : null,
    wallClockTradesPerMin:
      progress?.wall_clock_trades_per_min != null &&
      Number.isFinite(Number(progress.wall_clock_trades_per_min))
        ? Number(progress.wall_clock_trades_per_min)
        : null,
    evolutionLastActionApplied:
      progress?.evolution_last_action_applied != null
        ? Boolean(progress.evolution_last_action_applied)
        : null,
    evolutionLastActionDetail:
      String(progress?.evolution_last_action_detail ?? "").trim() || null,
    dataDaysLoaded:
      progress?.data_days_loaded != null &&
      Number.isFinite(Number(progress.data_days_loaded))
        ? Math.max(0, Number(progress.data_days_loaded))
        : null,
    dataManifestDaysLoaded: opts.dataManifestDaysLoaded,
    adaptationCycling: opts.adaptationCycling,
    regimeDistributionSummary:
      String(progress?.regime_distribution_summary ?? "").trim() || null,
  };
}
