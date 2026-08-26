import type { BirthStatusPayload } from "@/lib/birthClient";
import {
  buildMilestones,
  isBirthComplete,
  isBirthCertificateFailed,
  isBirthEngineActive,
  isBirthFailed,
  isBirthInterrupted,
  isBirthResidualHistoryFailure,
  isBirthStageStalled,
  resolveBirthHeadline,
  type BirthMilestone,
} from "@/lib/birthPhaseModel";
import {
  resolveBirthSurface,
  type BirthSurface,
  type BirthUiPhase,
} from "@/store/birthSurfaceModel";

export interface BirthApplyStatusInput {
  uiPhase: BirthUiPhase;
  runPinned: boolean;
  genesisPinned: boolean;
  birthSurface: BirthSurface;
}

export interface BirthApplyStatusPatch {
  status: BirthStatusPayload;
  milestones: BirthMilestone[];
  headline: string;
  uiPhase: BirthUiPhase;
  birthSurface: BirthSurface;
  runPinned: boolean;
  pollError: null;
  sessionHydrated: true;
  sessionProbeState: "ready";
}

/** Pure applyStatus reducer — keeps birthStore façade thin. */
export function computeBirthApplyStatusPatch(
  payload: BirthStatusPayload,
  current: BirthApplyStatusInput,
): BirthApplyStatusPatch {
  const milestones = buildMilestones(payload.progress, payload.status);
  const headline = resolveBirthHeadline(
    milestones,
    payload.status,
    payload.progress,
    payload.certificate_ok,
  );
  let uiPhase: BirthUiPhase = current.uiPhase;
  let runPinned = current.runPinned;
  const genesisPinned = current.genesisPinned;

  const engineActive = payload.live === true || isBirthEngineActive(payload);

  if (current.uiPhase === "finale") {
    /* keep finale until parent transitions */
  } else if (runPinned && !genesisPinned) {
    // Raptor v14: keep training shell during cold-start; clear pin once live or terminal.
    if (engineActive) {
      uiPhase = "running";
      runPinned = false;
    } else if (isBirthComplete(payload)) {
      uiPhase = "finale";
      runPinned = false;
    } else if (isBirthStageStalled(payload)) {
      uiPhase = "stage_stalled";
      runPinned = false;
    } else if (isBirthCertificateFailed(payload)) {
      uiPhase = "certificate_failed";
      runPinned = false;
    } else if (isBirthFailed(payload) && !isBirthInterrupted(payload)) {
      uiPhase = "error";
      runPinned = false;
    } else {
      // interrupted / idle / starting → stay on running shell
      uiPhase = "running";
    }
  } else if (engineActive && !genesisPinned) {
    uiPhase = "running";
  } else if (isBirthCertificateFailed(payload)) {
    uiPhase = genesisPinned ? "idle" : "certificate_failed";
  } else if (isBirthComplete(payload)) {
    uiPhase = "finale";
  } else if (isBirthStageStalled(payload)) {
    uiPhase = genesisPinned ? "idle" : "stage_stalled";
  } else if (isBirthEngineActive(payload)) {
    uiPhase = genesisPinned ? "idle" : "running";
  } else if (isBirthFailed(payload)) {
    // Residual history failure: recovery surface (Retry / Fabric), never silent Genesis.
    if (genesisPinned) {
      uiPhase = "idle";
    } else if (isBirthResidualHistoryFailure(payload)) {
      uiPhase = "error";
    } else {
      uiPhase = "error";
    }
  } else if (isBirthInterrupted(payload)) {
    uiPhase = "idle";
  } else if (genesisPinned) {
    uiPhase = "idle";
  }

  const birthSurface = resolveBirthSurface(
    uiPhase,
    current.birthSurface,
    payload,
    genesisPinned,
    runPinned,
  );

  return {
    status: payload,
    milestones,
    headline,
    uiPhase,
    birthSurface,
    runPinned,
    pollError: null,
    sessionHydrated: true,
    sessionProbeState: "ready",
  };
}
