import { TrendingDown, TrendingUp } from "lucide-react";

import {
  buildPolicyComparison,
  type PolicyComparisonMetricKey,
  type PolicySnapshot,
} from "@/lib/ppoPolicyComparisonModel";
import type { PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";
import { cn } from "@/lib/utils";

export interface PolicyComparisonProps {
  logs: PPOEvolutionMetric[];
  className?: string;
}

const METRIC_ROWS: Array<{
  key: PolicyComparisonMetricKey;
  label: string;
  format: (value: number) => string;
  positiveIsGood: boolean;
}> = [
  { key: "meanReward", label: "Mean Reward", format: (v) => v.toFixed(3), positiveIsGood: true },
  { key: "entropy", label: "Entropy", format: (v) => v.toFixed(3), positiveIsGood: false },
  { key: "winrate", label: "Winrate 5k", format: (v) => `${(v * 100).toFixed(1)}%`, positiveIsGood: true },
  { key: "sharpe", label: "Sharpe 5k", format: (v) => v.toFixed(2), positiveIsGood: true },
  { key: "policyLoss", label: "Policy Loss", format: (v) => v.toFixed(4), positiveIsGood: false },
  {
    key: "explainedVariance",
    label: "Explained Var",
    format: (v) => `${(v * 100).toFixed(1)}%`,
    positiveIsGood: true,
  },
];

function ActionMixBar({ snapshot }: { snapshot: PolicySnapshot }) {
  const { long, short, hold } = snapshot.actionDistribution;

  return (
    <div className="space-y-1.5">
      <p className="text-[10px] tracking-[0.14em] text-muted-foreground uppercase">Action mix</p>
      <div className="flex h-2 overflow-hidden rounded-full bg-white/10">
        <div className="bg-cyan-400/80" style={{ width: `${long * 100}%` }} />
        <div className="bg-violet-400/80" style={{ width: `${short * 100}%` }} />
        <div className="bg-slate-500/80" style={{ width: `${hold * 100}%` }} />
      </div>
    </div>
  );
}

function DeltaBadge({
  delta,
  positiveIsGood,
}: {
  delta: number;
  positiveIsGood: boolean;
}) {
  const isPositive = delta >= 0;
  const isGood = positiveIsGood ? isPositive : !isPositive;
  const Icon = isPositive ? TrendingUp : TrendingDown;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 font-mono text-[10px] tabular-nums",
        isGood ? "text-emerald-300" : "text-red-300",
      )}
    >
      <Icon className="size-3" aria-hidden />
      {isPositive ? "+" : ""}
      {delta.toFixed(3)}
    </span>
  );
}

export function PolicyComparison({ logs, className }: PolicyComparisonProps) {
  const comparison = buildPolicyComparison(logs);

  return (
    <section
      className={cn(
        "relative overflow-hidden rounded-lg border border-white/10 bg-black/20 p-4",
        className,
      )}
      aria-label="Policy comparison"
    >
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-cyan-400/30 to-violet-400/20"
        aria-hidden
      />
      <p className="mb-4 text-[10px] tracking-[0.14em] text-muted-foreground uppercase">
        Policy Comparison
      </p>

      {!comparison ? (
        <p className="text-xs text-muted-foreground">Need at least 2 training snapshots…</p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_auto_1fr]">
          <div className="space-y-3 rounded-lg border border-white/10 bg-black/25 p-3">
            <p className="font-mono text-xs tracking-wide text-cyan-200/90 uppercase">
              {comparison.birth.label}
            </p>
            {METRIC_ROWS.map((row) => (
              <div key={row.key} className="flex items-center justify-between gap-2 text-[11px]">
                <span className="text-muted-foreground">{row.label}</span>
                <span className="font-mono tabular-nums text-cyan-100/90">
                  {row.format(comparison.birth[row.key])}
                </span>
              </div>
            ))}
            <ActionMixBar snapshot={comparison.birth} />
          </div>

          <div className="hidden space-y-3 lg:flex lg:flex-col lg:justify-center">
            {METRIC_ROWS.map((row) => (
              <DeltaBadge
                key={row.key}
                delta={comparison.deltas[row.key]}
                positiveIsGood={row.positiveIsGood}
              />
            ))}
          </div>

          <div className="space-y-3 rounded-lg border border-cyan-400/20 bg-cyan-950/10 p-3">
            <p className="font-mono text-xs tracking-wide text-cyan-200 uppercase">
              {comparison.current.label}
            </p>
            {METRIC_ROWS.map((row) => (
              <div key={row.key} className="flex items-center justify-between gap-2 text-[11px]">
                <span className="text-muted-foreground">{row.label}</span>
                <span className="font-mono tabular-nums text-cyan-100/95">
                  {row.format(comparison.current[row.key])}
                </span>
              </div>
            ))}
            <ActionMixBar snapshot={comparison.current} />
          </div>
        </div>
      )}
    </section>
  );
}
