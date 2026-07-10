import type { BirthProgressPayload } from "@/lib/birthClient";

import { normalizeToken, parseProgressTimestamp } from "@/lib/birth/birthModelUtils";
import { extractSimProgress } from "@/lib/birth/birthProgressExtract";

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
  simTicksProcessedCumulative: number | null;
  wallClockRolloutSecAvg: number | null;
  wallClockTradesPerMin: number | null;
  evolutionLastActionApplied: boolean | null;
  evolutionLastActionDetail: string | null;
  dataDaysLoaded: number | null;
  dataManifestDaysLoaded: number | null;
  adaptationCycling: boolean;
  regimeDistributionSummary: string | null;
}

const STALE_WORKING_SEC = 120;
const STALE_WARN_SEC = 600;

function parseProgressTimestamp(progress: BirthProgressPayload | undefined): number | null {
  const raw = progress?.timestamp;
  if (!raw) return null;
  const ms = Date.parse(raw);
  return Number.isFinite(ms) ? ms : null;
}

function resolveAdaptationCycling(
  progress: BirthProgressPayload | undefined,
  heartbeatSec: number | null,
): boolean {
  if (!progress?.auto_recovery_active) return false;
  const tier = Math.max(0, Number(progress.adaptation_tier ?? 0));
  const maxTiers = Math.max(1, Number(progress.max_adaptation_tiers ?? 4));
  if (tier < maxTiers - 1) return false;
  if (progress.is_advancing === true) return false;
  if (heartbeatSec == null || heartbeatSec > STALE_WORKING_SEC) return false;
  return true;
}

function resolveScorecardHealth(
  progress: BirthProgressPayload | undefined,
  heartbeatSec: number | null,
): { health: StageScorecardHealth; healthHint: string } {
  if (heartbeatSec == null) {
    return { health: "working", healthHint: "Waiting for progress update…" };
  }
  if (resolveAdaptationCycling(progress, heartbeatSec)) {
    return {
      health: "working",
      healthHint: "Recovery cycling — geen nieuwe trades",
    };
  }
  if (progress?.is_advancing === true && heartbeatSec <= STALE_WORKING_SEC) {
    return { health: "advancing", healthHint: "Progress advancing" };
  }
  if (heartbeatSec <= STALE_WORKING_SEC) {
    return {
      health: "working",
      healthHint: "Active — PPO batch may run silently (5–20 min is normal)",
    };
  }
  if (heartbeatSec <= STALE_WARN_SEC) {
    return {
      health: "working",
      healthHint: "No recent update — long PPO batch may still be running",
    };
  }
  return {
    health: "stale",
    healthHint: "Possible stall — check logs if metrics unchanged for 10+ min",
  };
}

function metricPctForCriteria(
  passCriteriaId: string,
  metricValue: number | null,
  metricTarget: number | null,
  metricMin: number | null,
  metricMax: number | null,
): number {
  if (metricValue == null) return 0;
  if (passCriteriaId === "trend_winrate" && metricTarget != null && metricTarget > 0) {
    return Math.min(100, (metricValue / metricTarget) * 100);
  }
  if (passCriteriaId === "range_hold_ratio" && metricMin != null && metricMax != null) {
    if (metricValue >= metricMin && metricValue <= metricMax) return 100;
    if (metricValue < metricMin && metricMin > 0) {
      return Math.min(100, (metricValue / metricMin) * 100);
    }
    if (metricValue > metricMax && metricMax > 0) {
      return Math.max(0, 100 - ((metricValue - metricMax) / metricMax) * 100);
    }
  }
  if (passCriteriaId === "range_roundtrip" && metricMin != null && metricMax != null) {
    if (metricValue >= metricMin && metricValue <= metricMax) return 100;
    if (metricValue < metricMin && metricMin > 0) {
      return Math.min(100, (metricValue / metricMin) * 100);
    }
    if (metricValue > metricMax && metricMax > 0) {
      return Math.max(0, 100 - ((metricValue - metricMax) / metricMax) * 100);
    }
  }
  if (passCriteriaId === "mixed_constitution") {
    return metricValue <= 0 ? 100 : 0;
  }
  return 0;
}

