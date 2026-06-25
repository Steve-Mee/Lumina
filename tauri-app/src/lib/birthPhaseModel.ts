import type { BirthProgressPayload, BirthStatusPayload } from "@/lib/birthClient";

export type BirthMilestoneId = "dna" | "fitness" | "strategies" | "refinement" | "awakening";

export type MilestoneState = "pending" | "active" | "complete";

export interface BirthMilestone {
  id: BirthMilestoneId;
  label: string;
  headline: string;
  state: MilestoneState;
}

export const BIRTH_MILESTONE_ORDER: BirthMilestoneId[] = [
  "dna",
  "fitness",
  "strategies",
  "refinement",
  "awakening",
];

const MILESTONE_META: Record<
  BirthMilestoneId,
  { label: string; headline: string; stages: string[]; phases: string[] }
> = {
  dna: {
    label: "Real market history",
    headline: "Loading real market history…",
    stages: ["detected", "pipeline_boot", "checkpoint_available"],
    phases: ["detected", "checkpoint_available", "loading_history"],
  },
  fitness: {
    label: "Regime map",
    headline: "Building regime map…",
    stages: ["loading_data", "historical_loaded", "synthetic_top_up"],
    phases: ["loading_history", "loading_history_failed", "ticks_ready"],
  },
  strategies: {
    label: "Curriculum training",
    headline: "Curriculum stage active…",
    stages: ["training_running"],
    phases: [
      "curriculum_stage",
      "curriculum_learning",
      "curriculum_research",
      "data_expansion",
      "parallel_simulation",
      "ppo_training",
    ],
  },
  refinement: {
    label: "PPO polish + OOS eval",
    headline: "Policy polish and OOS Sharpe check…",
    stages: ["ppo_training"],
    phases: ["ppo_polish", "oos_evaluation"],
  },
  awakening: {
    label: "Birth Certificate v2",
    headline: "Birth Certificate v2 issued",
    stages: ["completed", "practice_completed"],
    phases: ["completed", "practice_completed", "certificate_issued"],
  },
};

function normalizeToken(value: unknown): string {
  return String(value ?? "")
    .trim()
    .toLowerCase();
}

export function resolveActiveMilestone(
  progress: BirthProgressPayload | undefined,
  status: string,
): BirthMilestoneId {
  const stage = normalizeToken(progress?.stage);
  const phase = normalizeToken(progress?.phase);
  const normalizedStatus = normalizeToken(status);

  if (normalizedStatus === "completed" || stage === "completed" || stage === "practice_completed") {
    return "awakening";
  }

  for (let i = BIRTH_MILESTONE_ORDER.length - 1; i >= 0; i -= 1) {
    const id = BIRTH_MILESTONE_ORDER[i]!;
    const meta = MILESTONE_META[id];
    if (meta.stages.includes(stage) || meta.phases.includes(phase)) {
      return id;
    }
  }

  if (phase === "ppo_polish" || phase === "oos_evaluation") return "refinement";
  if (phase === "ppo_training") return "strategies";
  if (phase.includes("simulation") || stage.includes("simulation") || stage.includes("training")) {
    return "strategies";
  }
  if (phase.includes("loading") || stage.includes("loading") || stage.includes("historical")) {
    return "fitness";
  }

  return "dna";
}

export function buildMilestones(
  progress: BirthProgressPayload | undefined,
  status: string,
): BirthMilestone[] {
  const activeId = resolveActiveMilestone(progress, status);
  const activeIndex = BIRTH_MILESTONE_ORDER.indexOf(activeId);

  return BIRTH_MILESTONE_ORDER.map((id, index) => {
    let state: MilestoneState = "pending";
    if (index < activeIndex) state = "complete";
    else if (index === activeIndex) state = "active";
    const meta = MILESTONE_META[id];
    return {
      id,
      label: meta.label,
      headline: meta.headline,
      state,
    };
  });
}

export interface CompactMilestoneView {
  items: BirthMilestone[];
  upcomingCount: number;
}

