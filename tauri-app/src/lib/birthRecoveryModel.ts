import type { BirthProgressPayload, BirthStatusPayload } from "@/lib/birthClient";

export type BirthRecoveryKind =
  | "history_unavailable"
  | "checkpoint_available"
  | "simulation_stall"
  | null;

function norm(value: unknown): string {
  return String(value ?? "").trim().toLowerCase();
}

export function detectBirthRecoveryKind(
  status: BirthStatusPayload | null,
): BirthRecoveryKind {
  if (!status?.progress) {
    return null;
  }
  const stage = norm(status.progress.stage);
  const phase = norm(status.progress.phase);

  if (stage === "history_unavailable" || phase === "loading_history_failed") {
    return "history_unavailable";
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
