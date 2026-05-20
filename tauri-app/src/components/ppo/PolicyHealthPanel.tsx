import { Badge } from "@/components/ui/badge";
import {
  evaluatePolicyHealth,
  POLICY_HEALTH_STATUS_LABEL,
  type PolicyHealthMetric,
  type PolicyHealthStatus,
} from "@/lib/ppoPolicyHealth";
import type { PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";
import { cn } from "@/lib/utils";

export interface PolicyHealthPanelProps {
  metric: PPOEvolutionMetric | null;
  compact?: boolean;
  className?: string;
}

const STATUS_STYLES: Record<
  PolicyHealthStatus,
  { badge: string; dot: string }
> = {
  healthy: {
    badge:
      "border-emerald-500/40 bg-emerald-950/40 text-emerald-300 lumina-glow-edge",
    dot: "bg-emerald-400",
  },
  watch: {
    badge:
      "border-amber-500/40 bg-amber-950/40 text-amber-300 lumina-glow-edge",
    dot: "bg-amber-400",
  },
  critical: {
    badge: "border-red-500/40 bg-red-950/30 text-red-300",
    dot: "bg-red-400",
  },
};

function StatusIndicator({ status }: { status: PolicyHealthStatus }) {
  const styles = STATUS_STYLES[status];

  return (
    <Badge variant="outline" className={cn("font-mono text-[10px] tracking-wide", styles.badge)}>
      <span className={cn("mr-1.5 inline-block size-1.5 rounded-full", styles.dot)} aria-hidden />
      {POLICY_HEALTH_STATUS_LABEL[status]}
    </Badge>
  );
}

interface MetricRowProps {
  label: string;
  displayValue: string;
  metric: PolicyHealthMetric;
  compact?: boolean;
}

function MetricRow({ label, displayValue, metric, compact }: MetricRowProps) {
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-3 lumina-surface-muted rounded-md px-3",
        compact ? "py-2" : "py-2.5",
      )}
    >
      <div className="min-w-0">
        <p className="text-[10px] tracking-[0.14em] text-muted-foreground uppercase">{label}</p>
        <p className="font-mono text-sm tabular-nums text-cyan-100/95">{displayValue}</p>
      </div>
      <StatusIndicator status={metric.status} />
    </div>
  );
}

export function PolicyHealthPanel({ metric, compact = false, className }: PolicyHealthPanelProps) {
  return (
    <section
      className={cn(
        "relative overflow-hidden lumina-surface-muted rounded-lg p-3",
        className,
      )}
      aria-label="Policy health"
    >
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-cyan-400/30 to-violet-400/20"
        aria-hidden
      />
      <p className="mb-3 text-[10px] tracking-[0.14em] text-muted-foreground uppercase">
        Policy Health
      </p>

      {!metric ? (
        <p className="text-xs text-muted-foreground">Waiting for policy metrics…</p>
      ) : (
        <div className="space-y-2">
          {(() => {
            const snapshot = evaluatePolicyHealth(metric);
            return (
              <>
                <MetricRow
                  label="Policy Loss"
                  displayValue={snapshot.policyLoss.value.toFixed(4)}
                  metric={snapshot.policyLoss}
                  compact={compact}
                />
                <MetricRow
                  label="Value Loss"
                  displayValue={snapshot.valueLoss.value.toFixed(4)}
                  metric={snapshot.valueLoss}
                  compact={compact}
                />
                <MetricRow
                  label="Explained Variance"
                  displayValue={`${(snapshot.explainedVariance.value * 100).toFixed(1)}%`}
                  metric={snapshot.explainedVariance}
                  compact={compact}
                />
              </>
            );
          })()}
        </div>
      )}
    </section>
  );
}
