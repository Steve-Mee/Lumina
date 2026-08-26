import { motion, useReducedMotion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  Baby,
  CheckCircle2,
  Loader2,
  Play,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useBirthStatus } from "../hooks/useBirthStatus";
import { IntelligenceTierBadgeLive } from "./IntelligenceTierBadge";

const BG_VOID = "#0a0a0f";
const ACCENT_CYAN = "#00f0ff";
const ACCENT_GREEN = "#00ff9f";
const EST_TRADES_PER_REAL_DAY = 450;

const ACTIVE_PROGRESS_STAGES = new Set([
  "detected",
  "loading_data",
  "training_running",
  "pipeline_boot",
  "historical_loaded",
  "synthetic_top_up",
  "parallel_simulation",
  "ppo_training",
  "deferred_calendar",
  "simulation_stall_retry",
]);

function formatCompact(n: number): string {
  if (!Number.isFinite(n)) {
    return "—";
  }
  const abs = Math.abs(n);
  if (abs >= 1_000_000) {
    return `${(n / 1_000_000).toFixed(abs >= 10_000_000 ? 0 : 1)}M`;
  }
  if (abs >= 1000) {
    return `${(n / 1000).toFixed(abs >= 100_000 ? 0 : 1)}k`;
  }
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function estimateRealDays(trainingTrades: number): number {
  return Math.max(1, Math.ceil(Math.max(1, Number(trainingTrades) || 1) / EST_TRADES_PER_REAL_DAY));
}

function statusTone(status: string): { label: string; color: string; pulse: boolean } {
  const s = status.trim().toLowerCase();
  if (s === "running" || s === "started") {
    return { label: "Training active", color: ACCENT_GREEN, pulse: true };
  }
  if (s === "completed" || s === "already_completed") {
    return { label: "Completed", color: ACCENT_GREEN, pulse: false };
  }
  if (s === "error") {
    return { label: "Failed", color: "#f87171", pulse: false };
  }
  if (s === "already_running") {
    return { label: "Already running", color: ACCENT_CYAN, pulse: true };
  }
  return { label: "Idle", color: "#94a3b8", pulse: false };
}

export default function BirthPhasePanel(): JSX.Element {
  const reduceMotion = useReducedMotion() ?? false;
  const [targetTrades, setTargetTrades] = useState(0);

  const { status, error, loading, isFetching, refresh, lastUpdatedAt, startBirth, starting } =
    useBirthStatus();

  const rawStatus = status?.status ?? "idle";
  const tone = statusTone(rawStatus);
  const progress = status?.progress;
  useEffect(() => {
    const progressTarget = Number(progress?.target_trades ?? 0);
    if (targetTrades <= 0 && Number.isFinite(progressTarget) && progressTarget > 0) {
      setTargetTrades(progressTarget);
    }
  }, [progress?.target_trades, targetTrades]);
  const tradesDone = progress?.trades_done ?? 0;
  const tradesTarget = progress?.target_trades ?? targetTrades;
  const estimatedRealDays = estimateRealDays(Math.max(1, targetTrades));
  const progressPct = Math.max(
    0,
    Math.min(
      100,
      status?.progress_pct ?? progress?.progress_pct ?? (tradesTarget > 0 ? (tradesDone / tradesTarget) * 100 : 0),
    ),
  );
  const stage = progress?.stage?.trim() || "not_started";
  const ppoSteps = progress?.ppo_steps ?? 0;
  const crossProcessActive =
    rawStatus.toLowerCase() === "idle" && ACTIVE_PROGRESS_STAGES.has(stage.toLowerCase());
  const displayTone = crossProcessActive
    ? { label: "Training mogelijk actief (andere runner)", color: ACCENT_CYAN, pulse: true }
    : tone;
  const progressMessage =
    typeof (progress as { message?: unknown } | undefined)?.message === "string"
      ? String((progress as { message?: string }).message)
      : status?.message ?? "";
  const remainingTrades =
    typeof (progress as { remaining_trades?: unknown } | undefined)?.remaining_trades === "number"
      ? Number((progress as { remaining_trades?: number }).remaining_trades)
      : null;
  const artifactsOk = Boolean(status?.artifacts_ok);
  const artifactsLabel = status?.artifacts_label ?? (artifactsOk ? "Artifacts OK" : "Artifacts missing");
  const phaseLabel = status?.phase_label ?? "Birth Phase";
  const hasValidTarget = Number.isFinite(targetTrades) && targetTrades >= 1000;
  const canStart = !starting && !["running", "started"].includes(rawStatus.toLowerCase()) && hasValidTarget;
  const showForce = rawStatus === "already_completed" || rawStatus === "completed";

  const startDisabledReason = useMemo(() => {
    if (starting) {
      return "Start wordt verwerkt…";
    }
    if (rawStatus === "running") {
      return "Birth Phase draait al.";
    }
    if (!hasValidTarget) {
      return "Kies eerst een target (minimaal 1000 trades).";
    }
    return null;
  }, [hasValidTarget, rawStatus, starting]);

  return (
    <motion.div
      className="relative min-h-screen text-zinc-200"
      style={{ backgroundColor: BG_VOID }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: reduceMotion ? 0 : 0.35 }}
    >
      <motion.div
        aria-hidden
        className="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_70%_50%_at_50%-10%,rgba(0,240,255,0.09),transparent_55%)]"
        animate={reduceMotion ? undefined : { opacity: [0.7, 1, 0.7] }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
      />

      <header className="sticky top-0 z-20 border-b border-[#00f0ff]/10 bg-black/60 backdrop-blur-xl">
        <motion.div
          className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-4 py-5 sm:px-6"
          initial={{ y: reduceMotion ? 0 : -8, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
        >
          <motion.div className="flex items-center gap-3" whileHover={reduceMotion ? undefined : { scale: 1.01 }}>
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-[#00f0ff]/30 bg-black/70 shadow-[0_0_28px_rgba(0,240,255,0.15)]">
              <Baby className="h-6 w-6 text-[#00f0ff]" strokeWidth={1.5} />
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.38em] text-[#00f0ff]/85">LUMINA</p>
              <h1 className="text-lg font-semibold text-white sm:text-xl">{phaseLabel}</h1>
              <p className="text-xs text-zinc-500">On-policy birth training via LuminaBirthEngine</p>
            </div>
          </motion.div>

          <motion.div className="flex flex-wrap items-center justify-end gap-2">
            <IntelligenceTierBadgeLive fallbackStatus={status?.adaptive_intelligence} />

            <span
              className="inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider"
              style={{
                borderColor: `${displayTone.color}44`,
                color: displayTone.color,
                background: `${displayTone.color}11`,
              }}
            >
              {displayTone.pulse ? (
                <span className="relative flex h-2 w-2">
                  <motion.span
                    className="absolute inline-flex h-full w-full rounded-full"
                    style={{ backgroundColor: displayTone.color }}
                    animate={reduceMotion ? {} : { scale: [1, 2.6], opacity: [0.7, 0] }}
                    transition={{ duration: 1.3, repeat: Infinity }}
                  />
                  <span
                    className="relative inline-flex h-2 w-2 rounded-full"
                    style={{ backgroundColor: displayTone.color }}
                  />
                </span>
              ) : null}
              {displayTone.label}
            </span>
            <motion.button
              type="button"
              onClick={() => void refresh()}
              className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/12 bg-black/55 text-[#00f0ff]"
              aria-label="Status verversen"
              whileTap={reduceMotion ? undefined : { scale: 0.94 }}
            >
              <RefreshCw className={`h-4 w-4 ${isFetching ? "motion-safe:animate-spin" : ""}`} />
            </motion.button>
          </motion.div>
        </motion.div>
      </header>

      <main className="relative z-10 mx-auto max-w-5xl space-y-6 px-4 py-8 sm:px-6">
        {error ? (
          <motion.div
            role="alert"
            className="flex items-start gap-3 rounded-2xl border border-amber-500/35 bg-amber-500/10 px-4 py-3 text-sm text-amber-100"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
            <span>{error.message}</span>
          </motion.div>
        ) : null}

        <motion.section
          className="rounded-3xl border border-[#00f0ff]/12 bg-gradient-to-br from-[#101018]/95 to-black/85 p-6 shadow-[0_24px_80px_-30px_rgba(0,240,255,0.22)]"
          initial={{ opacity: 0, y: reduceMotion ? 0 : 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
        >
          <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold text-white">Training control</h2>
              <p className="mt-1 text-sm text-zinc-500">
                Start de birth loop in een achtergrondthread. Voortgang komt uit{" "}
                <code className="rounded bg-black/50 px-1 text-[#00f0ff]/90">state/lumina_birth_progress.json</code>.
              </p>
            </div>
            <motion.div
              className={`rounded-xl border px-3 py-2 text-xs font-medium ${
                artifactsOk
                  ? "border-[#00ff9f]/35 bg-[#00ff9f]/10 text-[#00ff9f]"
                  : "border-amber-500/35 bg-amber-500/10 text-amber-200"
              }`}
              animate={artifactsOk && !reduceMotion ? { scale: [1, 1.02, 1] } : undefined}
              transition={{ duration: 2, repeat: Infinity }}
            >
              <span className="text-zinc-500">SSOT · </span>
              {artifactsLabel}
            </motion.div>
          </div>

          <div className="mb-6 grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
            <label className="block">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
                Target trades
              </span>
              <input
                type="number"
                min={1000}
                max={5_000_000}
                step={1000}
                value={targetTrades}
                disabled={!canStart && !showForce}
                onChange={(e) => setTargetTrades(Number(e.target.value) || 0)}
                className="mt-2 w-full rounded-xl border border-[#00f0ff]/25 bg-black/70 px-4 py-3 font-mono text-white outline-none focus:border-[#00f0ff]/55"
              />
              <p className="mt-2 text-xs text-zinc-400">
                Geschatte sessieduur: ~{estimatedRealDays.toLocaleString()} dagen (ceil(trades/
                {EST_TRADES_PER_REAL_DAY})). Dit is wall-clock, niet het history-venster.
              </p>
              <p className="mt-1 text-xs text-zinc-500">
                History start is Foundation 90 kalenderdagen (expand 180/365), niet trades/450.
              </p>
              <p className="mt-1 text-xs text-zinc-500">
                Hogere trade-budgets cyclen dezelfde tape vaker; synthetic top-up is practice-only.
              </p>
            </label>
            <div className="flex flex-wrap gap-2">
              <motion.button
                type="button"
                disabled={!canStart}
                title={startDisabledReason ?? undefined}
                onClick={() => void startBirth(targetTrades, false)}
                className="inline-flex min-w-[180px] items-center justify-center gap-2 rounded-xl border border-[#00f0ff]/45 bg-gradient-to-r from-[#00f0ff]/20 to-[#00ff9f]/15 px-5 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45"
                whileHover={canStart && !reduceMotion ? { scale: 1.02 } : undefined}
                whileTap={canStart && !reduceMotion ? { scale: 0.97 } : undefined}
              >
                {starting ? (
                  <Loader2 className="h-5 w-5 motion-safe:animate-spin" />
                ) : (
                  <Play className="h-5 w-5" />
                )}
                Start Birth Phase
              </motion.button>
              {showForce ? (
                <motion.button
                  type="button"
                  disabled={starting || !hasValidTarget}
                  onClick={() => void startBirth(targetTrades, true)}
                  className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/15 bg-black/50 px-4 py-3 text-sm text-zinc-300"
                  whileTap={reduceMotion ? undefined : { scale: 0.97 }}
                >
                  <Sparkles className="h-4 w-4" />
                  Force restart
                </motion.button>
              ) : null}
            </div>
          </div>

          {status?.message ? <p className="mb-4 text-sm text-zinc-400">{status.message}</p> : null}

          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="text-zinc-500">Progress</span>
            <span className="font-mono text-[#00f0ff]">
              {formatCompact(tradesDone)} / {formatCompact(tradesTarget)} ({progressPct.toFixed(1)}%)
            </span>
          </div>
          <motion.div className="h-3 overflow-hidden rounded-full bg-zinc-900 ring-1 ring-white/5">
            <motion.div
              className="h-full rounded-full"
              initial={false}
              animate={{ width: `${progressPct}%` }}
              transition={reduceMotion ? { duration: 0 } : { type: "spring", stiffness: 120, damping: 20 }}
              style={{
                background: `linear-gradient(90deg, ${ACCENT_CYAN}99, ${ACCENT_GREEN})`,
                boxShadow: `0 0 20px ${ACCENT_CYAN}55`,
              }}
            />
          </motion.div>

          <dl className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
            {[
              { k: "Stage", v: stage },
              { k: "PPO steps", v: ppoSteps.toLocaleString() },
              {
                k: "Elapsed",
                v: status?.elapsed_seconds != null ? `${status.elapsed_seconds}s` : loading ? "…" : "—",
              },
              { k: "Last sync", v: lastUpdatedAt ? new Date(lastUpdatedAt).toLocaleTimeString() : "—" },
            ].map((item) => (
              <motion.div
                key={item.k}
                className="rounded-xl border border-white/[0.06] bg-black/40 px-3 py-3"
                whileHover={reduceMotion ? undefined : { borderColor: "rgba(0,240,255,0.25)" }}
              >
                <dt className="text-[10px] uppercase tracking-wider text-zinc-500">{item.k}</dt>
                <dd className="mt-1 font-mono text-sm text-zinc-200">{item.v}</dd>
              </motion.div>
            ))}
          </dl>
        </motion.section>

        <motion.section
          className="grid gap-4 sm:grid-cols-2"
          initial={{ opacity: 0, y: reduceMotion ? 0 : 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.12 }}
        >
          <div className="rounded-2xl border border-[#00f0ff]/12 bg-black/50 p-5">
            <motion.div
              className="flex items-center gap-2 text-[#00f0ff]"
              initial={{ opacity: 0, x: reduceMotion ? 0 : -4 }}
              animate={{ opacity: 1, x: 0 }}
            >
              <Activity className="h-5 w-5" />
              <h3 className="font-semibold text-white">Live status</h3>
            </motion.div>
            <p className="mt-3 font-mono text-sm text-zinc-400">{rawStatus}</p>
            {crossProcessActive ? (
              <p className="mt-2 text-sm text-amber-200/90">
                Status is idle in dit proces, maar progress op schijf toont actieve stage{" "}
                <code className="text-zinc-300">{stage}</code>. Start training via dezelfde backend
                (POST /api/birth/start).
              </p>
            ) : null}
            {progressMessage ? <p className="mt-2 text-sm text-zinc-500">{progressMessage}</p> : null}
            {remainingTrades != null && remainingTrades > 0 ? (
              <p className="mt-1 text-xs text-zinc-500">Resterende trades: ~{remainingTrades.toLocaleString()}</p>
            ) : null}
            {status?.error ? <p className="mt-2 text-sm text-red-300">{status.error}</p> : null}
          </div>
          <motion.div
            className="rounded-2xl border border-[#00ff9f]/15 bg-black/50 p-5"
            animate={
              artifactsOk && !reduceMotion
                ? { boxShadow: ["0 0 0 rgba(0,255,159,0)", "0 0 24px rgba(0,255,159,0.12)", "0 0 0 rgba(0,255,159,0)"] }
                : undefined
            }
            transition={{ duration: 2.5, repeat: Infinity }}
          >
            <div className="flex items-center gap-2 text-[#00ff9f]">
              {artifactsOk ? (
                <CheckCircle2 className="h-5 w-5" />
              ) : (
                <AlertTriangle className="h-5 w-5 text-amber-400" />
              )}
              <h3 className="font-semibold text-white">Completion gate</h3>
            </div>
            <p className="mt-3 text-sm text-zinc-400">
              Volledige launcher unlock vereist completion flag{" "}
              <code className="text-zinc-300">lumina_birth_completed.flag</code> én{" "}
              <code className="text-zinc-300">lumina_ppo_policy.zip</code>.
            </p>
            <p className={`mt-2 text-sm font-medium ${artifactsOk ? "text-[#00ff9f]" : "text-amber-300"}`}>
              {artifactsLabel}
            </p>
          </motion.div>
        </motion.section>

        <p className="text-center text-[11px] text-zinc-600">
          Polling elke 2s via <code>/api/birth/status</code>
          {lastUpdatedAt ? ` · laatste update ${new Date(lastUpdatedAt).toLocaleTimeString()}` : null}
        </p>
      </main>
    </motion.div>
  );
}
