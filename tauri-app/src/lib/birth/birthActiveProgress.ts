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
