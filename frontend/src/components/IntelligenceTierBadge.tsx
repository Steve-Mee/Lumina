import { motion, useReducedMotion } from "framer-motion";
import { BrainCircuit, Loader2 } from "lucide-react";
import { useMemo } from "react";
import {
  type AdaptiveIntelligenceStatus,
  type AdaptiveTransitionSummary,
  normalizeAdaptiveIntelligenceStatus,
  useAdaptiveIntelligence,
} from "../hooks/useAdaptiveIntelligence";
import {
  buildIntelligenceTooltip,
  formatProviderLabel,
  formatTierLabel,
  resolveIntelligenceHealth,
  TIER_VISUAL,
} from "../lib/intelligenceDisplay";
import { IntelligenceHealthDot } from "./IntelligenceHealthDot";

export interface IntelligenceTierBadgeProps {
  status?: AdaptiveIntelligenceStatus | null;
  transitionSummary?: AdaptiveTransitionSummary | null;
  fallbackStatus?: unknown;
  loading?: boolean;
  error?: Error | null;
  compact?: boolean;
  className?: string;
}

/** Presentational tier badge — pass `status` or `fallbackStatus` from birth API. */
export function IntelligenceTierBadge({
  status,
  transitionSummary = null,
  fallbackStatus,
  loading = false,
  error = null,
  compact = false,
  className = "",
}: IntelligenceTierBadgeProps): JSX.Element {
  const reduceMotion = useReducedMotion() ?? false;
  const resolved =
    status ?? (fallbackStatus != null ? normalizeAdaptiveIntelligenceStatus(fallbackStatus) : null);
  const tierVisual = resolved ? TIER_VISUAL[resolved.tier] : null;
  const health = resolveIntelligenceHealth({
    status: resolved,
    loading,
    error,
    transition: transitionSummary,
  });
  const tooltip = resolved ? buildIntelligenceTooltip(resolved, transitionSummary) : undefined;
  const showTransitionPulse = Boolean(transitionSummary?.is_transition);
  const providerLabel = resolved ? formatProviderLabel(resolved.recommended_provider) : "";

  const ariaLabel = useMemo(() => {
    if (!resolved) {
      return "Adaptive intelligence status unavailable";
    }
    return `Adaptive intelligence ${resolved.tier} tier, model ${resolved.recommended_model}, ${providerLabel}, ${health}`;
  }, [health, providerLabel, resolved]);

  if (loading && !resolved) {
    return (
      <span
        className={`inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/70 px-3 py-1.5 text-[11px] text-zinc-500 shadow-inner shadow-black/60 ${className}`}
        aria-label="Loading adaptive intelligence"
      >
        <Loader2 className="h-3.5 w-3.5 motion-safe:animate-spin text-[#00f0ff]/70" />
        <span className="uppercase tracking-[0.14em]">Intel…</span>
      </span>
    );
  }

  if (!resolved) {
    return (
      <span
        className={`group inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/70 px-3 py-1.5 text-[11px] text-zinc-500 shadow-inner shadow-black/60 transition-all hover:border-red-500/30 ${className}`}
        title={error?.message ?? "No adaptive intelligence state published yet"}
        aria-label={ariaLabel}
      >
        <IntelligenceHealthDot health="error" />
        <BrainCircuit className="h-3.5 w-3.5 text-zinc-600" />
        <span className="uppercase tracking-[0.14em]">AI n/a</span>
      </span>
    );
  }

  const accentColor = tierVisual?.color ?? "#94a3b8";
  const borderColor = tierVisual?.border ?? "rgba(255,255,255,0.12)";
  const glow = tierVisual?.glow ?? "transparent";

  return (
    <motion.span
      className={`group relative inline-flex cursor-default items-center gap-2 rounded-full border bg-black/70 px-3 py-1.5 shadow-inner shadow-black/60 transition-all duration-200 hover:scale-[1.02] hover:border-[#00f0ff]/25 ${compact ? "text-[10px]" : "text-[11px]"} ${className}`}
      style={{
        borderColor,
        boxShadow: `0 0 18px ${glow}, inset 0 1px 0 rgba(255,255,255,0.04)`,
      }}
      title={tooltip}
      aria-label={ariaLabel}
      initial={reduceMotion ? false : { opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      whileHover={reduceMotion ? undefined : { boxShadow: `0 0 24px ${glow}` }}
      transition={{ duration: 0.2 }}
    >
      <IntelligenceHealthDot health={health} pulse={showTransitionPulse || health === "degraded"} />

      <span className="font-bold uppercase tracking-[0.16em]" style={{ color: accentColor }}>
        {formatTierLabel(resolved.tier)}
      </span>

      {compact ? (
        <span className="max-w-[64px] truncate uppercase tracking-[0.1em] text-zinc-500">
          {providerLabel}
        </span>
      ) : (
        <>
          <span aria-hidden className="text-zinc-700">
            ·
          </span>
          <span className="max-w-[140px] truncate font-medium tracking-tight text-zinc-200">
            {resolved.recommended_model}
          </span>
          <span
            className="hidden shrink-0 rounded-md border border-white/10 bg-white/[0.04] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-zinc-400 sm:inline"
          >
            {providerLabel}
          </span>
        </>
      )}
    </motion.span>
  );
}

export interface IntelligenceTierBadgeLiveProps {
  fallbackStatus?: unknown;
  compact?: boolean;
  className?: string;
  enabled?: boolean;
}

/** Polls `/api/monitoring/adaptive-intelligence/latest` and renders the badge. */
export function IntelligenceTierBadgeLive({
  fallbackStatus,
  compact = false,
  className = "",
  enabled = true,
}: IntelligenceTierBadgeLiveProps): JSX.Element {
  const { status, transitionSummary, loading, error } = useAdaptiveIntelligence({ enabled });

  return (
    <IntelligenceTierBadge
      status={status}
      transitionSummary={transitionSummary}
      fallbackStatus={fallbackStatus}
      loading={loading}
      error={error}
      compact={compact}
      className={className}
    />
  );
}
