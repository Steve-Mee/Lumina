import type { BirthStatusPayload } from "@/lib/birthClient";
import {
  isBirthCertificateFailed,
  isBirthEngineActive,
  isBirthInterrupted,
  isBirthStageStalled,
} from "@/lib/birthPhaseModel";

import type { BirthUiPhase } from "@/lib/birth/birthClientTypes";
export type { BirthUiPhase };

export type BirthSurface = "genesis" | "running" | "recovery";

export function resolveBirthSurface(
  uiPhase: BirthUiPhase,
  current: BirthSurface,
  payload: BirthStatusPayload,
  genesisPinned: boolean,
): BirthSurface {
  if (genesisPinned) {
    return "genesis";
  }
  if (payload.live === true || isBirthEngineActive(payload)) {
    return "running";
  }
  if (uiPhase === "certificate_failed" || uiPhase === "stage_stalled" || uiPhase === "error") {
    return "recovery";
  }
  if (uiPhase === "finale") {
    return "running";
  }
  if (genesisPinned || (uiPhase === "idle" && isBirthInterrupted(payload))) {
    return "genesis";
  }
  if (uiPhase === "running" || isBirthEngineActive(payload)) {
    return "running";
  }
  if (uiPhase === "idle") {
    return "genesis";
  }
  if (current === "recovery" && uiPhase === "idle") {
    return "genesis";
  }
  return current;
}

export function recoveryFailureUiPhase(status: BirthStatusPayload | null): BirthUiPhase {
  if (status == null) {
    return "error";
  }
  if (isBirthStageStalled(status)) {
    return "stage_stalled";
  }
  if (isBirthCertificateFailed(status)) {
    return "certificate_failed";
  }
  return "error";
}