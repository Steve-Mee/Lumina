import type { ActiveSignal } from "@/lib/liveTradingTypes";
import { cn } from "@/lib/utils";

interface ActiveSignalCardProps {
  signal: ActiveSignal | null;
  className?: string;
}

function signalClass(signal: string): string {
  const normalized = signal.toUpperCase();
  if (normalized === "BUY" || normalized === "LONG") return "decision-signal-buy";
  if (normalized === "SELL" || normalized === "SHORT") return "decision-signal-sell";
  return "decision-signal-hold";
}

export function ActiveSignalCard({ signal, className }: ActiveSignalCardProps) {
  if (!signal) {
    return (
      <div className={cn("rounded-lg border border-white/10 bg-black/25 p-3 text-xs text-muted-foreground", className)}>
        No active signal telemetry.
      </div>
    );
  }

  return (
    <div className={cn("rounded-lg border border-white/10 bg-black/25 p-3", className)}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="font-mono text-[10px] tracking-[0.16em] text-muted-foreground uppercase">
          Active Signal
        </p>
        <span className={cn("rounded-md px-2 py-0.5 font-mono text-xs tracking-wider uppercase", signalClass(signal.signal))}>
          {signal.signal}
        </span>
      </div>
      <div className="mb-2 h-1.5 overflow-hidden rounded-full bg-white/5">
        <div
          className="h-full rounded-full bg-gradient-to-r from-violet-500 to-cyan-400"
          style={{ width: `${Math.round(signal.confidence * 100)}%` }}
        />
      </div>
      <p className="font-mono text-[11px] text-cyan-100/90">
        Confidence {Math.round(signal.confidence * 100)}% · Confluence {Math.round(signal.confluence * 100)}%
      </p>
      <p className="mt-2 text-[11px] leading-relaxed text-foreground/90">{signal.reason || "No reason published."}</p>
      <p className="mt-1 font-mono text-[10px] text-muted-foreground">
        Stop {signal.stop.toFixed(2)} · Target {signal.target.toFixed(2)} · {signal.strategy || "strategy n/a"}
      </p>
    </div>
  );
}
