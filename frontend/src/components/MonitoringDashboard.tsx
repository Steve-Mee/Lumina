import {
  animate,
  motion,
  useMotionValue,
  useReducedMotion,
  useSpring,
  useTransform,
} from "framer-motion";
import {
  Activity,
  BrainCircuit,
  Cpu,
  Download,
  Gauge,
  HelpCircle,
  Pause,
  Play,
  Radio,
  RefreshCw,
  UserRound,
  Zap,
} from "lucide-react";
import { useCallback, useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import {
  type LuminaMetrics,
  LuminaMetricsFetchError,
  DEFAULT_POLLING_INTERVAL_MS,
  useLuminaMetrics,
} from "../hooks/useLuminaMetrics";

const BG_VOID = "#0a0a0f";
const ACCENT_CYAN = "#00f0ff";
const ACCENT_GREEN = "#00ff9f";

const DISPLAY_USER =
  typeof import.meta !== "undefined" && typeof import.meta.env?.VITE_DASHBOARD_OPERATOR === "string"
    ? import.meta.env.VITE_DASHBOARD_OPERATOR.trim() || "Operator"
    : "Operator";
const METRICS_SOURCE_PATH = "/api/monitoring/metrics/json";
const BUILD_MARKER = (() => {
  try {
    const raw = typeof import.meta !== "undefined" ? String(import.meta.url || "") : "";
    const match = raw.match(/index-([A-Za-z0-9_-]+)\.js/);
    return match?.[1] ?? "dev";
  } catch {
    return "dev";
  }
})();

/** Activity log level — colours map per spec */
type ActivityLevel = "INFO" | "PROGRESS";

type ActivityRow = {
  id: string;
  ts: number;
  level: ActivityLevel | "WARN";
  message: string;
};

function nextRowId(): string {
  try {
    return crypto.randomUUID();
  } catch {
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }
}

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
  return n.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function deriveOperationalMode(metrics: LuminaMetrics): string {
  const p = metrics.phase.trim().toLowerCase();
  if (p.includes("ppo") || p.includes("training")) {
    return "PPO training corridor";
  }
  if (p.includes("birth") || p.includes("first_boot") || p.includes("first boot")) {
    return "Birth Phase training";
  }
  if (p.includes("evolution")) {
    return "Evolution / promotion";
  }
  if (metrics.synthetic_percent > 55) {
    return "Synthetic-biased simulation";
  }
  if (metrics.historical_days > 0) {
    return "Historical-data anchored";
  }
  return "Live observatory";
}

function pct01(numerator: number, denominator: number): number {
  if (denominator <= 0 || !Number.isFinite(numerator)) {
    return 0;
  }
  return Math.max(0, Math.min(1, numerator / denominator));
}

/** Tooltip: keyboard-focusable hover/focus panel */
function FieldTip({
  tip,
  label,
}: {
  tip: string;
  label?: string;
}): JSX.Element {
  const tipId = useId();

  return (
    <span className="group/tip relative ml-1.5 inline-flex align-middle">
      <button
        type="button"
        className="-m-1 rounded-full p-1 text-[#00f0ff]/55 outline-none transition hover:text-[#00f0ff] focus-visible:ring-2 focus-visible:ring-[#00f0ff]/55"
        aria-describedby={tipId}
        aria-label={label ?? "Metric uitleg"}
      >
        <HelpCircle className="h-3.5 w-3.5" strokeWidth={1.75} />
      </button>
      <span
        id={tipId}
        role="tooltip"
        className="pointer-events-none invisible absolute bottom-full left-1/2 z-50 mb-2 w-max max-w-[min(280px,calc(100vw-24px))] -translate-x-1/2 translate-y-1 rounded-xl border border-white/10 bg-zinc-950/98 px-3 py-2 text-left text-[11px] leading-snug text-zinc-300 opacity-0 shadow-2xl shadow-black/70 backdrop-blur-md transition-opacity duration-150 group-focus-within/tip:visible group-focus-within/tip:opacity-100 group-hover/tip:visible group-hover/tip:opacity-100"
      >
        {tip}
      </span>
    </span>
  );
}

/** Card wrapper groups hover semantics for tooltip */
function MetricGlassCard({
  children,
  tip,
  tipAriaLabel,
  className,
  delay,
  reduceMotion,
}: {
  children: ReactNode;
  tip?: string;
  tipAriaLabel?: string;
  className?: string;
  delay?: number;
  reduceMotion: boolean | null;
}): JSX.Element {
  return (
    <motion.div
      className={`group relative rounded-2xl border border-[#00f0ff]/12 bg-gradient-to-br from-[#13131f]/95 to-black/85 p-[1px] shadow-[0_12px_50px_-20px_rgba(0,240,255,0.35)] ${className ?? ""}`}
      initial={{ opacity: 0, y: reduceMotion ? 0 : 10 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ duration: reduceMotion ? 0 : 0.45, delay: delay ?? 0, ease: [0.22, 1, 0.36, 1] }}
      whileHover={reduceMotion ? undefined : { y: -6, transition: { type: "spring", stiffness: 420, damping: 26 } }}
    >
      <div className="relative rounded-[calc(1rem-1px)] bg-[#090911]/90 p-5 backdrop-blur-md">
        {tip !== undefined ? (
          <div className="absolute right-3 top-3 flex items-center">
            <FieldTip tip={tip} label={tipAriaLabel} />
          </div>
        ) : null}
        {children}
      </div>
    </motion.div>
  );
}

/** Horizontal load bar segment */
function GlowBar({
  value,
  color,
  label,
  reduceMotion,
}: {
  value: number;
  color: string;
  label: string;
  reduceMotion: boolean | null;
}): JSX.Element {
  const pct = Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0));

  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-[11px] text-zinc-500">
        <span>{label}</span>
        <span className="font-mono text-zinc-400">{pct.toFixed(0)}%</span>
      </div>
      <div className="h-2.5 overflow-hidden rounded-full bg-zinc-900/90 ring-1 ring-white/[0.05]">
        <motion.div
          className="h-full rounded-full"
          initial={false}
          animate={{ width: `${pct}%` }}
          transition={reduceMotion ? { duration: 0 } : { type: "spring", stiffness: 220, damping: 28 }}
          style={{
            background: `linear-gradient(90deg, ${color}99, ${color})`,
            boxShadow: `0 0 18px ${color}55`,
          }}
        />
      </div>
    </div>
  );
}

