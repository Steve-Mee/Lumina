import { motion, useReducedMotion } from "framer-motion";
import { BrainCircuit, Loader2, RefreshCw } from "lucide-react";
import {
  type AdaptiveIntelligenceStatus,
  type AdaptiveTransitionSummary,
  normalizeAdaptiveIntelligenceStatus,
  useAdaptiveIntelligence,
} from "../hooks/useAdaptiveIntelligence";
import {
  formatModeLabel,
  formatProviderLabel,
  formatReasoningLabel,
  formatTierLabel,
  HEALTH_DOT,
  resolveIntelligenceHealth,
  TIER_VISUAL,
} from "../lib/intelligenceDisplay";
import { IntelligenceHealthDot } from "./IntelligenceHealthDot";

export interface IntelligenceTierStatusCardProps {
  status?: AdaptiveIntelligenceStatus | null;
  transitionSummary?: AdaptiveTransitionSummary | null;
  fallbackStatus?: unknown;
  loading?: boolean;
  error?: Error | null;
  lastUpdatedAt?: number | null;
  onRefresh?: () => void;
  isFetching?: boolean;
  className?: string;
}

function DetailRow({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <motion.div
      className="rounded-xl border border-white/[0.06] bg-black/40 px-3 py-2.5"
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-zinc-500">{label}</p>
      <p className="mt-1 truncate text-sm font-medium text-zinc-100">{value}</p>
    </motion.div>
  );
}

