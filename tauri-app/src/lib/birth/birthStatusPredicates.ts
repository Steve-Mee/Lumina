import type { BirthProgressPayload, BirthStatusPayload } from "@/lib/birthClient";

import {
  BIRTH_ACTIVE_PROGRESS_PHASES,
  BIRTH_ACTIVE_PROGRESS_STAGES,
} from "@/lib/birth/birthActiveProgress";
import { normalizeToken } from "@/lib/birth/birthModelUtils";

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

export function isBirthProgressActive(payload: BirthStatusPayload): boolean {
  if (isBirthInterrupted(payload)) {
    return false;
  }
  const stage = normalizeToken(payload.progress?.stage);
  const phase = normalizeToken(payload.progress?.phase);
  if (stage === "interrupted" || stage === "completed" || stage === "failed") {
    return false;
  }
  if (phase === "restart_required" || phase === "paused") {
    return false;
  }
  return BIRTH_ACTIVE_PROGRESS_STAGES.has(stage) || BIRTH_ACTIVE_PROGRESS_PHASES.has(phase);
}

/**
 * True when the Birth engine is actually executing.
 * On-disk progress alone (e.g. training_running after app restart) is NOT enough —
 * that would hide Resume/Wipe behind a fake "running" surface.
 */
export function isBirthEngineActive(payload: BirthStatusPayload): boolean {
  if (isBirthInterrupted(payload)) {
    return false;
  }
  if (isBirthRunning(payload)) {
    return true;
  }
  // Stale progress without a live runner must not look like an active engine.
  return payload.live === true && isBirthProgressActive(payload);
}

/** True when backend reports a live runner/thread (or top-level running status). */
export function isBirthEngineLive(payload: BirthStatusPayload | null | undefined): boolean {
  if (!payload) {
    return false;
  }
  if (isBirthInterrupted(payload)) {
    return false;
  }
  if (payload.live === true) {
    return true;
  }
  return isBirthRunning(payload);
}

export function isBirthInterrupted(payload: BirthStatusPayload): boolean {
  const status = normalizeToken(payload.status);
  const stage = normalizeToken(payload.progress?.stage);
  const phase = normalizeToken(payload.progress?.phase);
  return (
    status === "interrupted" ||
    status === "paused" ||
    stage === "interrupted" ||
    stage === "paused" ||
    phase === "paused" ||
    payload.progress?.user_initiated_stop === true
  );
}

/** Setup complete but birth never started — missing certificate is expected, not a failure. */
export function isBirthPendingGenesis(payload: BirthStatusPayload): boolean {
  const status = normalizeToken(payload.status);
  if (status !== "idle" && status !== "wiped") {
    return false;
  }
  const stage = normalizeToken(payload.progress?.stage);
  return stage === "not_started" || stage === "";
}

export function isBirthCertificateFailed(payload: BirthStatusPayload): boolean {
  if (isBirthEngineActive(payload)) {
    return false;
  }
  if (isBirthStageStalled(payload)) {
    return false;
  }
  if (isBirthPendingGenesis(payload)) {
    return false;
  }
  const status = normalizeToken(payload.status);
  const stage = normalizeToken(payload.progress?.stage);
  const phase = normalizeToken(payload.progress?.phase);
  if (status === "certificate_failed") {
    return true;
  }
  if (stage === "failed" && phase === "certificate_failed") {
    return true;
  }
  if (phase === "certificate_failed" || phase === "certificate_remediation") {
    return true;
  }
  if (payload.certificate_ok === false) {
    return status === "completed";
  }
  return false;
}

export function isBirthFailed(payload: BirthStatusPayload): boolean {
  const status = normalizeToken(payload.status);
  return status === "error" || status === "certificate_failed";
}

export function isBirthStageStalled(payload: BirthStatusPayload | null): boolean {
  if (!payload) {
    return false;
  }
  if (payload.live === true || isBirthEngineActive(payload)) {
    return false;
  }
  const stage = normalizeToken(payload.progress?.stage);
  const phase = normalizeToken(payload.progress?.phase);
  if (phase === "stage_stalled" || stage === "stage_stalled") {
    return true;
  }
  const status = normalizeToken(payload.status);
  return status === "stage_stalled";
}

/** Hide stale interrupted attention while birth is actively running again. */
export function shouldShowBirthAttentionBanner(
  progress: BirthProgressPayload | undefined,
  options?: { birthRunning?: boolean; birthStatus?: string },
): boolean {
  if (!progress?.needs_attention) {
    return false;
  }
  const reason = normalizeToken(progress.attention_reason_code);
  const running =
    options?.birthRunning === true || normalizeToken(options?.birthStatus) === "running";
  if (running && reason === "birth_interrupted") {
    return false;
  }
  return true;
}