/** Spring-smoothed number for live counters */
function LiveStatNumber({
  value,
  decimals = 0,
  reduceMotion,
}: {
  value: number;
  decimals?: number;
  reduceMotion: boolean | null;
}): JSX.Element {
  const mv = useMotionValue(value);
  const spring = useSpring(mv, {
    stiffness: reduceMotion ? 800 : 180,
    damping: reduceMotion ? 80 : 22,
    mass: 0.4,
  });
  const text = useTransform(spring, (v) => {
    if (decimals > 0) {
      return v.toLocaleString(undefined, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      });
    }
    return Math.round(v).toLocaleString();
  });

  useEffect(() => {
    mv.set(value);
    if (reduceMotion) {
      animate(mv, value, { duration: 0 });
    }
  }, [value, mv, reduceMotion]);

  return <motion.span className="font-mono tabular-nums tracking-tight">{text}</motion.span>;
}

/** Central circular milestone progress */
function TradeOrbitRing({
  tradesCompleted,
  target,
  hasTarget,
  reduceMotion,
}: {
  tradesCompleted: number;
  target: number;
  hasTarget: boolean;
  reduceMotion: boolean | null;
}): JSX.Element {
  const pct = pct01(tradesCompleted, target);
  const size = 320;
  const stroke = 12;
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const dashOffset = circumference * (1 - pct);

  return (
    <div className="relative mx-auto flex w-full max-w-[min(340px,100%)] shrink-0 flex-col items-center">
      <div
        className="pointer-events-none absolute inset-0 rounded-full opacity-55 blur-[64px]"
        style={{ background: `radial-gradient(circle, ${ACCENT_CYAN}22 0%, transparent 65%)` }}
      />

      <div className="relative aspect-square w-full" style={{ maxWidth: size }}>
        <svg className="-rotate-90" viewBox={`0 0 ${size} ${size}`}>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="#1a1a24"
            strokeWidth={stroke}
          />
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={ACCENT_CYAN}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: dashOffset }}
            transition={reduceMotion ? { duration: 0 } : { type: "spring", stiffness: 90, damping: 18 }}
            style={{
              filter: `drop-shadow(0 0 14px ${ACCENT_CYAN}aa)`,
            }}
          />
        </svg>

        <div className="absolute inset-0 flex flex-col items-center justify-center px-10 text-center">
          <span className="text-[11px] font-semibold uppercase tracking-[0.32em] text-zinc-500">Trade horizon</span>
          <motion.div
            className="mt-2 bg-gradient-to-b from-white to-[#bdbdcc] bg-clip-text font-sans text-[clamp(1.95rem,5.5vw,2.85rem)] font-semibold tracking-tight text-transparent"
            initial={{ scale: reduceMotion ? 1 : 0.96, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: reduceMotion ? 0 : 0.5 }}
          >
            {hasTarget ? (
              <>
                <LiveStatNumber value={tradesCompleted} reduceMotion={reduceMotion} />
                <span className="mx-2 text-[#414152]">/</span>
                <span className="font-mono text-zinc-500">{formatCompact(target)}</span>
              </>
            ) : (
              <span className="font-mono text-zinc-500">—</span>
            )}
          </motion.div>
          <p className="mt-4 text-[12px] text-zinc-500">
            {hasTarget
              ? `${Math.round(pct * 1000) / 10}% complete • live counter from telemetry`
              : "Target not selected yet — start first boot training"}
          </p>
        </div>
      </div>
    </div>
  );
}

