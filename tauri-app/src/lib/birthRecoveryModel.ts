import type { BirthProgressPayload, BirthStatusPayload } from "@/lib/birthClient";

export type BirthRecoveryKind =
  | "history_unavailable"
  | "checkpoint_available"
  | "simulation_stall"
  | "session_interrupted"
  | "certificate_failed"
  | "stage_stalled"
  | null;

function norm(value: unknown): string {
  return String(value ?? "").trim().toLowerCase();
}

export function hasBirthCheckpointProgress(
  progress: BirthProgressPayload | undefined,
): boolean {
  if (!progress) {
    return false;
  }
  return (
    checkpointTradeCount(progress) > 0 ||
    Number(progress.ppo_steps ?? progress.ppo_steps_cumulative ?? 0) > 0 ||
    Number(progress.trades_done ?? progress.cumulative_trades ?? 0) > 0
  );
}

export function detectBirthRecoveryKind(
  status: BirthStatusPayload | null,
): BirthRecoveryKind {
  if (!status) {
    return null;
  }

  const topStatus = norm(status.status);
  if (topStatus === "certificate_failed") {
    return "certificate_failed";
  }
  if (topStatus === "stage_stalled") {
    return "stage_stalled";
  }
  if (topStatus === "interrupted") {
    return "session_interrupted";
  }

  if (!status.progress) {
    return null;
  }
  const stage = norm(status.progress.stage);
  const phase = norm(status.progress.phase);

  if (stage === "history_unavailable" || phase === "loading_history_failed") {
    return "history_unavailable";
  }
  if (phase === "certificate_failed" || phase === "certificate_remediation") {
    return "certificate_failed";
  }
  if (phase === "stage_stalled" || stage === "stage_stalled") {
    return "stage_stalled";
  }
  if (stage === "checkpoint_available") {
    return "checkpoint_available";
  }
  if (
    phase === "simulation_stall" ||
    phase === "simulation_stall_retry" ||
    phase === "simulation_stall_grace" ||
    (stage === "failed" && phase === "simulation_stall")
  ) {
    return "simulation_stall";
  }
  return null;
}

/** Whether cold-start bootstrap should call continue_training without wizard activation. */
export function shouldAutoResumeBirth(
  status: BirthStatusPayload | null,
  appSurfaceReason?: string,
): boolean {
  if (!status) {
    return false;
  }
  const topStatus = norm(status.status);
  if (topStatus === "running" || topStatus === "started" || topStatus === "active") {
    return false;
  }
  if (topStatus === "interrupted" || appSurfaceReason === "birth_interrupted") {
    return true;
  }
  const recovery = detectBirthRecoveryKind(status);
  if (recovery === "checkpoint_available" || recovery === "simulation_stall") {
    return true;
  }
  if (appSurfaceReason === "birth_error" && hasBirthCheckpointProgress(status.progress)) {
    return true;
  }
  return false;
}

export function birthProgressDiagnostics(progress: BirthProgressPayload | undefined): string | null {
  if (!progress) {
    return null;
  }
  const diag = (progress as Record<string, unknown>).stall_diagnostics;
  if (typeof diag === "string" && diag.trim()) {
    return diag;
  }
  if (diag && typeof diag === "object") {
    return JSON.stringify(diag, null, 2);
  }
  return null;
}

export function checkpointTradeCount(progress: BirthProgressPayload | undefined): number {
  if (!progress) {
    return 0;
  }
  const raw = progress as Record<string, unknown>;
  return Number(raw.checkpoint_trades ?? progress.cumulative_trades ?? progress.trades_done ?? 0);
}
