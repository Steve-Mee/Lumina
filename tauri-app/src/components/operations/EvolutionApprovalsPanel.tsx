import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { GitBranch } from "lucide-react";

import { ApiKeySetupCallout } from "@/components/cockpit/ApiKeySetupCallout";
import { Button } from "@/components/ui/button";
import {
  approveProposal,
  fetchEvolutionProposals,
  rejectProposal,
  resolveDefaultChallengerName,
  type EvolutionProposal,
} from "@/lib/evolutionClient";
import { selectApiKeyConfigured, useApiKeyStore } from "@/store/apiKeyStore";
import { selectCurrentMode, useCoreStore } from "@/store/coreStore";
import { modeValueClass, pendingHighlightClass } from "@/lib/modePresentation";

export function EvolutionApprovalsPanel({ className }: { className?: string }) {
  const [proposals, setProposals] = useState<EvolutionProposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [realConfirm, setRealConfirm] = useState<Record<string, boolean>>({});
  const operatorMode = useCoreStore(selectCurrentMode);
  const apiKeyConfigured = useApiKeyStore(selectApiKeyConfigured);

  const refresh = useCallback(async () => {
    try {
      setProposals(await fetchEvolutionProposals());
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load proposals");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 30_000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const handleApprove = async (proposal: EvolutionProposal) => {
    const name = resolveDefaultChallengerName(proposal);
    if (!name) {
      toast.error("No challenger name found");
      return;
    }
    if (operatorMode === "REAL" && !realConfirm[proposal.hash]) {
      toast.warning("Confirm REAL human approval before approving");
      return;
    }
    try {
      await approveProposal({ hash: proposal.hash, challenger_name: name });
      toast.success("Proposal approved");
      void refresh();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Approve failed";
      toast.error(
        operatorMode === "REAL" && message.includes("signed")
          ? "REAL mode requires signed promotion payload from backend flow"
          : message,
      );
    }
  };

  const handleReject = async (proposal: EvolutionProposal) => {
    try {
      await rejectProposal({ hash: proposal.hash, reason: "Rejected from Evolution Approvals panel" });
      toast.success("Proposal rejected");
      void refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Reject failed");
    }
  };

  if (!apiKeyConfigured) {
    return <ApiKeySetupCallout className={className} />;
  }

  return (
    <div className={cn("space-y-3 overflow-y-auto p-1", className)}>
      <div className="flex items-center gap-2">
        <GitBranch className="size-4 text-violet-300/90" />
        <h3 className="font-mono text-[11px] tracking-[0.14em] text-violet-200/90 uppercase">
          Evolution Approvals
        </h3>
        <Button type="button" size="xs" variant="ghost" className="ml-auto" onClick={() => void refresh()}>
          Refresh
        </Button>
      </div>

      {loading && proposals.length === 0 ? (
        <p className="text-xs text-muted-foreground">Loading proposals…</p>
      ) : null}

      {proposals.length === 0 && !loading ? (
        <p className="text-xs text-muted-foreground">No open evolution proposals.</p>
      ) : null}

      {proposals.map((proposal) => (
        <article
          key={proposal.hash}
          className="lumina-surface-muted rounded-lg p-3"
        >
          <p className={cn("font-mono text-xs", modeValueClass(operatorMode))}>{proposal.hash.slice(0, 16)}…</p>
          <p className="mt-1 text-[11px] text-muted-foreground">
            {proposal.challengers?.length ?? 0} challenger(s)
            {proposal.timestamp ? ` · ${proposal.timestamp}` : ""}
          </p>
          <ul className="mt-2 space-y-1 text-[11px] text-muted-foreground">
            {(proposal.challengers ?? []).slice(0, 3).map((c) => (
              <li key={c.name ?? "unknown"}>• {c.name ?? "unnamed"}</li>
            ))}
          </ul>
          <div className="mt-3 flex flex-col gap-2">
            {operatorMode === "REAL" ? (
              <label className={cn("flex items-start gap-2 text-[10px]", pendingHighlightClass(operatorMode))}>
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={Boolean(realConfirm[proposal.hash])}
                  onChange={(e) =>
                    setRealConfirm((prev) => ({ ...prev, [proposal.hash]: e.target.checked }))
                  }
                />
                I confirm REAL promotion (signed payload may still be required by backend)
              </label>
            ) : null}
            <div className="flex gap-2">
              <Button
                type="button"
                size="xs"
                disabled={operatorMode === "REAL" && !realConfirm[proposal.hash]}
                onClick={() => void handleApprove(proposal)}
              >
                Approve
              </Button>
              <Button type="button" size="xs" variant="secondary" onClick={() => void handleReject(proposal)}>
                Reject
              </Button>
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}