function useActivityJournal(
  metrics: LuminaMetrics | null,
  error: LuminaMetricsFetchError | Error | null,
  lastUpdatedAt: number | null,
  loading: boolean,
): ActivityRow[] {
  const [rows, setRows] = useState<ActivityRow[]>([]);
  const prevTrades = useRef<number | null>(null);
  const prevSession = useRef<string>("");
  const prevStage = useRef<string>("");
  const prevSessionActive = useRef<boolean | null>(null);
  const initRef = useRef(false);
  const lastErrDigest = useRef<string | null>(null);
  const channelInfoRef = useRef(false);

  const push = useCallback((level: ActivityRow["level"], message: string) => {
    setRows((prev) => {
      const row: ActivityRow = { id: nextRowId(), ts: Date.now(), level, message };
      return [...prev.slice(-149), row];
    });
  }, []);

  useEffect(() => {
    if (error instanceof LuminaMetricsFetchError) {
      const digest = `${error.status}:${error.message}`;
      if (lastErrDigest.current === digest) {
        return;
      }
      lastErrDigest.current = digest;
      push("WARN", `[HTTP ${error.status}] ${error.message}`);
      return;
    }
    if (error) {
      const digest = error.message;
      if (lastErrDigest.current === digest) {
        return;
      }
      lastErrDigest.current = digest;
      push("WARN", error.message);
      return;
    }
    if (lastErrDigest.current !== null) {
      lastErrDigest.current = null;
      push("INFO", "Verbinding hersteld • metrics transport weer live.");
    }
  }, [error, push]);

  useEffect(() => {
    if (!metrics || !lastUpdatedAt) {
      return;
    }
    if (!metrics.session_active) {
      if (prevSessionActive.current === true) {
        push("INFO", "Sessie idle — activity stream pauzeert.");
      }
      prevSessionActive.current = false;
      return;
    }
    prevSessionActive.current = true;
    if (!initRef.current) {
      initRef.current = true;
      push("INFO", "Activity stream geactiveerd.");
    }
    if (!channelInfoRef.current && !loading) {
      channelInfoRef.current = true;
      push(
        "INFO",
        `JSON metrics channel online • snapshots elke ${(DEFAULT_POLLING_INTERVAL_MS / 1000).toFixed(1)}s via /api proxy.`,
      );
    }

    const t = metrics.training_completed_trades || metrics.trades_completed;
    const prev = prevTrades.current;
    prevTrades.current = t;
    const sessionKey = `${metrics.session_kind}:${metrics.session_active ? "1" : "0"}`;
    const stageKey = metrics.first_boot_stage || "";
    const sessionChanged = prevSession.current !== sessionKey;
    const stageChanged = prevStage.current !== stageKey;
    prevSession.current = sessionKey;
    prevStage.current = stageKey;

    let deltaFrag = "";
    if (prev === null) {
      deltaFrag = "baseline ingest";
    } else if (t !== prev) {
      const d = t - prev;
      const sign = d > 0 ? "+" : "";
      deltaFrag = `trade delta ${sign}${formatCompact(Math.abs(d))}`;
    }

    const velFrag =
      metrics.velocity >= 1000 ? formatCompact(metrics.velocity) : metrics.velocity.toFixed(1);

    if (!sessionChanged && !stageChanged && prev !== null && t === prev) {
      return;
    }
    const msg = [
      `Tick ${new Date(lastUpdatedAt).toLocaleTimeString()}`,
      `session "${metrics.session_kind}"`,
      `trades ${formatCompact(t)}${deltaFrag ? ` • ${deltaFrag}` : ""}`,
      `velocity ${velFrag} evt/s`,
      `phase "${metrics.phase || "UNKNOWN"}"`,
      `Twin reward ${metrics.approval_twin_reward.toFixed(2)}`,
    ].join(" · ");

    push("PROGRESS", msg);
  }, [metrics, lastUpdatedAt, loading, push]);

  return rows;
}

