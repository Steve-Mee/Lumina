import { toast } from "sonner";

import { assertCommandDeckAllowed } from "@/lib/commandDeckGuard";
import { deriveDecisionBrief } from "@/lib/decisionTheaterModel";
import {
  approveProposal,
  fetchEvolutionProposals,
  rejectProposal,
  resolveDefaultChallengerName,
} from "@/lib/evolutionClient";
import { flattenPositions } from "@/lib/runtimeClient";
import { useCoreStore } from "@/store/coreStore";
import { useDeckPanelStore } from "@/store/deckPanelStore";
function proposalHashSuffix(hash: string | null): string {
  if (!hash) return "";
  return ` · ${hash.slice(0, 12)}…`;
}

export function modifierKeyLabel(): string {
  if (typeof navigator !== "undefined" && /Mac|iPhone|iPad/i.test(navigator.platform)) {
    return "⌘";
  }
  return "Ctrl";
}

export function dispatchPause(): void {
  if (!assertCommandDeckAllowed()) {
    return;
  }
  void flattenPositions()
    .then((result) => {
      const count = Number((result as { flattened_count?: number }).flattened_count ?? 0);
      toast.success(`Trading paused — flattened ${count} position(s)`);
    })
    .catch((err) => {
      toast.error(err instanceof Error ? err.message : "Flatten failed");
    });
}

export function dispatchEvolve(): void {
  if (!assertCommandDeckAllowed()) {
    return;
  }
  useDeckPanelStore.getState().setActiveRightTab("evolutionApprovals");
  void fetchEvolutionProposals()
    .then((rows) => {
      toast.info(
        rows.length
          ? `${rows.length} open proposal(s) — review in Evolution Approvals`
          : "No open proposals — evolution cycle runs on schedule",
      );
    })
    .catch((err) => {
      toast.error(err instanceof Error ? err.message : "Failed to load proposals");
    });
}
export async function dispatchApproveLastMutation(): Promise<void> {
  if (!assertCommandDeckAllowed()) {
    return;
  }
  const state = useCoreStore.getState();
  const pendingHash = state.evolutionState.activeMutations[0]?.hash ?? null;

  if (!pendingHash) {
    toast.error("No pending mutation to approve");
    return;
  }

  try {
    const proposals = await fetchEvolutionProposals();
    const proposal = proposals.find((row) => row.hash === pendingHash);
    const challengerName = resolveDefaultChallengerName(proposal);
    if (!challengerName) {
      toast.error("Could not resolve challenger name for proposal");
      return;
    }

    if (state.operatorMode === "REAL") {
      toast.warning(
        `REAL approve requires signed promotion payload — use backend REAL flow${proposalHashSuffix(pendingHash)}`,
      );
      return;
    }

    await approveProposal({ hash: pendingHash, challenger_name: challengerName });
    toast.success(`Mutation approved${proposalHashSuffix(pendingHash)}`);
  } catch (err) {
    toast.error(err instanceof Error ? err.message : "Approve failed");
  }
}

export async function dispatchRejectMutation(): Promise<void> {
  if (!assertCommandDeckAllowed()) {
    return;
  }
  const state = useCoreStore.getState();
  const brief = deriveDecisionBrief(state);
  const hash = brief.proposalHash ?? state.evolutionState.activeMutations[0]?.hash ?? null;
  if (!hash) {
    toast.error("No pending mutation to reject");
    return;
  }

  try {
    await rejectProposal({ hash, reason: "Rejected from Decision Theater" });
    toast.success(`Mutation rejected${proposalHashSuffix(hash)}`);
  } catch (err) {
    toast.error(err instanceof Error ? err.message : "Reject failed");
  }
}

export function dispatchShadowDeploy(): void {
  if (!assertCommandDeckAllowed()) {
    return;
  }
  useDeckPanelStore.getState().setActiveRightTab("monitor");
  toast.info("Shadow deployments tracked in System Monitor");
}