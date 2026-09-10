/** Operator-truth helpers: never paint Birth as “complete” unless the engine passed. */

import type { BirthProgressPayload } from "@/lib/birthClient";

export interface BirthProgressTruth {
  pctIsNotComplete: boolean;
  stagePassNow: boolean;
  stageIndex: number;
  stageCount: number;
  blocker: string | null;
  /** Discrete position, never a fake completion percent. */
  curriculumLabel: string;
}

function finitePositive(raw: unknown): number | null {
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : null;
}

function manifestRecord(
  progress: BirthProgressPayload | undefined,
): Record<string, unknown> | null {
  const raw = progress?.data_manifest;
  return raw && typeof raw === "object" ? (raw as Record<string, unknown>) : null;
}

export function resolveManifestCalendarDays(
  progress: BirthProgressPayload | undefined,
): number | null {
  if (!progress) return null;
  const manifest = manifestRecord(progress);
  return (
    finitePositive(progress.data_manifest_calendar_days) ??
    finitePositive(manifest?.actual_calendar_days) ??
    finitePositive(progress.actual_real_days_loaded) ??
    finitePositive(manifest?.days_loaded) ??
    finitePositive(progress.data_days_loaded)
  );
}

export function resolveStageWindowDays(
  progress: BirthProgressPayload | undefined,
): number | null {
  if (!progress) return null;
  return (
    finitePositive(progress.stage_window_calendar_days) ??
    finitePositive(progress.foundation_unique_calendar_days)
  );
}

export function extractBirthProgressTruth(
  progress: BirthProgressPayload | undefined,
): BirthProgressTruth {
  const raw = progress?.progress_truth;
  const truth =
    raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  const stageCount = Math.max(
    1,
    Number(truth.stage_count ?? progress?.curriculum_total ?? 5) || 5,
  );
  const stageIndex = Math.max(
    0,
    Number(truth.stage_index ?? progress?.curriculum_index ?? 0) || 0,
  );
  const stagePassNow = Boolean(truth.stage_pass_now ?? progress?.stage_pass_now);
  const blocker =
    String(truth.blocker ?? progress?.stage_blocker_metric ?? "").trim() || null;
  const pctIsNotComplete =
    truth.pct_is_not_complete == null ? !stagePassNow : Boolean(truth.pct_is_not_complete);
  const pos =
    stageIndex > 0
      ? `Stage ${Math.min(stageIndex, stageCount)}/${stageCount}`
      : "Birth";
  const curriculumLabel = stagePassNow
    ? `${pos} · passed`
    : blocker
      ? `${pos} · not passed · ${blocker.replace(/_/g, " ")}`
      : `${pos} · not passed`;
  return {
    pctIsNotComplete,
    stagePassNow,
    stageIndex,
    stageCount,
    blocker,
    curriculumLabel,
  };
}

/** Fill = stages passed / 5. Never the theater 79.5% index. */
export function curriculumStagesPassedFill(
  progress: BirthProgressPayload | undefined,
): number {
  const passed = Array.isArray(progress?.stages_passed)
    ? progress.stages_passed.filter(Boolean).length
    : 0;
  const total = Math.max(1, Number(progress?.curriculum_total ?? 5) || 5);
  const truth = extractBirthProgressTruth(progress);
  if (truth.stagePassNow && passed >= total) return 100;
  return Math.min(100, Math.max(0, (passed / total) * 100));
}

/** Deck/HUD copy. Never “80% complete” while a stage gate is open. */
export function formatBirthProgressHeadline(
  progress: BirthProgressPayload | undefined,
  fallbackPct?: number,
): string {
  const truth = extractBirthProgressTruth(progress);
  if (progress?.curriculum_stage || progress?.curriculum_index) {
    return truth.curriculumLabel;
  }
  const pct = Number(fallbackPct ?? progress?.progress_pct ?? 0);
  if (!Number.isFinite(pct) || pct <= 0) return "Birth in progress";
  if (truth.pctIsNotComplete || !truth.stagePassNow) {
    return `${pct.toFixed(0)}% of curriculum index (not complete)`;
  }
  return `${pct.toFixed(0)}% complete`;
}

export function extractPpoLungs(progress: BirthProgressPayload | undefined): {
  nEnvs: number;
  device: string | null;
  batchPct: number | null;
  batchSteps: number;
  batchTotal: number;
} {
  const nEnvs = Math.max(1, Number(progress?.ppo_n_envs ?? 1) || 1);
  const device = String(progress?.ppo_device ?? "").trim() || null;
  const batchPctRaw = Number(progress?.ppo_batch_progress_pct);
  const batchPct = Number.isFinite(batchPctRaw) ? Math.min(100, Math.max(0, batchPctRaw)) : null;
  return {
    nEnvs,
    device,
    batchPct,
    batchSteps: Math.max(0, Number(progress?.ppo_batch_steps ?? 0) || 0),
    batchTotal: Math.max(0, Number(progress?.ppo_batch_total ?? 0) || 0),
  };
}

export function extractThroughput(progress: BirthProgressPayload | undefined): {
  innerTpm: number | null;
  outerTpm: number | null;
} {
  const inner = Number(progress?.wall_clock_trades_per_min);
  const outer = Number(progress?.wall_clock_trades_per_min_outer);
  return {
    innerTpm: Number.isFinite(inner) && inner > 0 ? inner : null,
    outerTpm: Number.isFinite(outer) && outer > 0 ? outer : null,
  };
}

export function occupancyEnvelopeDominated(
  progress: BirthProgressPayload | undefined,
): boolean {
  const reason = String(progress?.pass_reason ?? "").toLowerCase();
  return reason.includes("occupancy_envelope_dominated");
}

export function formatLungsThroughputHint(
  progress: BirthProgressPayload | undefined,
  manifestDays: number | null,
): string | undefined {
  const tpm = extractThroughput(progress);
  const lungs = extractPpoLungs(progress);
  const windowDays = resolveStageWindowDays(progress);
  const parts: string[] = [];
  if (tpm.outerTpm != null) parts.push(`session ${tpm.outerTpm.toLocaleString()}/min`);
  if (tpm.innerTpm != null) parts.push(`rollout ${tpm.innerTpm.toLocaleString()}/min`);
  if (windowDays != null && windowDays !== manifestDays) {
    parts.push(`stage window ${windowDays}d`);
  }
  if (lungs.nEnvs > 1 || lungs.device) {
    parts.push(`lungs ${lungs.nEnvs}×${lungs.device ?? "cpu"}`);
  }
  return parts.length > 0 ? parts.join(" · ") : undefined;
}