/** Expanded adaptive intelligence panel for dashboard sidebars. */
export function IntelligenceTierStatusCard({
  status,
  transitionSummary = null,
  fallbackStatus,
  loading = false,
  error = null,
  lastUpdatedAt = null,
  onRefresh,
  isFetching = false,
  className = "",
}: IntelligenceTierStatusCardProps): JSX.Element {
  const reduceMotion = useReducedMotion() ?? false;
  const resolved =
    status ?? (fallbackStatus != null ? normalizeAdaptiveIntelligenceStatus(fallbackStatus) : null);
  const health = resolveIntelligenceHealth({
    status: resolved,
    loading,
    error,
    transition: transitionSummary,
  });
  const healthVisual = HEALTH_DOT[health];
  const tierVisual = resolved ? TIER_VISUAL[resolved.tier] : null;

  return (
    <motion.section
      className={`overflow-hidden rounded-3xl border border-[#00f0ff]/10 bg-gradient-to-br from-[#101018]/95 to-black/80 shadow-[0_20px_60px_-30px_rgba(0,240,255,0.2)] backdrop-blur-md ${className}`}
      initial={{ opacity: 0, y: reduceMotion ? 0 : 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduceMotion ? 0 : 0.35 }}
    >
      <motion.div
        className="border-b border-white/[0.06] px-5 py-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      >
        <div className="flex items-start justify-between gap-3">
          <motion.div className="flex items-center gap-3" initial={{ x: -6 }} animate={{ x: 0 }}>
            <span
              className="flex h-10 w-10 items-center justify-center rounded-2xl border border-[#00f0ff]/20 bg-black/60"
              style={{ boxShadow: `0 0 20px ${tierVisual?.glow ?? "transparent"}` }}
            >
              <BrainCircuit
                className="h-5 w-5"
                style={{ color: tierVisual?.color ?? "#94a3b8" }}
                strokeWidth={1.5}
              />
            </span>
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-[0.32em] text-[#00f0ff]/80">
                Adaptive Intelligence
              </p>
              <h3 className="mt-0.5 font-semibold text-white">Inference stack</h3>
            </div>
          </motion.div>
          {onRefresh ? (
            <motion.button
              type="button"
              onClick={() => void onRefresh()}
              className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-white/12 bg-black/55 text-[#00f0ff] transition-colors hover:border-[#00f0ff]/35"
              aria-label="Adaptive intelligence verversen"
              whileTap={reduceMotion ? undefined : { scale: 0.94 }}
            >
              <RefreshCw className={`h-4 w-4 ${isFetching ? "motion-safe:animate-spin" : ""}`} />
            </motion.button>
          ) : null}
        </div>
      </motion.div>

      <div className="space-y-4 px-5 py-4">
        {loading && !resolved ? (
          <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-black/45 px-4 py-6 text-sm text-zinc-500">
            <Loader2 className="h-5 w-5 motion-safe:animate-spin text-[#00f0ff]/70" />
            Intelligence status laden…
          </div>
        ) : null}

        {!loading && !resolved ? (
          <div className="rounded-2xl border border-red-500/25 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            {error?.message ?? "Geen adaptive intelligence state gepubliceerd."}
          </div>
        ) : null}

        {resolved ? (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <IntelligenceHealthDot health={health} pulse={transitionSummary?.is_transition} size="md" />
              <span
                className="rounded-full border px-2.5 py-1 text-[11px] font-bold uppercase tracking-[0.14em]"
                style={{
                  color: tierVisual?.color,
                  borderColor: tierVisual?.border,
                  backgroundColor: `${tierVisual?.color ?? "#94a3b8"}14`,
                }}
              >
                {formatTierLabel(resolved.tier)}
              </span>
              <span className="rounded-full border border-white/10 bg-black/50 px-2.5 py-1 text-[11px] font-semibold text-zinc-300">
                {formatProviderLabel(resolved.recommended_provider)}
              </span>
              <span
                className="rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider"
                style={{
                  borderColor: `${healthVisual.color}44`,
                  color: healthVisual.color,
                  backgroundColor: `${healthVisual.color}12`,
                }}
              >
                {healthVisual.label}
              </span>
            </div>

            <motion.div
              className="rounded-2xl border border-white/[0.08] bg-black/50 px-4 py-3"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.05 }}
            >
              <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-zinc-500">
                Recommended model
              </p>
              <p className="mt-1 break-all font-mono text-lg font-semibold text-white">
                {resolved.recommended_model}
              </p>
            </motion.div>

            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <DetailRow label="Reasoning" value={formatReasoningLabel(resolved.reasoning_mode)} />
              <DetailRow
                label="Context"
                value={resolved.context_length > 0 ? resolved.context_length.toLocaleString() : "—"}
              />
              <DetailRow label="Mode" value={formatModeLabel(resolved.mode)} />
              <DetailRow label="Backend" value={formatProviderLabel(resolved.recommended_provider)} />
            </div>

            <motion.div
              className="rounded-2xl border border-white/[0.06] bg-black/40 px-4 py-3"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.1 }}
            >
              <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-zinc-500">Status</p>
              {resolved.degraded_state && resolved.status_reason ? (
                <p className="mt-2 text-sm text-amber-200/90">{resolved.status_reason}</p>
              ) : (
                <p className="mt-2 text-sm text-zinc-400">
                  {health === "healthy"
                    ? "Inference stack operationeel."
                    : "Controleer inference-configuratie."}
                </p>
              )}
              {resolved.last_probe_error ? (
                <p className="mt-2 text-sm text-red-300/90">Probe: {resolved.last_probe_error}</p>
              ) : null}
            </motion.div>

            {transitionSummary?.is_transition && transitionSummary.changed_fields.length > 0 ? (
              <motion.div
                className="rounded-2xl border border-[#00f0ff]/20 bg-[#00f0ff]/[0.04] px-4 py-3"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
              >
                <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[#00f0ff]/80">
                  Transition
                </p>
                <p className="mt-2 text-sm text-zinc-300">
                  Gewijzigd: {transitionSummary.changed_fields.join(", ")}
                </p>
              </motion.div>
            ) : null}
          </>
        ) : null}

        {lastUpdatedAt ? (
          <p className="text-[11px] text-zinc-500">
            Laatste update {new Date(lastUpdatedAt).toLocaleTimeString()}
          </p>
        ) : null}
      </div>
    </motion.section>
  );
}

export interface IntelligenceTierStatusCardLiveProps {
  fallbackStatus?: unknown;
  className?: string;
  enabled?: boolean;
}

/** Polls adaptive intelligence API and renders the expanded status card. */
export function IntelligenceTierStatusCardLive({
  fallbackStatus,
  className = "",
  enabled = true,
}: IntelligenceTierStatusCardLiveProps): JSX.Element {
  const {
    status,
    transitionSummary,
    loading,
    error,
    lastUpdatedAt,
    refresh,
    isFetching,
  } = useAdaptiveIntelligence({ enabled });

  return (
    <IntelligenceTierStatusCard
      status={status}
      transitionSummary={transitionSummary}
      fallbackStatus={fallbackStatus}
      loading={loading}
      error={error}
      lastUpdatedAt={lastUpdatedAt}
      onRefresh={refresh}
      isFetching={isFetching}
      className={className}
    />
  );
}
