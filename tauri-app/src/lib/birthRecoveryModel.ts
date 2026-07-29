import type { BirthProgressPayload, BirthStatusPayload } from "@/lib/birthClient";
import { isBirthEngineActive } from "@/lib/birthPhaseModel";

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

export function isBirthCheckpointResumable(status: BirthStatusPayload | null | undefined): boolean {
  return status?.checkpoint_resumable === true;
}

/** @deprecated Use isBirthCheckpointResumable(status) — progress trade counts are not a resume signal. */
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
  if (
    topStatus === "interrupted" ||
    topStatus === "paused" ||
    status.progress?.user_initiated_stop === true
  ) {
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
  // Checkpoint on disk + no live engine → offer Resume/Wipe (stage name may still be training_*).
  if (
    isBirthCheckpointResumable(status) &&
    status.live !== true &&
    topStatus !== "running" &&
    topStatus !== "started" &&
    topStatus !== "active"
  ) {
    return "checkpoint_available";
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
  if (isBirthEngineActive(status)) {
    return false;
  }
  if (status.progress?.user_initiated_stop === true) {
    return false;
  }
  const topStatus = norm(status.status);
  if (topStatus === "running" || topStatus === "started" || topStatus === "active") {
    return false;
  }
  // Interrupted / checkpoint after restart: land on Genesis Recovery so the operator
  // can choose Resume or Wipe. Do not silently continue_training.
  if (
    topStatus === "interrupted" ||
    topStatus === "paused" ||
    appSurfaceReason === "birth_interrupted"
  ) {
    return false;
  }
  const recovery = detectBirthRecoveryKind(status);
  if (recovery === "session_interrupted" || recovery === "checkpoint_available") {
    return false;
  }
  if (recovery === "stage_stalled" && status.progress?.retryable !== false) {
    return true;
  }
  if (status.progress?.autonomous_recovery_pending === true) {
    return true;
  }
  const terminal = norm(status.progress?.terminal_stall_reason);
  if (terminal === "phoenix_cycle" && status.progress?.retryable !== false) {
    return true;
  }
  if (
    (terminal === "plateau_evolution_exhausted" || terminal === "stall_remediation_exhausted") &&
    status.progress?.retryable !== false &&
    status.progress?.needs_attention !== true
  ) {
    return true;
  }
  if (recovery === "simulation_stall") {
    return true;
  }
  if (appSurfaceReason === "birth_error" && isBirthCheckpointResumable(status)) {
    return false;
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

export type BirthWipeVerifyInput = {
  apiStatus: string;
  apiCheckpointResumable?: boolean;
  polledStatus: BirthStatusPayload | null | undefined;
};

export type BirthWipeVerifyResult = { ok: true } | { ok: false; error: string };

const WIPE_STATUS_NOT_CLEAN_ERROR =
  "Wipe voltooid maar status is niet schoon — herstart de backend en probeer opnieuw.";
const WIPE_CHECKPOINT_STILL_RESUMABLE_ERROR =
  "Wipe voltooid maar checkpoint is nog resumeerbaar — herstart de backend en probeer opnieuw.";
const WIPE_STATUS_UNVERIFIED_ERROR =
  "Wipe voltooid maar status kon niet worden geverifieerd — herstart de backend en probeer opnieuw.";

/** Verify wipe succeeded using API response and a fresh status poll (before store reset). */
export function verifyBirthWipeSucceeded(input: BirthWipeVerifyInput): BirthWipeVerifyResult {
  const apiStatus = norm(input.apiStatus);
  const apiClean = apiStatus === "wiped" && input.apiCheckpointResumable !== true;
  const polled = input.polledStatus;

  if (!polled) {
    return apiClean ? { ok: true } : { ok: false, error: WIPE_STATUS_UNVERIFIED_ERROR };
  }

  if (polled.checkpoint_resumable === true || input.apiCheckpointResumable === true) {
    return { ok: false, error: WIPE_CHECKPOINT_STILL_RESUMABLE_ERROR };
  }

  const topStatus = norm(polled.status);
  if (topStatus === "idle" || topStatus === "wiped") {
    return { ok: true };
  }

  if (
    apiClean &&
    (topStatus === "running" ||
      topStatus === "interrupted" ||
      topStatus === "stopping" ||
      topStatus === "started")
  ) {
    return { ok: true };
  }

  return { ok: false, error: WIPE_STATUS_NOT_CLEAN_ERROR };
}
