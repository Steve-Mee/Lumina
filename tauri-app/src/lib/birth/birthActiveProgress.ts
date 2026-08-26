import type { BirthProgressPayload } from "@/lib/birthClient";

import { normalizeToken } from "@/lib/birth/birthModelUtils";

export const BIRTH_ACTIVE_PROGRESS_STAGES = new Set([
  "detected",
  "loading_data",
  "training_running",
  "pipeline_boot",
  "historical_loaded",
  "synthetic_top_up",
  "parallel_simulation",
  "ppo_training",
  "curriculum_research",
  "curriculum_learning",
  "data_expansion",
]);

export const BIRTH_ACTIVE_PROGRESS_PHASES = new Set([
  "detected",
  "loading_history",
  "enriching_news",
  "enriching_regimes",
  "train_holdout_split",
  "holdout_preflight",
  "holdout_preflight_expansion",
  "policy_init",
  "ticks_ready",
  "curriculum_stage",
  "curriculum_learning",
  "curriculum_research",
  "data_expansion",
  "parallel_simulation",
  "ppo_training",
  "ppo_polish",
  "oos_evaluation",
]);

export const BIRTH_TERMINAL_PROGRESS_STAGES = new Set([
  "completed",
  "failed",
  "interrupted",
  "stage_stalled",
  "practice_completed",
]);

/**
 * Data-prep / plant bootstrap — historical load, enrich, split, policy init.
 * Stage 1/5 scorecard must NOT appear here (only Birth preparation).
 */
export const BIRTH_DATA_PREP_PHASES = new Set([
  "detected",
  "loading_history",
  "loading_history_failed",
  "enriching_news",
  "enriching_regimes",
  "train_holdout_split",
  "holdout_preflight",
  "holdout_preflight_expansion",
  "policy_init",
  "ticks_ready",
  "pipeline_boot",
  "historical_loaded",
  "synthetic_top_up",
]);

/**
 * Curriculum is live — Stage N/5 scorecard + gates are honest.
 * Includes recovery / swarm / stall so the right column stays useful mid-stage.
 */
export const BIRTH_CURRICULUM_SCORECARD_PHASES = new Set([
  "curriculum_stage",
  "curriculum_learning",
  "curriculum_research",
  "parallel_simulation",
  "ppo_training",
  "ppo_polish",
  "oos_evaluation",
  "data_expansion",
  "policy_swarm",
  "plateau_evolution",
  "stall_remediation",
  "stage_stalled",
  "phoenix_cycle",
  "phoenix_resume",
  "phoenix_novelty",
  "swarm_reject_hard_stop",
  "swarm_no_lift_hard_stop",
  "certificate_failed",
  "certificate_remediation",
  "certificate_issued",
]);

/**
 * True only when Stage intelligence (Stage 1/5 …) should render.
 * Data load / enrich / ticks_ready → false even if curriculum_stage is pre-stamped.
 */
export function isBirthCurriculumScorecardActive(
  progress: BirthProgressPayload | undefined,
): boolean {
  if (!progress) return false;
  const phase = normalizeToken(progress.phase);
  const sub = normalizeToken(progress.sub_phase ?? "");
  // Prefer the more specific sub_phase when present.
  const active = sub || phase;

  // Hard ban: data plant / historical load — never Stage N/5 cards.
  if (
    (active && BIRTH_DATA_PREP_PHASES.has(active)) ||
    (phase && BIRTH_DATA_PREP_PHASES.has(phase))
  ) {
    return false;
  }

  if (active && BIRTH_CURRICULUM_SCORECARD_PHASES.has(active)) {
    return true;
  }
  if (phase && BIRTH_CURRICULUM_SCORECARD_PHASES.has(phase)) {
    return true;
  }

  // Fallback: stage string itself is a curriculum training stage.
  const stage = normalizeToken(progress.stage);
  if (
    stage === "ppo_training" ||
    stage === "curriculum_learning" ||
    stage === "curriculum_research" ||
    stage === "parallel_simulation" ||
    stage === "stage_stalled"
  ) {
    return true;
  }

  // Partial / test payloads without phase: only if curriculum already has trades.
  const curriculumStage = String(progress.curriculum_stage ?? "").trim();
  const stageTrades = Number(progress.stage_trades ?? 0);
  if (curriculumStage && stageTrades > 0 && !active) {
    return true;
  }
  return false;
}

export function isBirthProgressPayloadActive(
  progress: BirthProgressPayload | undefined,
): boolean {
  if (!progress) return false;
  const stage = normalizeToken(progress.stage);
  const phase = normalizeToken(progress.phase);
  if (BIRTH_TERMINAL_PROGRESS_STAGES.has(stage)) return false;
  if (phase === "restart_required" || phase === "paused" || phase === "certificate_failed") {
    return false;
  }
  return BIRTH_ACTIVE_PROGRESS_STAGES.has(stage) || BIRTH_ACTIVE_PROGRESS_PHASES.has(phase);
}
