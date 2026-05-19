import type { LiveTradingSnapshot } from "@/lib/liveTradingTypes";
import { cn } from "@/lib/utils";

interface PositionBannerProps {
  trading: LiveTradingSnapshot | null;
  className?: string;
}

export function PositionBanner({ trading, className }: PositionBannerProps) {
  const position = trading?.position;
  const qty = position?.live_qty ?? 0;
  const side =
    qty > 0 ? "LONG" : qty < 0 ? "SHORT" : position?.side_signal?.toUpperCase() || "FLAT";

  const sideClass =
    side === "LONG" || side === "BUY"
      ? "decision-signal-buy"
      : side === "SHORT" || side === "SELL"
        ? "decision-signal-sell"
        : "decision-signal-hold";

  return (
    <div
      className={cn(
        "decision-theater-banner rounded-lg border border-white/10 bg-black/30 px-3 py-2.5",
        className,
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className={cn("rounded-md px-2 py-0.5 font-mono text-[10px] tracking-wider uppercase", sideClass)}>
            {side}
          </span>
          <span className="font-mono text-sm text-cyan-100">
            {qty !== 0 ? `${Math.abs(qty)} contracts` : "No open position"}
          </span>
        </div>
        <div className="flex flex-wrap gap-3 font-mono text-[10px] text-muted-foreground">
          <span>Entry {position?.entry_price?.toFixed(2) ?? "—"}</span>
          <span className={cn((position?.open_pnl ?? 0) >= 0 ? "text-emerald-300" : "text-red-300")}>
            Open {(position?.open_pnl ?? 0).toFixed(2)}
          </span>
          <span className={cn((position?.daily_pnl ?? 0) >= 0 ? "text-emerald-300/90" : "text-red-300/90")}>
            Daily {(position?.daily_pnl ?? 0).toFixed(2)}
          </span>
        </div>
      </div>
    </div>
  );
}
