import { motion, useReducedMotion } from "framer-motion";
import { AlertTriangle, BrainCircuit, Loader2 } from "lucide-react";
import { useMemo } from "react";
import {
  type AdaptiveIntelligenceStatus,
  type AdaptiveTransitionSummary,
  type IntelligenceTier,
  normalizeAdaptiveIntelligenceStatus,
  useAdaptiveIntelligence,
} from "../hooks/useAdaptiveIntelligence";

const TIER_VISUAL: Record<
  IntelligenceTier,
  { label: string; color: string; border: string; glow: string }
> = {
  high: {
    label: "HIGH",
    color: "#fbbf24",
    border: "rgba(251,191,36,0.45)",
    glow: "rgba(251,191,36,0.22)",
  },
  standard: {
    label: "STD",
    color: "#00ff9f",
    border: "rgba(0,255,159,0.4)",
    glow: "rgba(0,255,159,0.2)",
  },
  light: {
    label: "LIGHT",
    color: "#94a3b8",
    border: "rgba(148,163,184,0.35)",
    glow: "rgba(148,163,184,0.15)",
  },
};

function formatMode(mode: string): string {
  return mode.replaceAll("_", " ").toUpperCase();
}

function buildTooltip(
  status: AdaptiveIntelligenceStatus,
  transitionSummary: AdaptiveTransitionSummary | null,
): string {
  const lines = [
    `Tier: ${status.tier}`,
    `Provider: ${status.recommended_provider}`,
    `Model: ${status.recommended_model}`,
    `Mode: ${status.mode}`,
    `Reasoning: ${status.reasoning_mode}`,
    `Context: ${status.context_length.toLocaleString()}`,
  ];
  if (status.degraded_state && status.status_reason) {
    lines.push(`Degraded: ${status.status_reason}`);
  }
  if (status.last_probe_error) {
    lines.push(`Probe error: ${status.last_probe_error}`);
  }
  if (transitionSummary?.is_transition && transitionSummary.changed_fields.length > 0) {
    lines.push(`Transition: ${transitionSummary.changed_fields.join(", ")}`);
  }
  return lines.join("\n");
}

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
  const tooltip = resolved ? buildTooltip(resolved, transitionSummary) : undefined;
  const showTransition = Boolean(transitionSummary?.is_transition);

  const ariaLabel = useMemo(() => {
    if (!resolved) {
      return "Adaptive intelligence status unavailable";
    }
    const degraded = resolved.degraded_state ? "degraded" : "healthy";
    return `Adaptive intelligence ${resolved.tier} tier, ${resolved.recommended_provider}, ${degraded}`;
  }, [resolved]);

  if (loading && !resolved) {
    return (
      <span
        className={`inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/55 px-3 py-1.5 text-[11px] text-zinc-500 ${className}`}
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
        className={`inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/55 px-3 py-1.5 text-[11px] text-zinc-500 ${className}`}
        title={error?.message ?? "No adaptive intelligence state published yet"}
        aria-label={ariaLabel}
      >
        <BrainCircuit className="h-3.5 w-3.5 text-zinc-600" />
        <span className="uppercase tracking-[0.14em]">AI n/a</span>
      </span>
    );
  }

  const degraded = resolved.degraded_state;
  const borderColor = degraded ? "rgba(251,146,60,0.55)" : tierVisual?.border ?? "rgba(255,255,255,0.12)";
  const accentColor = degraded ? "#fb923c" : tierVisual?.color ?? "#94a3b8";

  return (
    <motion.span
      className={`relative inline-flex items-center gap-2 rounded-full border bg-black/60 px-3 py-1.5 shadow-inner shadow-black/60 ${compact ? "text-[10px]" : "text-[11px]"} ${className}`}
      style={{
        borderColor,
        boxShadow: `0 0 18px ${degraded ? "rgba(251,146,60,0.12)" : tierVisual?.glow ?? "transparent"}`,
      }}
      title={tooltip}
      aria-label={ariaLabel}
      initial={reduceMotion ? false : { opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.2 }}
    >
      {showTransition ? (
        <span className="relative flex h-2 w-2 shrink-0">
          {!reduceMotion ? (
            <motion.span
              className="absolute inline-flex h-full w-full rounded-full"
              style={{ backgroundColor: accentColor }}
              animate={{ scale: [1, 2.4], opacity: [0.7, 0] }}
              transition={{ duration: 1.2, repeat: Infinity, ease: "easeOut" }}
            />
          ) : null}
          <span className="relative inline-flex h-2 w-2 rounded-full" style={{ backgroundColor: accentColor }} />
        </span>
      ) : (
        <BrainCircuit className="h-3.5 w-3.5 shrink-0" style={{ color: accentColor }} strokeWidth={1.75} />
      )}

      <span className="font-bold uppercase tracking-[0.16em]" style={{ color: accentColor }}>
        {tierVisual?.label ?? resolved.tier}
      </span>

      {!compact ? (
        <>
          <span aria-hidden className="text-zinc-700">
            ·
          </span>
          <span className="max-w-[72px] truncate uppercase tracking-[0.12em] text-zinc-400">
            {resolved.recommended_provider}
          </span>
          <span aria-hidden className="hidden text-zinc-700 sm:inline">
            ·
          </span>
          <span className="hidden uppercase tracking-[0.1em] text-zinc-500 sm:inline">
            {formatMode(resolved.mode)}
          </span>
        </>
      ) : null}

      {degraded ? (
        <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-400" aria-hidden />
      ) : null}
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
