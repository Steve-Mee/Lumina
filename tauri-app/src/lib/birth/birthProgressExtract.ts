import type { BirthProgressPayload, BirthStatusPayload } from "@/lib/birthClient";

export function formatGenesisCheckpointSummary(
  status: BirthStatusPayload | null | undefined,
): string | null {
  if (!status || status.checkpoint_resumable !== true) {
    return null;
  }
  const progress = status.progress;
  const ppo = Number(status.checkpoint_ppo_steps ?? progress?.ppo_steps ?? 0);
  const stage = String(status.curriculum_stage ?? progress?.curriculum_stage ?? "").trim();
  const stageTrades = Number(
    status.checkpoint_stage_trades ??
      progress?.stage_trades ??
      status.checkpoint_cumulative_trades ??
      0,
  );
  const stageTarget = Number(progress?.stage_target_trades ?? progress?.target_trades ?? 0);
  if (ppo <= 0 && stageTrades <= 0) {
    return null;
  }
  const parts: string[] = [];
  if (stage && stage !== "interrupted" && stage !== "not_started") {
    parts.push(stage.replace(/_/g, " "));
  }
  if (ppo > 0) {
    parts.push(`${ppo.toLocaleString()} PPO steps`);
  }
  if (stageTrades > 0 && stageTarget > 0) {
    parts.push(`${stageTrades}/${stageTarget} stage trades`);
  }
  return parts.length > 0 ? parts.join(" · ") : null;
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
