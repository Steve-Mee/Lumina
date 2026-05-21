import { useCallback, useEffect, useState } from "react";
import { Users } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { fetchGlobalWisdom, fetchLeaderboard, fetchReconciliationStatus, type LeaderboardRow, type ReconciliationStatus } from "@/lib/opsClient";
import { modeTextTier2Class, modeTitleClass, modeValueClass, utilityListItemClass } from "@/lib/modePresentation";
import { selectCurrentMode, useCoreStore } from "@/store/coreStore";
import { cn } from "@/lib/utils";

function formatPnl(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}`;
}

export function CommunityPanel({ className }: { className?: string }) {
  const operatorMode = useCoreStore(selectCurrentMode);
  const [leaderboard, setLeaderboard] = useState<LeaderboardRow[]>([]);
  const [wisdom, setWisdom] = useState<Record<string, unknown>>({});
  const [reconciliation, setReconciliation] = useState<ReconciliationStatus | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [lb, gw, recon] = await Promise.all([
        fetchLeaderboard(),
        fetchGlobalWisdom(),
        fetchReconciliationStatus(),
      ]);
      setLeaderboard(lb);
      setWisdom(gw);
      setReconciliation(recon);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Community data failed");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const wisdomEntries =
    wisdom && typeof wisdom === "object"
      ? Object.entries(wisdom).filter(([key]) => key !== "last_updated")
      : [];

  return (
    <div className={cn("space-y-4 overflow-y-auto p-1", className)}>
      <div className="flex items-center gap-2">
        <Users className={cn("size-4", modeTitleClass(operatorMode))} />
        <h3
          className={cn(
            "font-mono text-[11px] tracking-[0.14em] uppercase",
            modeTextTier2Class(operatorMode),
          )}
        >
          Community
        </h3>
        <Button type="button" size="xs" variant="command-ghost" className="ml-auto" onClick={() => void refresh()}>
          Refresh
        </Button>
      </div>

      <section className="lumina-surface-muted rounded-lg p-3">
        <p className="mb-2 font-mono text-[10px] uppercase text-muted-foreground">Reconciliation</p>
        {reconciliation ? (
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <span className="text-muted-foreground">State: </span>
              <span className="font-mono">{reconciliation.connection_state ?? reconciliation.status ?? "—"}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Pending: </span>
              <span className="font-mono">{reconciliation.pending_count ?? 0}</span>
            </div>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">Reconciliation status unavailable.</p>
        )}
      </section>

      <section className="lumina-surface-muted rounded-lg p-3">
        <p className="mb-2 font-mono text-[10px] uppercase text-muted-foreground">Trader League</p>
        {leaderboard.length === 0 ? (
          <p className="text-xs text-muted-foreground">No leaderboard entries.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[320px] text-left text-xs">
              <thead>
                <tr className="border-b border-white/10 font-mono text-[10px] uppercase text-muted-foreground">
                  <th className="py-1 pr-2">#</th>
                  <th className="py-1 pr-2">Trader</th>
                  <th className="py-1 pr-2">Mode</th>
                  <th className="py-1 pr-2 text-right">Trades</th>
                  <th className="py-1 pr-2 text-right">Win%</th>
                  <th className="py-1 text-right">PnL</th>
                </tr>
              </thead>
              <tbody>
                {leaderboard.slice(0, 10).map((row, idx) => (
                  <tr key={`${row.participant}-${idx}`} className="border-b border-white/5">
                    <td className="py-1.5 pr-2 font-mono text-muted-foreground">{idx + 1}</td>
                    <td className="py-1.5 pr-2 font-medium text-foreground">{row.participant}</td>
                    <td className="py-1.5 pr-2 uppercase text-muted-foreground">{row.mode}</td>
                    <td className="py-1.5 pr-2 text-right font-mono">{row.trades}</td>
                    <td className="py-1.5 pr-2 text-right font-mono">
                      {row.win_rate != null ? `${row.win_rate.toFixed(1)}%` : "—"}
                    </td>
                    <td
                      className={cn(
                        "py-1.5 text-right font-mono",
                        row.total_pnl >= 0 ? "text-emerald-300" : "text-red-300",
                      )}
                    >
                      {formatPnl(row.total_pnl)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="lumina-surface-muted rounded-lg p-3">
        <p className="mb-2 font-mono text-[10px] uppercase text-muted-foreground">Global Wisdom</p>
        {wisdomEntries.length === 0 ? (
          <p className="text-xs text-muted-foreground">No wisdom entries yet.</p>
        ) : (
          <ul className="space-y-2">
            {wisdomEntries.slice(0, 8).map(([key, value]) => (
              <li key={key} className={utilityListItemClass(operatorMode)}>
                <p className={cn("font-mono text-[10px] uppercase", modeValueClass(operatorMode))}>{key}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {typeof value === "string" ? value : JSON.stringify(value)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
