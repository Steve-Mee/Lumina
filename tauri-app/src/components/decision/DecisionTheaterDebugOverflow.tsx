import { StatusChip } from "@/components/birth/BirthGenesisDeckPrimitives";
import {
  hasDebugPayload,
  type StageOverflowSignal,
} from "@/lib/decisionTheaterLayout";
import type { LiveTradingSnapshot } from "@/lib/liveTradingTypes";
import { cn } from "@/lib/utils";

interface DecisionTheaterDebugOverflowProps {
  trading: LiveTradingSnapshot | null;
  overflow?: StageOverflowSignal[];
  className?: string;
}

function chipState(glow: StageOverflowSignal["glow"]): "ok" | "partial" | "warn" | "idle" {
  if (glow === "emerald") return "ok";
  if (glow === "amber") return "warn";
  return "partial";
}

export function DecisionTheaterDebugOverflow({
  trading,
  overflow = [],
  className,
}: DecisionTheaterDebugOverflowProps) {
  const hasDebug = hasDebugPayload(trading);
  const hasOverflow = overflow.length > 0;
  if (!hasDebug && !hasOverflow) {
    return null;
  }

  return (
    <details className={cn("decision-theater-stage__telemetry mt-4 group", className)}>
      <summary className="mb-2 flex cursor-pointer list-none items-center font-mono text-[10px] tracking-[0.16em] text-muted-foreground uppercase [&::-webkit-details-marker]:hidden">
        Telemetry
      </summary>
      {hasOverflow ? (
        <div
          className="birth-mission-status-strip risk-envelope-status-strip flex flex-wrap gap-1.5"
          aria-label="Decision metrics"
        >
          {overflow.map((signal) => (
            <StatusChip
              key={signal.id}
              label={`${signal.label} ${signal.value}`}
              state={chipState(signal.glow)}
              tip={signal.label}
            />
          ))}
        </div>
      ) : null}
      {hasDebug ? (
        <div className="mt-2 space-y-2">
          {trading?.current_dream ? (
            <pre className="max-h-32 overflow-auto whitespace-pre-wrap font-mono text-[10px] text-muted-foreground">
              {JSON.stringify(trading.current_dream, null, 2)}
            </pre>
          ) : null}
          {trading?.runtime_state ? (
            <pre className="max-h-32 overflow-auto whitespace-pre-wrap font-mono text-[10px] text-muted-foreground">
              {JSON.stringify(trading.runtime_state, null, 2)}
            </pre>
          ) : null}
        </div>
      ) : null}
    </details>
  );
}