function inferPassCriteriaFromStage(
  curriculumStage: string,
  stageTarget: number,
): {
  id: string;
  goalLabel: string;
  metricLabel: string;
  metricTarget: number | null;
  metricMin: number | null;
  metricMax: number | null;
  displayName: string;
  curriculumIndex: number;
} {
  const stage = curriculumStage.toLowerCase();
  if (stage === "stage2_range") {
    return {
      id: "range_roundtrip",
      goalLabel: `≥${stageTarget} trades · position-flat 30–70% on range ticks`,
      metricLabel: "Position flat",
      metricTarget: null,
      metricMin: 0.3,
      metricMax: 0.7,
      displayName: "Range patience",
      curriculumIndex: 2,
    };
  }
  if (stage === "stage3_mixed") {
    return {
      id: "mixed_constitution",
      goalLabel: `≥${stageTarget} trades · 0 constitution violations`,
      metricLabel: "Violations",
      metricTarget: 0,
      metricMin: null,
      metricMax: null,
      displayName: "Mixed regimes",
      curriculumIndex: 3,
    };
  }
  return {
    id: "trend_winrate",
    goalLabel: `≥${stageTarget} trades · winrate ≥45%`,
    metricLabel: "Winrate",
    metricTarget: 0.45,
    metricMin: null,
    metricMax: null,
    displayName: "Trend",
    curriculumIndex: 1,
  };
}

const ADAPTATION_REASON_LABELS: Record<string, string> = {
  negative_winrate_trend_after_volume_gate: "Negative winrate trend",
  metrics_not_improving_within_wall: "Metrics stalled after volume gate",
  default_stall_retry: "Standard stall recovery",
};

function humanAdaptationReason(reason: string): string {
  const key = reason.trim();
  return ADAPTATION_REASON_LABELS[key] ?? key.replace(/_/g, " ");
}

function extractAdaptationFields(progress: BirthProgressPayload | undefined): {
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
  };
}

