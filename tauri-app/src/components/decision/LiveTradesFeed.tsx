import type { TradeRecord } from "@/lib/liveTradingTypes";
import { cn } from "@/lib/utils";

interface LiveTradesFeedProps {
  trades: TradeRecord[];
  className?: string;
}

export function LiveTradesFeed({ trades, className }: LiveTradesFeedProps) {
  return (
    <section className={cn("flex min-h-0 flex-col", className)}>
      <h4 className="mb-2 font-mono text-[10px] tracking-[0.16em] text-muted-foreground uppercase">
        Recent Trades
      </h4>
      <div className="min-h-0 flex-1 space-y-1.5 overflow-y-auto pr-1 [scrollbar-width:thin]">
        {trades.length === 0 ? (
          <p className="text-xs text-muted-foreground">No recent executions.</p>
        ) : (
          trades.map((trade, index) => (
            <div
              key={`${trade.ts ?? "trade"}-${index}`}
              className="rounded-md border border-white/8 bg-black/25 px-2.5 py-2"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-[10px] uppercase text-cyan-200/90">{trade.signal || "—"}</span>
                <span
                  className={cn(
                    "font-mono text-[10px] tabular-nums",
                    trade.pnl >= 0 ? "text-emerald-300" : "text-red-300",
                  )}
                >
                  {trade.pnl.toFixed(2)}
                </span>
              </div>
              <p className="mt-1 font-mono text-[9px] text-muted-foreground">
                {trade.entry.toFixed(2)} → {trade.exit.toFixed(2)} · qty {trade.qty}
                {trade.symbol ? ` · ${trade.symbol}` : ""}
              </p>
              <p className="font-mono text-[9px] text-muted-foreground/80">
                {trade.ts ? new Date(trade.ts).toLocaleString() : "Unknown time"}
              </p>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