/** Show completed + active + next milestone only (max 3 visible). */
export function buildCompactMilestones(
  progress: BirthProgressPayload | undefined,
  status: string,
): CompactMilestoneView {
  const all = buildMilestones(progress, status);
  const activeIndex = all.findIndex((m) => m.state === "active");
  if (activeIndex < 0) {
    return { items: all.slice(0, 1), upcomingCount: Math.max(0, all.length - 1) };
  }
  const start = Math.max(0, activeIndex - 1);
  const end = Math.min(all.length, activeIndex + 2);
  const items = all.slice(start, end);
  const upcomingCount = Math.max(0, all.length - end);
  return { items, upcomingCount };
}

export function resolveBirthHeadline(
  milestones: BirthMilestone[],
  status: string,
  progress?: BirthProgressPayload,
  certificateOk?: boolean,
): string {
  const failedPayload: BirthStatusPayload = {
    status,
    progress,
    certificate_ok: certificateOk,
  };
  if (isBirthCertificateFailed(failedPayload)) {
    if (normalizeToken(status) === "certificate_failed" || progress?.phase === "certificate_failed") {
      return "Birth Certificate thresholds not met";
    }
    return "Birth Certificate v2 required";
  }
  if (normalizeToken(status) === "completed") {
    return "Birth Certificate v2 issued";
  }
  if (normalizeToken(status) === "certificate_failed") {
    return "Birth Certificate thresholds not met — review OOS metrics and retry";
  }
  const phase = normalizeToken(progress?.phase);
  if (phase === "oos_evaluation") {
    const sharpe = Number(progress?.oos_metrics?.oos_sharpe ?? 0);
    return `OOS Sharpe evaluation (${sharpe.toFixed(2)})…`;
  }
  const curriculum = String(progress?.curriculum_stage ?? "").trim();
  if (curriculum) {
    return `Curriculum ${curriculum.replace(/_/g, " ")}…`;
  }
  const days = Number(progress?.actual_real_days_loaded ?? 0);
  if (days > 0 && phase.includes("loading")) {
    return `Loading real history (${days} days)…`;
  }
  const active = milestones.find((m) => m.state === "active");
  if (active) return active.headline;
  return "Birth Phase v2 in progress…";
}

export type BirthUiPhase = "running" | "finale" | "error" | "idle" | "certificate_failed";

export function resolveBirthPhaseCopy(
  uiPhase: BirthUiPhase,
  milestones: BirthMilestone[],
): string {
  if (uiPhase === "finale") {
    return "Birth phase complete — continue training or enter the command deck.";
  }
  if (uiPhase === "error") {
    return "Birth interrupted — review diagnostics or retry.";
  }
  if (uiPhase === "certificate_failed") {
    return "Certificate thresholds not met — review OOS metrics below and retry birth.";
  }
  const active = milestones.find((m) => m.state === "active");
  if (active?.id === "refinement") {
    return "Policy refinement in progress — neural lattice stabilizing.";
  }
  if (active?.id === "strategies") {
    return "Strategy generation active — parallel simulation lanes open.";
  }
  if (active?.id === "fitness") {
    return "Fitness landscape loading — historical and synthetic lanes merging.";
  }
  return "Neural lattice forming — DNA, strategies, and policy in parallel.";
}

export function isBirthComplete(payload: BirthStatusPayload): boolean {
  if (payload.certificate_ok === false || payload.artifacts_ok === false) return false;
  const status = normalizeToken(payload.status);
  const stage = normalizeToken(payload.progress?.stage);
  const phase = normalizeToken(payload.progress?.phase);
  return (
    status === "completed" ||
    stage === "completed" ||
    stage === "practice_completed" ||
    phase === "certificate_issued"
  );
}

export function isBirthRunning(payload: BirthStatusPayload): boolean {
  const status = normalizeToken(payload.status);
  return status === "running" || status === "started" || status === "active";
}

export function isBirthInterrupted(payload: BirthStatusPayload): boolean {
  const status = normalizeToken(payload.status);
  const stage = normalizeToken(payload.progress?.stage);
  return status === "interrupted" || stage === "interrupted";
}

