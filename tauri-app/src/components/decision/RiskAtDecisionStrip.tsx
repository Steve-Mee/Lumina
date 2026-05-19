import type { LiveTradingSnapshot } from "@/lib/liveTradingTypes";
import { cn } from "@/lib/utils";

interface RiskAtDecisionStripProps {
  trading: LiveTradingSnapshot | null;
  killSwitchActive?: boolean;
  className?: string;
}

export function RiskAtDecisionStrip({
  trading,
  killSwitchActive = false,
  className,
}: RiskAtDecisionStripProps) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-3 rounded-lg border border-white/10 bg-black/25 px-3 py-2 font-mono text-[10px]",
        className,
      )}
    >
      <span className="text-muted-foreground uppercase tracking-wider">Risk @ Decision</span>
      <span>Losses {trading?.consecutive_losses ?? 0}</span>
      <span>Recon pending {trading?.pending_reconciliations ?? 0}</span>
      <span>Regime conf {Math.round((trading?.regime_confidence ?? 0) * 100)}%</span>
      {killSwitchActive ? (
        <span className="text-red-300 uppercase">Kill switch active</span>
      ) : (
        <span className="text-emerald-300/90">Kill switch off</span>
      )}
    </div>
  );
}
