import { BrainCircuit, Loader2 } from "lucide-react";

import { IntelligenceHealthDot } from "@/components/intelligence/IntelligenceHealthDot";
import { useAdaptiveIntelligenceContext } from "@/context/AdaptiveIntelligenceContext";
import {
  formatProviderLabel,
  formatTierLabel,
  resolveIntelligenceHealth,
  TIER_VISUAL,
} from "@/lib/intelligenceDisplay";
import { cn } from "@/lib/utils";

interface IntelligenceTierBadgeProps {
  className?: string;
  compact?: boolean;
}

export function IntelligenceTierBadgeLive({ className, compact = false }: IntelligenceTierBadgeProps) {
  const { status, transitionSummary, loading, error, connected } =
    useAdaptiveIntelligenceContext();
  const health = resolveIntelligenceHealth({ status, loading, error, transition: transitionSummary });
  const tierVisual = status ? TIER_VISUAL[status.tier] : null;

  if (loading && !status) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/50 px-2.5 py-1 font-mono text-[10px] text-muted-foreground",
          className,
        )}
      >
        <Loader2 className="size-3 animate-spin text-cyan-400/70" />
        Intel…
      </span>
    );
  }

  if (!status) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/50 px-2.5 py-1 font-mono text-[10px] text-muted-foreground",
          className,
        )}
        title={error?.message ?? "No adaptive intelligence state"}
      >
        <IntelligenceHealthDot health="error" />
        <BrainCircuit className="size-3" />
        N/A
      </span>
    );
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border bg-black/50 px-2.5 py-1 font-mono text-[10px] tracking-wider uppercase",
        className,
      )}
      style={{ borderColor: tierVisual?.border }}
      title={`${formatTierLabel(status.tier)} · ${status.recommended_model} · ${formatProviderLabel(status.recommended_provider)}${connected ? " · Live" : ""}`}
    >
      <IntelligenceHealthDot
        health={health}
        pulse={Boolean(transitionSummary?.is_transition)}
      />
      <BrainCircuit className="size-3" style={{ color: tierVisual?.color }} />
      <span style={{ color: tierVisual?.color }}>{formatTierLabel(status.tier)}</span>
      {!compact ? (
        <span className="hidden text-muted-foreground normal-case lg:inline">
          {status.recommended_model}
        </span>
      ) : null}
    </span>
  );
}
