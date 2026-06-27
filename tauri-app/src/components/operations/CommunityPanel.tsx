import { useCallback, useEffect, useState } from "react";
import { Users } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  fetchGlobalWisdom,
  fetchLeaderboard,
  fetchReconciliationStatus,
  uploadCommunityBible,
  uploadCommunityReflection,
  type LeaderboardRow,
  type ReconciliationStatus,
} from "@/lib/opsClient";
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
  const [bibleTraderName, setBibleTraderName] = useState("");
  const [bibleRuleJson, setBibleRuleJson] = useState('{"rule": "volume_first"}');
  const [bibleSharpe, setBibleSharpe] = useState("1.0");
  const [reflectionTrader, setReflectionTrader] = useState("");
  const [reflectionText, setReflectionText] = useState("");
  const [reflectionLesson, setReflectionLesson] = useState("");
  const [uploadBusy, setUploadBusy] = useState(false);

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

  const handleBibleUpload = useCallback(async () => {
    const trader = bibleTraderName.trim();
    if (!trader) {
      toast.error("Trader name is required");
      return;
    }
    let evolvableLayer: Record<string, unknown>;
    try {
      evolvableLayer = JSON.parse(bibleRuleJson) as Record<string, unknown>;
    } catch {
      toast.error("Evolvable layer must be valid JSON");
      return;
    }
    const sharpe = Number.parseFloat(bibleSharpe);
    setUploadBusy(true);
    try {
      await uploadCommunityBible({
        trader_name: trader,
        evolvable_layer: evolvableLayer,
        backtest_results: { sharpe: Number.isFinite(sharpe) ? sharpe : 0 },
      });
      toast.success("Community bible uploaded");
      await refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Bible upload failed");
    } finally {
      setUploadBusy(false);
    }
  }, [bibleRuleJson, bibleSharpe, bibleTraderName, refresh]);

  const handleReflectionUpload = useCallback(async () => {
    const trader = reflectionTrader.trim();
    if (!trader || !reflectionText.trim() || !reflectionLesson.trim()) {
      toast.error("Trader, reflection, and key lesson are required");
      return;
    }
    setUploadBusy(true);
    try {
      await uploadCommunityReflection({
        trader_name: trader,
        reflection: reflectionText.trim(),
        key_lesson: reflectionLesson.trim(),
      });
      toast.success("Reflection uploaded");
      setReflectionText("");
      await refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Reflection upload failed");
    } finally {
      setUploadBusy(false);
    }
  }, [reflectionLesson, reflectionText, reflectionTrader, refresh]);

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

      <section className="lumina-surface-muted space-y-3 rounded-lg p-3">
        <p className="font-mono text-[10px] uppercase text-muted-foreground">Upload Community Bible</p>
        <div className="space-y-2">
          <label htmlFor="bible-trader" className="text-xs text-muted-foreground">
            Trader name
          </label>
          <input
            id="bible-trader"
            value={bibleTraderName}
            onChange={(e) => setBibleTraderName(e.target.value)}
            placeholder="LUMINA_Steve"
            className="h-8 w-full rounded border border-white/10 bg-black/20 px-2 font-mono text-xs"
          />
        </div>
        <div className="space-y-2">
          <label htmlFor="bible-rule" className="text-xs text-muted-foreground">
            Evolvable layer (JSON)
          </label>
          <textarea
            id="bible-rule"
            value={bibleRuleJson}
            onChange={(e) => setBibleRuleJson(e.target.value)}
            rows={3}
            className="w-full rounded border border-white/10 bg-black/20 p-2 font-mono text-xs"
          />
        </div>
        <div className="space-y-2">
          <label htmlFor="bible-sharpe" className="text-xs text-muted-foreground">
            Backtest Sharpe
          </label>
          <input
            id="bible-sharpe"
            value={bibleSharpe}
            onChange={(e) => setBibleSharpe(e.target.value)}
            className="h-8 w-full rounded border border-white/10 bg-black/20 px-2 font-mono text-xs"
          />
        </div>
        <Button type="button" size="xs" variant="command-primary" disabled={uploadBusy} onClick={() => void handleBibleUpload()}>
          Upload Bible
        </Button>
      </section>

      <section className="lumina-surface-muted space-y-3 rounded-lg p-3">
        <p className="font-mono text-[10px] uppercase text-muted-foreground">Upload Reflection</p>
        <div className="space-y-2">
          <label htmlFor="reflection-trader" className="text-xs text-muted-foreground">
            Trader name
          </label>
          <input
            id="reflection-trader"
            value={reflectionTrader}
            onChange={(e) => setReflectionTrader(e.target.value)}
            className="h-8 w-full rounded border border-white/10 bg-black/20 px-2 font-mono text-xs"
          />
        </div>
        <div className="space-y-2">
          <label htmlFor="reflection-text" className="text-xs text-muted-foreground">
            Reflection
          </label>
          <textarea
            id="reflection-text"
            value={reflectionText}
            onChange={(e) => setReflectionText(e.target.value)}
            rows={2}
            className="w-full rounded border border-white/10 bg-black/20 p-2 text-xs"
          />
        </div>
        <div className="space-y-2">
          <label htmlFor="reflection-lesson" className="text-xs text-muted-foreground">
            Key lesson
          </label>
          <input
            id="reflection-lesson"
            value={reflectionLesson}
            onChange={(e) => setReflectionLesson(e.target.value)}
            className="h-8 w-full rounded border border-white/10 bg-black/20 px-2 text-xs"
          />
        </div>
        <Button
          type="button"
          size="xs"
          variant="command-ghost"
          disabled={uploadBusy}
          onClick={() => void handleReflectionUpload()}
        >
          Upload Reflection
        </Button>
      </section>
    </div>
  );
}
