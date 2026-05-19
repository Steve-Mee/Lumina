import { toast } from "sonner";

import { deriveDecisionBrief } from "@/lib/decisionTheaterModel";
import { useCoreStore } from "@/store/coreStore";

function proposalHashSuffix(hash: string | null): string {
  if (!hash) {
    return "";
  }
  return ` · ${hash.slice(0, 12)}…`;
}

export function modifierKeyLabel(): string {
  if (typeof navigator !== "undefined" && /Mac|iPhone|iPad/i.test(navigator.platform)) {
    return "⌘";
  }
  return "Ctrl";
}

export function dispatchEvolve(): void {
  toast.info("Evolve cycle queued");
}

export function dispatchPause(): void {
  toast("Trading pause queued");
}

export function dispatchApproveLastMutation(): void {
  const state = useCoreStore.getState();
  const pendingHash = state.evolutionState.activeMutations[0]?.hash ?? null;

  if (!pendingHash) {
    toast.error("No pending mutation to approve");
    return;
  }

  const brief = deriveDecisionBrief(state);
  const hashSuffix = proposalHashSuffix(brief.proposalHash ?? pendingHash);

  if (state.operatorMode === "REAL") {
    toast.warning(`Approve queued (REAL mode — capital at risk)${hashSuffix}`);
    return;
  }

  toast.success(`Approve queued${hashSuffix}`);
}

export function dispatchRejectMutation(): void {
  const state = useCoreStore.getState();
  const brief = deriveDecisionBrief(state);
  const hashSuffix = proposalHashSuffix(brief.proposalHash);
  toast.error(`Reject queued${hashSuffix}`);
}

export function dispatchShadowDeploy(): void {
  const state = useCoreStore.getState();
  const brief = deriveDecisionBrief(state);
  const hashSuffix = proposalHashSuffix(brief.proposalHash);
  toast.info(`Shadow deploy queued${hashSuffix}`);
}