export function extractStageScorecard(
  progress: BirthProgressPayload | undefined,
  nowMs: number = Date.now(),
): StageScorecardModel | null {
  const curriculumStage = String(progress?.curriculum_stage ?? "").trim();
  const phase = normalizeToken(progress?.phase);
  const isCurriculum =
    Boolean(curriculumStage) &&
    !["completed", "practice_completed", "certificate_failed"].includes(phase);
  const isPolishOrOos = phase === "ppo_polish" || phase === "oos_evaluation";
  if (!isCurriculum && !isPolishOrOos) {
    return null;
  }

  const sim = extractSimProgress(progress);
  const inferred = curriculumStage
    ? inferPassCriteriaFromStage(curriculumStage, sim.target || 100)
    : null;

  const curriculumIndex = Number(
    progress?.curriculum_index ?? inferred?.curriculumIndex ?? 0,
  );
  const curriculumTotal = Number(progress?.curriculum_total ?? 3);
  const displayName =
    String(progress?.stage_display_name ?? "").trim() ||
    inferred?.displayName ||
    curriculumStage.replace(/_/g, " ");
  const stageLabel =
    curriculumIndex > 0 && curriculumIndex <= curriculumTotal
      ? `Stage ${curriculumIndex}/${curriculumTotal} · ${displayName}`
      : displayName;

  const passCriteriaId = String(
    progress?.pass_criteria_id ?? inferred?.id ?? "trend_winrate",
  );
  const goalLabel =
    String(progress?.pass_criteria_label ?? "").trim() ||
    inferred?.goalLabel ||
    `≥${sim.target} trades · winrate ≥45%`;

  let metricValue: number | null = null;
  let metricLabel = String(
    progress?.pass_metric_label ?? inferred?.metricLabel ?? "Winrate",
  );
  const metricTarget =
    progress?.pass_metric_target != null
      ? Number(progress.pass_metric_target)
      : inferred?.metricTarget ?? null;
  const metricMin =
    progress?.pass_metric_min != null
      ? Number(progress.pass_metric_min)
      : inferred?.metricMin ?? null;
  const metricMax =
    progress?.pass_metric_max != null
      ? Number(progress.pass_metric_max)
      : inferred?.metricMax ?? null;

  if (passCriteriaId === "trend_winrate") {
    if (progress?.stage_winrate != null && Number.isFinite(Number(progress.stage_winrate))) {
      metricValue = Number(progress.stage_winrate);
    } else if (
      progress?.stage_wins !== undefined &&
      progress?.stage_wins !== null &&
      sim.done > 0
    ) {
      metricValue = Number(progress.stage_wins) / sim.done;
    }
  } else if (passCriteriaId === "range_hold_ratio") {
    metricValue =
      progress?.stage_hold_ratio != null
        ? Number(progress.stage_hold_ratio)
        : progress?.hold_ratio != null
          ? Number(progress.hold_ratio)
          : null;
  } else if (passCriteriaId === "range_roundtrip") {
    metricValue =
      progress?.stage_range_flat_ratio != null
        ? Number(progress.stage_range_flat_ratio)
        : progress?.stage_hold_ratio != null
          ? Number(progress.stage_hold_ratio)
          : progress?.hold_ratio != null
            ? Number(progress.hold_ratio)
            : null;
  } else if (passCriteriaId === "mixed_constitution") {
    const sessionViolations = progress?.constitution_violations_session;
    metricValue = Number(
      sessionViolations != null && Number.isFinite(Number(sessionViolations))
        ? sessionViolations
        : progress?.constitution_violations ?? 0,
    );
    metricLabel = "Violations (session)";
  }

  const ts = parseProgressTimestamp(progress);
  const heartbeatSec = ts != null ? Math.max(0, Math.round((nowMs - ts) / 1000)) : null;
  const { health, healthHint } = resolveScorecardHealth(progress, heartbeatSec);
  const adaptationCycling = resolveAdaptationCycling(progress, heartbeatSec);
  const manifestDaysRaw = progress?.data_manifest?.days_loaded;
  const dataManifestDaysLoaded =
    manifestDaysRaw != null && Number.isFinite(Number(manifestDaysRaw))
      ? Math.max(0, Number(manifestDaysRaw))
      : null;

  const tradesTargetMet = sim.target > 0 && sim.done >= sim.target;
  let blockerLabel: string | null = null;
  let blockerDetail: string | null = null;
  if (tradesTargetMet) {
    const blockerMetric = String(progress?.stage_blocker_metric ?? "").trim();
    const passReason = String(progress?.pass_reason ?? "").trim();
    if (passReason) {
      blockerDetail = passReason;
      blockerLabel = "Blocking metric";
    } else if (passCriteriaId === "trend_winrate" && metricValue != null && metricTarget != null) {
      if (metricValue < metricTarget) {
        blockerLabel = "Winrate";
        blockerDetail = `${(metricValue * 100).toFixed(0)}% — need ${(metricTarget * 100).toFixed(0)}%`;
      }
    } else if (blockerMetric) {
      blockerLabel = blockerMetric.replace(/_/g, " ");
      if (progress?.stage_blocker_value != null) {
        blockerDetail = String(progress.stage_blocker_value);
      }
    }
  }

  return {
    stageLabel,
    goalLabel,
    tradesDone: sim.done,
    tradesRequired: sim.target,
    tradesPct: sim.pct,
    metricLabel,
    metricValue,
    metricTarget,
    metricMin,
    metricMax,
    metricPct: metricPctForCriteria(
      passCriteriaId,
      metricValue,
      metricTarget,
      metricMin,
      metricMax,
    ),
    passCriteriaId,
    subPhase: String(progress?.sub_phase ?? progress?.phase ?? ""),
    subPhaseLabel:
      String(progress?.sub_phase_label ?? "").trim() ||
      String(progress?.phase ?? "").replace(/_/g, " "),
    patternsMined: Number(progress?.patterns_mined ?? 0),
    learningAttempt: Number(progress?.learning_attempt ?? 0),
    explorationActive: Boolean(progress?.exploration_active),
    stageWallRemainingSec:
      progress?.stage_wall_remaining_sec != null
        ? Math.max(0, Number(progress.stage_wall_remaining_sec))
        : null,
    stageRangeRoundTrips:
      progress?.stage_range_round_trips != null
        ? Math.max(0, Number(progress.stage_range_round_trips))
        : null,
    heartbeatSec,
    health,
    healthHint,
    isCurriculum,
    blockerLabel,
    blockerDetail,
    provisionalPass: Boolean(progress?.provisional_pass),
    ...extractAdaptationFields(progress),
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
    dataManifestDaysLoaded,
    adaptationCycling,
    regimeDistributionSummary:
      String(progress?.regime_distribution_summary ?? "").trim() || null,
  };
}
