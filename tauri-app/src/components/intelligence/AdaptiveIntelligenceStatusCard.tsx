import { Loader2, RefreshCw } from "lucide-react";

import { IntelligenceHealthDot } from "@/components/intelligence/IntelligenceHealthDot";
import { useAdaptiveIntelligenceContext } from "@/context/AdaptiveIntelligenceContext";
import { Button } from "@/components/ui/button";
import {
  formatModeLabel,
  formatProviderLabel,
  formatReasoningLabel,
  formatTierLabel,
  HEALTH_DOT,
  resolveIntelligenceHealth,
  TIER_VISUAL,
} from "@/lib/intelligenceDisplay";
import { cn } from "@/lib/utils";

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-white/10 bg-black/30 px-3 py-2">
      <p className="font-mono text-[9px] tracking-[0.16em] text-muted-foreground uppercase">
        {label}
      </p>
      <p className="mt-1 truncate text-xs text-foreground">{value}</p>
    </div>
  );
}

interface AdaptiveIntelligenceStatusCardProps {
  className?: string;
}

export function AdaptiveIntelligenceStatusCard({ className }: AdaptiveIntelligenceStatusCardProps) {
  const {
    status,
    transitionSummary,
    loading,
    error,
    apiKeyConfigured,
    refresh,
    lastUpdatedAt,
    connected,
  } = useAdaptiveIntelligenceContext();

  const health = resolveIntelligenceHealth({ status, loading, error, transition: transitionSummary });
  const healthVisual = HEALTH_DOT[health];
  const tierVisual = status ? TIER_VISUAL[status.tier] : null;

  return (
    <section
      className={cn(
        "cockpit-panel overflow-hidden rounded-lg border border-white/10 bg-black/25 p-4",
        className,
      )}
    >
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <p className="font-mono text-[10px] tracking-[0.18em] text-cyan-200/80 uppercase">
            Adaptive Intelligence
          </p>
          <h3 className="text-sm font-medium text-foreground">Inference stack</h3>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0"
          onClick={() => void refresh()}
          aria-label="Refresh adaptive intelligence"
        >
          <RefreshCw className="size-3.5" />
        </Button>
      </div>

      {!apiKeyConfigured ? (
        <p className="rounded-md border border-amber-500/30 bg-amber-950/20 px-3 py-2 text-xs text-amber-200/90">
          Monitoring API key not configured. Complete setup credentials to enable history and
          metrics.
        </p>
      ) : null}

      {loading && !status ? (
        <div className="flex items-center gap-2 py-6 text-xs text-muted-foreground">
          <Loader2 className="size-4 animate-spin text-cyan-400/70" />
          Loading intelligence status…
        </div>
      ) : null}

      {error && !status ? (
        <p className="rounded-md border border-red-500/30 bg-red-950/20 px-3 py-2 text-xs text-red-200/90">
          {error.message}
        </p>
      ) : null}

      {status ? (
        <div className="space-y-3">
          <div className="flex items-center gap-3 rounded-md border border-white/10 bg-black/35 px-3 py-3">
            <IntelligenceHealthDot health={health} pulse={Boolean(transitionSummary?.is_transition)} />
            <div className="min-w-0 flex-1">
              <p className="font-mono text-lg font-semibold" style={{ color: tierVisual?.color }}>
                {formatTierLabel(status.tier)}
              </p>
              <p className="truncate text-xs text-muted-foreground">{status.recommended_model}</p>
            </div>
            <span
              className={cn(
                "rounded-full border px-2 py-0.5 font-mono text-[9px] tracking-wider uppercase",
                connected
                  ? "border-emerald-500/40 text-emerald-300"
                  : "border-white/15 text-muted-foreground",
              )}
            >
              {connected ? "Live" : "Poll"}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <DetailRow label="Provider" value={formatProviderLabel(status.recommended_provider)} />
            <DetailRow label="Mode" value={formatModeLabel(status.mode)} />
            <DetailRow label="Reasoning" value={formatReasoningLabel(status.reasoning_mode)} />
            <DetailRow label="Context" value={status.context_length.toLocaleString()} />
          </div>

          {status.degraded_state ? (
            <p className="rounded-md border border-amber-500/30 bg-amber-950/20 px-3 py-2 text-xs text-amber-200/90">
              Degraded: {status.status_reason || "Unknown reason"}
            </p>
          ) : null}

          {status.last_probe_error ? (
            <p className="rounded-md border border-red-500/30 bg-red-950/20 px-3 py-2 text-xs text-red-200/90">
              Probe error: {status.last_probe_error}
            </p>
          ) : null}

          {transitionSummary?.is_transition && transitionSummary.changed_fields.length > 0 ? (
            <div className="rounded-md border border-cyan-500/25 bg-cyan-950/15 px-3 py-2">
              <p className="font-mono text-[9px] tracking-[0.16em] text-cyan-300/80 uppercase">
                Recent transition
              </p>
              <p className="mt-1 text-xs text-foreground">
                Changed: {transitionSummary.changed_fields.join(", ")}
              </p>
            </div>
          ) : null}

          <p className="font-mono text-[10px] text-muted-foreground">
            Health: {healthVisual.label}
            {lastUpdatedAt ? ` · Updated ${new Date(lastUpdatedAt).toLocaleTimeString()}` : ""}
          </p>
        </div>
      ) : null}
    </section>
  );
}
