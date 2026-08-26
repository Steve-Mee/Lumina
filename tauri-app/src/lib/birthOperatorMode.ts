/**
 * Birth operator mode SSOT — one intent, one screen, no thrash.
 *
 * Priority (high → low):
 *   launching > training/finale > stall/cert overlays > decision > idle
 */

import type { BirthStatusPayload } from "@/lib/birthClient";
import {
  isBirthCertificateFailed,
  isBirthEngineActive,
  isBirthInterrupted,
  isBirthStageStalled,
} from "@/lib/birthPhaseModel";
import { detectBirthRecoveryKind, isBirthCheckpointResumable } from "@/lib/birthRecoveryModel";
import type { BirthUiPhase } from "@/lib/birth/birthClientTypes";

export type BirthOperatorMode =
  | "idle"
  | "decision"
  | "launching"
  | "training"
  | "finale"
  | "stall_overlay"
  | "certificate_overlay";

export type BirthActivationStep =
  | "idle"
  | "fabric"
  | "twin"
  | "history"
  | "engine"
  | "done";

export const BIRTH_ACTIVATION_STEPS: ReadonlyArray<{
  id: Exclude<BirthActivationStep, "idle" | "done">;
  label: string;
}> = [
  { id: "fabric", label: "Fabric link" },
  { id: "twin", label: "Twin readiness" },
  { id: "history", label: "Market history" },
  { id: "engine", label: "Engine start" },
];

export interface BirthOperatorModeInput {
  status: BirthStatusPayload | null;
  activating: boolean;
  runPinned: boolean;
  genesisPinned: boolean;
  uiPhase: BirthUiPhase;
  recoveryDismissed?: boolean;
}

/**
 * Resolve the single operator-visible mode. Callers must not branch on
 * competing surfaces when this returns launching/training/decision.
 */
export function resolveBirthOperatorMode(input: BirthOperatorModeInput): BirthOperatorMode {
  const {
    status,
    activating,
    runPinned,
    genesisPinned,
    uiPhase,
    recoveryDismissed = false,
  } = input;

  // Intent sticky: never flash decision/wipe while launch is in flight.
  if (activating) {
    return "launching";
  }

  if (uiPhase === "finale") {
    return "finale";
  }

  const engineActive =
    status != null && !genesisPinned && (status.live === true || isBirthEngineActive(status));

  // Cold-start after successful start — stay on training shell.
  if (runPinned && !genesisPinned) {
    if (uiPhase === "stage_stalled") {
      return "stall_overlay";
    }
    if (uiPhase === "certificate_failed") {
      return "certificate_overlay";
    }
    if (uiPhase === "error" && status != null && !isBirthInterrupted(status)) {
      // Hard fail after launch attempt → decision (not orphan).
      return "decision";
    }
    return "training";
  }

  if (engineActive || uiPhase === "running") {
    return "training";
  }

  if (!recoveryDismissed && !genesisPinned) {
    if (uiPhase === "certificate_failed" || (status != null && isBirthCertificateFailed(status))) {
      return "certificate_overlay";
    }
    if (uiPhase === "stage_stalled" || (status != null && isBirthStageStalled(status))) {
      return "stall_overlay";
    }
  }

  // Interrupted / paused / residual error / checkpoint waiting for operator choice.
  if (status != null && needsOperatorDecision(status, uiPhase)) {
    return "decision";
  }

  if (uiPhase === "error" && !genesisPinned) {
    return "decision";
  }

  return "idle";
}

/** True when the operator must choose Continue / Start clean (not silent training). */
export function needsOperatorDecision(
  status: BirthStatusPayload,
  uiPhase?: BirthUiPhase,
): boolean {
  if (isBirthEngineActive(status) || status.live === true) {
    return false;
  }
  if (isBirthInterrupted(status)) {
    return true;
  }
  if (isBirthCheckpointResumable(status)) {
    const top = String(status.status ?? "").toLowerCase();
    if (top !== "running" && top !== "started" && top !== "active") {
      return true;
    }
  }
  const kind = detectBirthRecoveryKind(status);
  if (
    kind === "session_interrupted" ||
    kind === "checkpoint_available" ||
    kind === "history_unavailable" ||
    kind === "simulation_stall"
  ) {
    return true;
  }
  if (uiPhase === "error") {
    return true;
  }
  return false;
}

/**
 * Hide Activate only when Continue / Start clean is mandatory.
 * Residual history / error without interrupt keeps Activate as Retry.
 */
export function shouldHideActivateForDecision(input: {
  sessionInterrupted: boolean;
  checkpointAvailable: boolean;
  activating?: boolean;
  sessionProbePending?: boolean;
  engineLive?: boolean;
}): boolean {
  if (input.activating || input.sessionProbePending || input.engineLive) {
    return false;
  }
  return input.sessionInterrupted || input.checkpointAvailable;
}

/** Banner “choose next step” only for stop/checkpoint — not residual history retry. */
export function shouldShowDecisionBanner(input: {
  sessionInterrupted: boolean;
  checkpointAvailable: boolean;
  resumePlateauRisk?: boolean;
}): boolean {
  return (
    input.sessionInterrupted || input.checkpointAvailable || Boolean(input.resumePlateauRisk)
  );
}

export function activationStepIndex(step: BirthActivationStep): number {
  switch (step) {
    case "fabric":
      return 0;
    case "twin":
      return 1;
    case "history":
      return 2;
    case "engine":
      return 3;
    case "done":
      return 4;
    default:
      return -1;
  }
}

export function activationStepLabel(step: BirthActivationStep): string {
  if (step === "idle") return "Ready";
  if (step === "done") return "Birth started";
  return BIRTH_ACTIVATION_STEPS.find((s) => s.id === step)?.label ?? step;
}