function exportMonitoringReport(metrics: LuminaMetrics | null, meta: { paused: boolean; lastUpdatedAt: number | null }) {
  const payload = {
    exported_at: new Date().toISOString(),
    paused: meta.paused,
    last_refresh_client_ms: meta.lastUpdatedAt,
    metrics_snapshot: metrics,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `lumina-monitoring-report-${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function MonitoringDashboard(): JSX.Element {
  const prefersReducedMotion = useReducedMotion();
  const reduceMotion = prefersReducedMotion ?? false;

  const [paused, setPaused] = useState(false);

  const { metrics, error, loading, isFetching, refresh, lastUpdatedAt } = useLuminaMetrics({
    enabled: !paused,
    pollingIntervalMs: DEFAULT_POLLING_INTERVAL_MS,
  });

  const liveMetrics = metrics;
  const stream = useActivityJournal(liveMetrics, error, lastUpdatedAt, loading);
  const streamRef = useRef<HTMLDivElement>(null);

  const modeLabel = useMemo(() => (liveMetrics ? deriveOperationalMode(liveMetrics) : "—"), [liveMetrics]);
  const phaseLabel = liveMetrics?.phase.trim() || "—";
  const targetTrades = liveMetrics?.training_target_trades ?? 0;
  const hasTrainingTarget = Boolean(liveMetrics?.training_target_applicable) && targetTrades > 0;
  const completedTrades = liveMetrics?.training_completed_trades ?? liveMetrics?.trades_completed ?? 0;
  const sessionLabel = liveMetrics?.session_kind?.trim() || "idle";
  const sessionActive = Boolean(liveMetrics?.session_active);
  const ppoSteps = liveMetrics?.ppo_steps ?? 0;
  const ppoTotal = Math.max(1, liveMetrics?.ppo_timesteps_total ?? 300000);
  const ppoPct = Math.max(
    0,
    Math.min(100, liveMetrics?.ppo_progress_pct ?? (ppoSteps / Math.max(1, ppoTotal)) * 100),
  );
  const showPpoProgress = sessionActive && (liveMetrics?.phase?.trim().toLowerCase() === "ppo_training" || ppoSteps > 0);

  /** scroll activity to bottom when new rows arrive */
  useEffect(() => {
    const el = streamRef.current;
    if (!el) {
      return;
    }
    el.scrollTop = el.scrollHeight;
  }, [stream.length]);

  return (
    <div
      className="relative min-h-screen text-zinc-200"
      style={{ backgroundColor: BG_VOID }}
    >
      {/* ambient vignette */}
      <div aria-hidden className="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_70%_50%_at_50%-10%,rgba(0,240,255,0.085),transparent_55%)]" />
      <div aria-hidden className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_100%_20%,rgba(0,255,159,0.07),transparent_45%)]" />

      {/* top bar */}
      <header className="sticky top-0 z-30 border-b border-[#00f0ff]/10 bg-black/55 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1480px] flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <div
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-[#00f0ff]/25 bg-black/70 shadow-inner shadow-black/70"
              style={{ boxShadow: `0 0 24px ${ACCENT_CYAN}22,inset 0 0 20px rgba(0,240,255,0.06)` }}
            >
              <Radio className="h-6 w-6 text-[#00f0ff]" strokeWidth={1.5} />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-[0.42em] text-[#00f0ff]/80">LUMINA</p>
              <h1 className="truncate font-semibold tracking-tight text-white">Executive monitoring cockpit</h1>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-end gap-3 sm:gap-4">
            <span className="relative inline-flex items-center gap-2 rounded-full border border-[#00ff9f]/30 bg-black/65 px-3 py-1.5">
              <span className="relative flex h-2 w-2">
                <motion.span
                  className="absolute inline-flex h-full w-full rounded-full bg-[#00ff9f]"
                  animate={reduceMotion ? {} : { scale: [1, 2.9], opacity: [0.72, 0] }}
                  transition={{ duration: 1.4, repeat: Infinity, repeatType: "loop", ease: "easeOut" }}
                />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-[#00ff9f] shadow-[0_0_10px_#00ff9faa]" />
              </span>
              <span className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#00ff9f]">
                {sessionActive ? sessionLabel.replaceAll("_", " ") : "Idle"}
              </span>
            </span>

            <motion.button
              type="button"
              onClick={() => void refresh()}
              className="inline-flex items-center gap-2 rounded-full border border-white/12 bg-black/55 px-3 py-2 text-[12px] text-zinc-300 shadow-lg shadow-black/50 transition-colors hover:border-[#00f0ff]/35 hover:text-white"
              aria-label="Handmatig verversen"
              whileTap={reduceMotion ? undefined : { scale: 0.97 }}
            >
              <RefreshCw className={`h-4 w-4 shrink-0 text-[#00f0ff] ${isFetching ? "motion-safe:animate-spin" : ""}`} />
              <span className="hidden sm:inline">Manual sync</span>
            </motion.button>

            <div className="hidden h-10 w-px shrink-0 bg-white/10 sm:block" />

            <div className="flex shrink-0 items-center gap-2 rounded-full border border-white/12 bg-black/45 py-1.5 pl-1.5 pr-3 shadow-inner shadow-black/50">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-[#00f0ff]/20 to-transparent">
                <UserRound className="h-4 w-4 text-[#00f0ff]" />
              </span>
              <div className="min-w-0">
                <p className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">Operator</p>
                <p className="max-w-[140px] truncate font-medium text-white">{DISPLAY_USER}</p>
              </div>
            </div>
          </div>
        </div>

        {/* auto-refresh ticker strip */}
        <div className="border-t border-[#00f0ff]/8 bg-black/35 px-4 py-2 text-[11px] text-zinc-500 sm:px-6 lg:px-8">
          <div className="mx-auto flex max-w-[1480px] flex-wrap items-center gap-x-4 gap-y-1">
            <span className="inline-flex items-center gap-2 text-zinc-400">
              <span
                className="hidden h-1.5 w-1.5 rounded-full sm:inline"
                style={{ backgroundColor: paused ? "#ef4444" : isFetching ? ACCENT_CYAN : ACCENT_GREEN }}
              />
              <span>{paused ? "Polling gepauseerd." : `Auto-refresh elke ${(DEFAULT_POLLING_INTERVAL_MS / 1000).toFixed(1)}s`}</span>
            </span>
            <span aria-hidden className="hidden text-zinc-700 sm:inline">/</span>
            <span className={`${error ? "text-amber-300" : "text-[#00ff9f]/90"}`}>
              {error ? "Laatste poll met fout — zie activity stream" : "Backendverbinding OK (als API key geldig is)"}
            </span>
            {lastUpdatedAt ? (
              <>
                <span aria-hidden className="hidden text-zinc-700 sm:inline">/</span>
                <span>Laatste update {new Date(lastUpdatedAt).toLocaleTimeString()}</span>
              </>
            ) : null}
            <span aria-hidden className="hidden text-zinc-700 sm:inline">/</span>
            <span className="font-mono text-zinc-500">
              src {METRICS_SOURCE_PATH} | build {BUILD_MARKER} | {sessionLabel}
            </span>
          </div>
        </div>
      </header>

      <main className="relative z-10 mx-auto max-w-[1480px] px-4 py-8 sm:px-6 lg:px-8 lg:py-10">
        <div className="grid grid-cols-1 gap-8 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,0.75fr)] xl:items-start xl:gap-10">
          {/* left column */}
          <div className="space-y-8">
            <section className="rounded-3xl border border-[#00f0ff]/10 bg-gradient-to-br from-[#101018]/95 to-black/80 p-6 shadow-[0_24px_80px_-30px_rgba(0,240,255,0.25)] backdrop-blur-md sm:p-8">
              <div className="mb-8 flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-white sm:text-xl">Training horizon</h2>
                  <p className="mt-1 max-w-md text-sm text-zinc-500">
                    Centrale voortgang op simulatie-trades
                    {hasTrainingTarget
                      ? ` (target ${formatCompact(targetTrades)})`
                      : " (target not configured yet)"}
                    .
                    {" "}Live data via{" "}
                    <code className="rounded bg-black/50 px-1 font-mono text-[#00f0ff]/90">useLuminaMetrics</code>.
                  </p>
                </div>
                <TradeOrbitRing
                  tradesCompleted={completedTrades}
                  target={hasTrainingTarget ? targetTrades : 1}
                  hasTarget={hasTrainingTarget}
                  reduceMotion={reduceMotion}
                />
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
                <MetricGlassCard
                  reduceMotion={reduceMotion}
                  delay={0.02}
                  tip="Aantal voltooide sim-trades in de huidige training-run. Weergave is gebonden aan de backend snapshot."
                  tipAriaLabel="Uitleg Trades Completed"
                >
                  <div className="flex items-start justify-between gap-2 pr-8">
                    <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#00f0ff]/20 bg-[#00f0ff]/5">
                      <Activity className="h-5 w-5 text-[#00f0ff]" />
                    </span>
                    <span className="text-[10px] font-semibold uppercase tracking-widest text-zinc-500">Trades</span>
                  </div>
                  <p className="mt-4 text-[11px] font-medium uppercase tracking-wider text-zinc-500">Trades completed</p>
                  <p className="mt-2 text-3xl font-semibold text-white">
                    <LiveStatNumber
                      value={liveMetrics?.training_completed_trades ?? liveMetrics?.trades_completed ?? 0}
                      reduceMotion={reduceMotion}
                    />
                  </p>
                </MetricGlassCard>

                <MetricGlassCard
                  reduceMotion={reduceMotion}
                  delay={0.06}
                  tip="Stappen op de PPO-policy sinds run-start. Corrigeert op basis van collector velden in de metrics JSON."
                  tipAriaLabel="Uitleg PPO steps"
                >
                  <div className="flex items-start justify-between gap-2 pr-8">
                    <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#00ff9f]/20 bg-[#00ff9f]/5">
                      <BrainCircuit className="h-5 w-5 text-[#00ff9f]" />
                    </span>
                    <span className="text-[10px] font-semibold uppercase tracking-widest text-zinc-500">Policy</span>
                  </div>
                  <p className="mt-4 text-[11px] font-medium uppercase tracking-wider text-zinc-500">PPO policy steps</p>
                  <p className="mt-2 text-3xl font-semibold text-white">
                    <LiveStatNumber value={liveMetrics?.ppo_steps ?? 0} reduceMotion={reduceMotion} />
                  </p>
                  {showPpoProgress ? (
                    <div className="mt-3 space-y-2">
                      <div className="flex items-center justify-between text-[11px] text-zinc-500">
                        <span>{formatCompact(ppoSteps)} / {formatCompact(ppoTotal)} steps</span>
                        <span>{ppoPct.toFixed(1)}%</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-zinc-900/70">
                        <div
                          className="h-1.5 rounded-full bg-[#00ff9f]/80 transition-all"
                          style={{ width: `${ppoPct}%` }}
                        />
                      </div>
                    </div>
                  ) : null}
                </MetricGlassCard>

                <MetricGlassCard
                  reduceMotion={reduceMotion}
                  delay={0.1}
                  tip="Belonings-signaal van de ApprovalTwin laag — gebruikt voor promotionele gates in evolution flow."
                  tipAriaLabel="Uitleg ApprovalTwin reward"
                >
                  <div className="flex items-start justify-between gap-2 pr-8">
                    <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#00f0ff]/20 bg-[#00f0ff]/5">
                      <Zap className="h-5 w-5 text-[#00f0ff]" />
                    </span>
                    <span className="text-[10px] font-semibold uppercase tracking-widest text-zinc-500">Twin</span>
                  </div>
                  <p className="mt-4 text-[11px] font-medium uppercase tracking-wider text-zinc-500">ApprovalTwin reward</p>
                  <p className="mt-2 text-3xl font-semibold text-white">
                    <LiveStatNumber value={liveMetrics?.approval_twin_reward ?? 0} decimals={2} reduceMotion={reduceMotion} />
                  </p>
                </MetricGlassCard>

                <MetricGlassCard
                  reduceMotion={reduceMotion}
                  delay={0.14}
                  className="sm:col-span-2 xl:col-span-1"
                  tip="CPU / GPU / RAM load uit hardware telemetry. Waarden zijn procenten (0–100) wanneer de backend ze levert."
                  tipAriaLabel="Uitleg system health"
                >
                  <div className="flex items-start justify-between gap-2 pr-8">
                    <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#00ff9f]/20 bg-[#00ff9f]/5">
                      <Cpu className="h-5 w-5 text-[#00ff9f]" />
                    </span>
                    <span className="text-[10px] font-semibold uppercase tracking-widest text-zinc-500">System</span>
                  </div>
                  <p className="mt-4 text-[11px] font-medium uppercase tracking-wider text-zinc-500">System health</p>
                  <div className="mt-5 space-y-4">
                    <GlowBar reduceMotion={reduceMotion} label="CPU" value={liveMetrics?.cpu ?? 0} color={ACCENT_CYAN} />
                    <GlowBar reduceMotion={reduceMotion} label="GPU" value={liveMetrics?.gpu ?? 0} color={ACCENT_GREEN} />
                    <GlowBar reduceMotion={reduceMotion} label="RAM" value={liveMetrics?.ram ?? 0} color={ACCENT_CYAN} />
                  </div>
                </MetricGlassCard>

                <MetricGlassCard
                  reduceMotion={reduceMotion}
                  delay={0.18}
                  tip="Training velocity — aggregates events per tijdseenheid zoals geleverd door de metrics-layer."
                  tipAriaLabel="Uitleg velocity"
                >
                  <div className="flex items-start justify-between gap-2 pr-8">
                    <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#00ff9f]/20 bg-[#00ff9f]/5">
                      <Gauge className="h-5 w-5 text-[#00ff9f]" />
                    </span>
                    <span className="text-[10px] font-semibold uppercase tracking-widest text-zinc-500">Throughput</span>
                  </div>
                  <p className="mt-4 text-[11px] font-medium uppercase tracking-wider text-zinc-500">Training velocity</p>
                  <p className="mt-2 text-3xl font-semibold text-white">
                    {hasTrainingTarget ? (
                      <>
                        <LiveStatNumber
                          value={liveMetrics?.velocity ?? 0}
                          decimals={1}
                          reduceMotion={reduceMotion}
                        />
                        <span className="ml-2 align-middle font-sans text-sm font-normal text-zinc-500">evt · s⁻¹</span>
                      </>
                    ) : (
                      <span className="font-mono text-zinc-500">—</span>
                    )}
                  </p>
                </MetricGlassCard>

                <MetricGlassCard
                  reduceMotion={reduceMotion}
                  delay={0.22}
                  tip={`Operationele mode afgeleid uit fase/synthetic/heuristic. Ruwe phase: "${phaseLabel}".`}
                  tipAriaLabel="Uitleg mode & phase"
                >
                  <div className="flex items-start justify-between gap-2 pr-8">
                    <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#00f0ff]/20 bg-[#00f0ff]/5">
                      <Radio className="h-5 w-5 text-[#00f0ff]" />
                    </span>
                    <span className="text-[10px] font-semibold uppercase tracking-widest text-zinc-500">Context</span>
                  </div>
                  <p className="mt-4 text-[11px] font-medium uppercase tracking-wider text-zinc-500">Current mode</p>
                  <p className="mt-2 line-clamp-2 text-xl font-semibold leading-snug text-white">{modeLabel}</p>
                  <div className="mt-6 border-t border-white/[0.06] pt-4">
                    <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-500">Phase</p>
                    <p className="mt-1 font-mono text-sm text-[#00ff9f]">{phaseLabel}</p>
                    <dl className="mt-5 grid grid-cols-2 gap-x-3 gap-y-3 text-[11px] text-zinc-500">
                      <div>
                        <dt>Historical days</dt>
                        <dd className="mt-1 font-mono text-zinc-200">
                          <LiveStatNumber value={liveMetrics?.historical_days ?? 0} reduceMotion={reduceMotion} />
                        </dd>
                      </div>
                      <div>
                        <dt>Synthetic blend</dt>
                        <dd className="mt-1 font-mono text-zinc-200">
                          {(liveMetrics?.synthetic_percent ?? 0).toFixed(1)}%
                        </dd>
                      </div>
                      <div className="col-span-2">
                        <dt>ETA (minuten)</dt>
                        <dd className="mt-1 font-mono text-zinc-200">
                          {liveMetrics == null
                            ? "—"
                            : liveMetrics.eta_minutes === null
                              ? "—"
                              : liveMetrics.eta_minutes.toLocaleString()}
                        </dd>
                      </div>
                      <div className="col-span-2">
                        <dt>First-boot stage</dt>
                        <dd className="mt-1 font-mono text-zinc-200">
                          {liveMetrics?.first_boot_stage?.trim() || "n/a"}
                        </dd>
                      </div>
                    </dl>
                  </div>
                </MetricGlassCard>
              </div>
            </section>
          </div>

          {/* right column activity */}
          <aside className="xl:sticky xl:top-[108px]">
            <motion.div
              initial={{ opacity: 0, x: reduceMotion ? 0 : 12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: reduceMotion ? 0 : 0.5 }}
              className="overflow-hidden rounded-3xl border border-[#00f0ff]/10 bg-black/65 shadow-[0_20px_60px_-30px_rgba(0,255,159,0.18)] backdrop-blur-xl"
            >
              <div className="border-b border-white/[0.06] px-5 py-4">
                <h3 className="flex items-center gap-2 font-semibold text-white">
                  <Activity className="h-5 w-5 text-[#00ff9f]" />
                  Live activity stream
                </h3>
                <p className="mt-1 text-[12px] text-zinc-500">
                  Gekleurde kern events - PROGRESS (neon groen), INFO (neon cyan), WARN (amber).
                </p>
              </div>
              <div
                ref={streamRef}
                aria-live="polite"
                className="h-[min(520px,calc(100vh-260px))] space-y-2 overflow-y-auto overscroll-contain px-4 py-4 font-mono text-[11px] leading-relaxed sm:px-5"
              >
                {stream.length === 0 ? (
                  <div className="rounded-xl border border-white/10 bg-white/[0.02] px-3 py-2 text-zinc-500">
                    Wachten op eerste telemetry event...
                  </div>
                ) : (
                  stream.map((row) => (
                    <motion.div
                      key={row.id}
                      layout={!reduceMotion}
                      initial={{ opacity: 0, x: reduceMotion ? 0 : 6 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: reduceMotion ? 0 : 0.22 }}
                      className={`flex gap-3 rounded-xl border px-3 py-2 backdrop-blur-sm ${
                        row.level === "INFO"
                          ? "border-[#00f0ff]/22 bg-[#00f0ff]/[0.045]"
                          : row.level === "PROGRESS"
                            ? "border-[#00ff9f]/22 bg-[#00ff9f]/[0.06]"
                            : "border-amber-500/30 bg-amber-500/[0.07]"
                      }`}
                    >
                      <span className="shrink-0 text-zinc-600">{new Date(row.ts).toLocaleTimeString()}</span>
                      <span
                        className={`shrink-0 font-bold uppercase tracking-[0.12em] ${
                          row.level === "INFO"
                            ? "text-[#00f0ff]"
                            : row.level === "PROGRESS"
                              ? "text-[#00ff9f]"
                              : "text-amber-400"
                        }`}
                      >
                        [{row.level}]
                      </span>
                      <span className="break-words text-zinc-300">{row.message}</span>
                    </motion.div>
                  ))
                )}
              </div>
            </motion.div>
          </aside>
        </div>

        {/* FAB */}
        <div className="pointer-events-none fixed bottom-6 right-4 z-40 flex flex-col items-end gap-3 sm:right-8">
          <motion.div
            className="pointer-events-auto flex flex-col gap-3"
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: reduceMotion ? 0 : 0.35, duration: reduceMotion ? 0 : 0.45 }}
          >
            <motion.button
              type="button"
              onClick={() => setPaused((p) => !p)}
              aria-pressed={paused}
              aria-label={paused ? "Polling hervatten" : "Polling pauzeren"}
              title={paused ? "Resume realtime polling" : "Pause realtime polling"}
              className="flex h-14 w-14 items-center justify-center rounded-full border border-[#00ff9f]/50 bg-black/85 text-[#00ff9f] shadow-[0_10px_40px_-12px_rgba(0,255,159,0.55)] backdrop-blur-md transition-colors hover:bg-[#00ff9f]/10"
              whileHover={reduceMotion ? undefined : { scale: 1.06 }}
              whileTap={reduceMotion ? undefined : { scale: 0.93 }}
            >
              {paused ? <Play className="h-6 w-6" /> : <Pause className="h-6 w-6" />}
            </motion.button>
            <motion.button
              type="button"
              onClick={() => exportMonitoringReport(liveMetrics ?? null, { paused, lastUpdatedAt })}
              aria-label="Rapport exporteren(JSON)"
              title="Export rapport"
              className="flex h-14 w-14 items-center justify-center rounded-full border border-[#00f0ff]/50 bg-black/85 text-[#00f0ff] shadow-[0_10px_40px_-12px_rgba(0,240,255,0.48)] backdrop-blur-md hover:bg-[#00f0ff]/10"
              whileHover={reduceMotion ? undefined : { scale: 1.06 }}
              whileTap={reduceMotion ? undefined : { scale: 0.93 }}
            >
              <Download className="h-6 w-6" />
            </motion.button>
          </motion.div>
        </div>
      </main>
    </div>
  );
}