export function isBirthCertificateFailed(payload: BirthStatusPayload): boolean {
  if (isBirthRunning(payload)) {
    return false;
  }
  if (isBirthStageStalled(payload)) {
    return false;
  }
  const status = normalizeToken(payload.status);
  const stage = normalizeToken(payload.progress?.stage);
  const phase = normalizeToken(payload.progress?.phase);
  return (
    status === "certificate_failed" ||
    (stage === "failed" && phase === "certificate_failed") ||
    payload.certificate_ok === false
  );
}

export function isBirthFailed(payload: BirthStatusPayload): boolean {
  const status = normalizeToken(payload.status);
  return status === "error" || status === "certificate_failed";
}

export function isBirthStageStalled(payload: BirthStatusPayload): boolean {
  if (isBirthRunning(payload)) {
    return false;
  }
  const status = normalizeToken(payload.status);
  const stage = normalizeToken(payload.progress?.stage);
  const phase = normalizeToken(payload.progress?.phase);
  return status === "stage_stalled" || phase === "stage_stalled" || stage === "stage_stalled";
}

export function extractSimProgress(progress: BirthProgressPayload | undefined): {
  done: number;
  target: number;
  pct: number;
} {
  const hasCurriculumStage = Boolean(String(progress?.curriculum_stage ?? "").trim());
  const stageTrades = Number(progress?.stage_trades ?? 0);
  const cumulative = Number(
    progress?.trades_done ?? progress?.cumulative_trades ?? progress?.total_trades ?? 0,
  );
  const done = hasCurriculumStage ? stageTrades : cumulative;
  const stageTarget = Number(progress?.stage_target_trades ?? 0);
  const globalTarget = Number(progress?.target_trades ?? 0);
  const target =
    hasCurriculumStage && stageTarget > 0 ? stageTarget : globalTarget;
  const pct =
    target > 0
      ? Math.min(100, (done / target) * 100)
      : Number(progress?.progress_pct ?? 0);
  return { done, target, pct };
}

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
  adaptationEnabled: boolean;
  wallBehavior: string | null;
  escalationLevel: number | null;
  lastAdaptationReason: string | null;
  lastAdaptationChunk: number | null;
  lastAdaptationSummary: string | null;
}

const STALE_WORKING_SEC = 120;
const STALE_WARN_SEC = 600;

function parseProgressTimestamp(progress: BirthProgressPayload | undefined): number | null {
  const raw = progress?.timestamp;
  if (!raw) return null;
  const ms = Date.parse(raw);
  return Number.isFinite(ms) ? ms : null;
}

function resolveScorecardHealth(
  progress: BirthProgressPayload | undefined,
  heartbeatSec: number | null,
): { health: StageScorecardHealth; healthHint: string } {
  if (heartbeatSec == null) {
    return { health: "working", healthHint: "Waiting for progress update…" };
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
      if (escalationLevel != null) {
        parts.push(`L${escalationLevel}`);
      }
      lastAdaptationSummary = parts.join(" · ");
    }
  }

  return {
    volumeGateStatus,
    winrateTrendSlope,
    retriesThisStage,
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
    metricValue = Number(progress?.constitution_violations ?? 0);
    metricLabel = "Violations";
  }

  const ts = parseProgressTimestamp(progress);
  const heartbeatSec = ts != null ? Math.max(0, Math.round((nowMs - ts) / 1000)) : null;
  const { health, healthHint } = resolveScorecardHealth(progress, heartbeatSec);

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
  };
}

export function extractPpoProgress(progress: BirthProgressPayload | undefined): {
  steps: number;
  label: string;
} {
  const steps = Number(
    progress?.ppo_steps_cumulative ?? progress?.ppo_steps ?? 0,
  );
  const batch = Number(progress?.ppo_batch_count ?? 0);
  const label =
    batch > 0 ? `${steps.toLocaleString()} steps · batch ${batch}` : `${steps.toLocaleString()} steps`;
  return { steps, label };
}
