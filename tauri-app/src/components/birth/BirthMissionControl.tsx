import type { BirthProgressPayload, BirthStatusPayload } from "@/lib/birthClient";
import type { BirthMilestone } from "@/lib/birthPhaseModel";
import { extractBirthSessionHud, extractStageScorecard } from "@/lib/birthPhaseModel";
import { cn } from "@/lib/utils";

import { BirthCompletionSummary } from "@/components/birth/BirthCompletionSummary";
import { BirthControlDock } from "@/components/birth/BirthControlDock";
import { BirthKpiTile } from "@/components/birth/BirthKpiTile";
import { BirthMetricsStrip } from "@/components/birth/BirthMetricsStrip";

interface BirthMissionControlProps {
  headline: string;
  subtitle: string;
  milestones: BirthMilestone[];
  progress?: BirthProgressPayload;
  status?: BirthStatusPayload | null;
  elapsedSeconds?: number;
  progressMessage?: string;
  finale?: boolean;
  running?: boolean;
  /** Show Stop birth in the panel toolbar (natural home for stop during training). */
  showStopControl?: boolean;
  controlBusy?: boolean;
  className?: string;
}

type ChipState = "ok" | "partial" | "warn" | "idle";

function formatMetricValue(scorecard: NonNullable<ReturnType<typeof extractStageScorecard>>): string {
  if (scorecard.metricValue == null) {
    return scorecard.tradesDone > 0 ? "syncing…" : "—";
  }
  if (scorecard.passCriteriaId === "mixed_constitution") {
    return String(Math.round(scorecard.metricValue));
  }
  return `${(scorecard.metricValue * 100).toFixed(0)}%`;
}

function formatMetricTarget(scorecard: NonNullable<ReturnType<typeof extractStageScorecard>>): string {
  if (scorecard.metricTarget != null) {
    return `need ${(scorecard.metricTarget * 100).toFixed(0)}%`;
  }
  return scorecard.goalLabel;
}

function resolveOverallPhaseLabel(progress: BirthProgressPayload | undefined): string {
  const phase = String(progress?.phase ?? "").trim().toLowerCase();
  if (phase === "loading_history") return "Data load";
  if (phase === "enriching_news" || phase === "enriching_regimes") return "Regime map";
  if (phase === "train_holdout_split" || phase === "holdout_preflight" || phase === "holdout_preflight_expansion") {
    return "Preflight";
  }
  if (phase === "policy_init" || phase === "ticks_ready") return "Policy init";
  if (phase.includes("curriculum") || phase.includes("simulation") || phase === "ppo_training") {
    return "Curriculum";
  }
  if (phase === "ppo_polish" || phase === "oos_evaluation") return "Polish / OOS";
  if (phase === "completed" || phase === "practice_completed" || phase === "certificate_issued") {
    return "Birth complete";
  }
  return "Birth progress";
}

function StatusChip({
  label,
  state,
  tip,
}: {
  label: string;
  state: ChipState;
  tip: string;
}) {
  return (
    <span
      className="risk-envelope-status-chip"
      data-state={state === "idle" ? undefined : state}
      title={tip}
    >
      <span className="risk-envelope-status-chip__dot" />
      {label}
    </span>
  );
}

function resolveMissionChips(progress: BirthProgressPayload | undefined): {
  history: ChipState;
  regime: ChipState;
  policy: ChipState;
  lanes: ChipState;
  tips: Record<"history" | "regime" | "policy" | "lanes", string>;
} {
  const phase = String(progress?.phase ?? "").trim().toLowerCase();
  const realPct = Number(progress?.real_data_pct ?? NaN);
  const synthetic = Boolean(progress?.synthetic_top_up ?? progress?.synthetic_ticks);
  const message = String(progress?.message ?? "").toLowerCase();

  let history: ChipState = "idle";
  let regime: ChipState = "idle";
  let policy: ChipState = "idle";
  let lanes: ChipState = "idle";

  if (phase === "loading_history" || phase === "loading_history_failed") {
    history = phase === "loading_history_failed" ? "warn" : "partial";
  } else if (phase) {
    history = "ok";
  }

  if (phase === "enriching_news" || phase === "enriching_regimes") {
    regime = "partial";
    history = "ok";
  } else if (
    phase === "train_holdout_split" ||
    phase === "holdout_preflight" ||
    phase === "holdout_preflight_expansion" ||
    phase === "policy_init" ||
    phase === "ticks_ready" ||
    phase.includes("curriculum") ||
    phase.includes("simulation") ||
    phase === "ppo_training" ||
    phase === "ppo_polish" ||
    phase === "oos_evaluation" ||
    phase.includes("certificate") ||
    phase === "completed" ||
    phase === "practice_completed"
  ) {
    regime = "ok";
    history = "ok";
  }

  if (phase === "policy_init") {
    policy = "partial";
  } else if (
    phase === "ticks_ready" ||
    phase.includes("curriculum") ||
    phase.includes("simulation") ||
    phase === "ppo_training" ||
    phase === "ppo_polish" ||
    phase === "oos_evaluation" ||
    phase.includes("certificate") ||
    phase === "completed" ||
    phase === "practice_completed"
  ) {
    policy = "ok";
  }

  if (Number.isFinite(realPct) && realPct >= 99) {
    lanes = synthetic || message.includes("synthetic") ? "partial" : "ok";
  } else if (Number.isFinite(realPct) && realPct > 0) {
    lanes = "partial";
  } else if (phase === "enriching_regimes" || phase === "loading_history" || message.includes("synthetic")) {
    lanes = "partial";
  } else if (regime === "ok" || policy === "ok") {
    lanes = "ok";
  }

  const realLabel = Number.isFinite(realPct) ? `${realPct.toFixed(0)}% real` : "lanes merging";
  return {
    history,
    regime,
    policy,
    lanes,
    tips: {
      history:
        history === "ok"
          ? "Historical market data loaded."
          : history === "partial"
            ? "Loading real market history…"
            : history === "warn"
              ? "History load failed — check Crosstrade / NT data path."
              : "History not started.",
      regime:
        regime === "ok"
          ? "Regime map ready."
          : regime === "partial"
            ? "Building regime map — historical and synthetic lanes merging."
            : "Regime map pending.",
      policy:
        policy === "ok"
          ? "Birth policy minted."
          : policy === "partial"
            ? "Initializing birth PPO policy…"
            : "Policy init not started.",
      lanes:
        lanes === "ok"
          ? `Data lanes ready (${realLabel}).`
          : lanes === "partial"
            ? `Historical / synthetic merge in progress (${realLabel}).`
            : "Data lanes idle.",
    },
  };
}

export function BirthMissionControl({
  subtitle,
  milestones: _milestones,
  progress,
  status = null,
  elapsedSeconds,
  progressMessage,
  finale = false,
  running = false,
  showStopControl = false,
  controlBusy = false,
  className,
}: BirthMissionControlProps) {
  const scorecard = extractStageScorecard(progress);
  const sessionHud = extractBirthSessionHud(progress);
  const overallPct = Number(progress?.progress_pct ?? 0);
  const phaseLabel = finale ? "Birth complete" : resolveOverallPhaseLabel(progress);
  const phaseToken = String(progress?.phase ?? "").trim() || "—";
  const stageToken = String(progress?.stage ?? "").trim() || "—";
  const chips = resolveMissionChips(progress);

  const wallMinutes =
    scorecard?.stageWallRemainingSec != null
      ? Math.ceil(scorecard.stageWallRemainingSec / 60)
      : null;

  const metricTone =
    scorecard?.blockerDetail != null
      ? "warn"
      : scorecard?.metricValue != null &&
          scorecard.metricTarget != null &&
          scorecard.metricValue >= scorecard.metricTarget
        ? "success"
        : "accent";

  return (
    <section
      className={cn(
        "birth-mission-control lumina-glass lumina-glass--overlay flex h-full min-h-0 flex-col overflow-hidden",
        className,
      )}
      aria-label="Birth mission control"
    >
      <header className="birth-mission-control__toolbar risk-envelope-panel__toolbar shrink-0">
        <div className="min-w-0">
          <p className="birth-mission-control__toolbar-title risk-envelope-panel__toolbar-title">
            {phaseLabel}
          </p>
          <p className="mt-0.5 font-mono text-[0.5rem] tracking-wide text-white/30 uppercase">
            {stageToken} · {phaseToken}
          </p>
        </div>
        <div className="birth-mission-control__toolbar-actions shrink-0">
          {showStopControl && running && !finale ? (
            <div className="birth-mission-control__stop-stack">
              <span className="birth-mission-control__progress-pct font-mono text-[0.55rem] tabular-nums tracking-wide text-cyan-200/80">
                {overallPct.toFixed(1)}%
              </span>
              <BirthControlDock
                mode="running"
                busy={controlBusy}
                inline
                className="birth-control-dock--panel border-0 bg-transparent p-0 shadow-none backdrop-blur-none"
              />
            </div>
          ) : running || finale ? (
            <span className="birth-mission-control__progress-pct font-mono text-[0.55rem] tabular-nums tracking-wide text-cyan-200/80">
              {overallPct.toFixed(1)}%
            </span>
          ) : null}
        </div>
      </header>

      {!finale ? (
        <div
          className="birth-mission-status-strip risk-envelope-status-strip shrink-0"
          role="status"
          aria-label="Birth lane status"
        >
          <StatusChip label="HISTORY" state={chips.history} tip={chips.tips.history} />
          <StatusChip label="REGIME" state={chips.regime} tip={chips.tips.regime} />
          <StatusChip label="POLICY" state={chips.policy} tip={chips.tips.policy} />
          <StatusChip label="LANES" state={chips.lanes} tip={chips.tips.lanes} />
        </div>
      ) : null}

      <div className="birth-mission-control__body min-h-0 flex-1 overflow-x-hidden overflow-y-auto">
        <div className="flex flex-col gap-1.5 px-2.5 py-1.5">
          {finale && status ? <BirthCompletionSummary status={status} /> : null}

          {subtitle ? (
            <p
              className="birth-mission-control__status-line birth-phase-subtitle shrink-0 text-left text-[11px] leading-snug text-white/55"
              title={subtitle}
            >
              {subtitle}
            </p>
          ) : null}

          <div className="birth-kpi-grid birth-intel-field-grid shrink-0">
            <BirthKpiTile
              label="Overall"
              value={`${overallPct.toFixed(1)}%`}
              detail={phaseLabel}
              tone="accent"
            />
            <BirthKpiTile
              label={scorecard ? "Stage trades" : "Trades"}
              value={
                scorecard
                  ? `${scorecard.tradesDone.toLocaleString()}`
                  : String(progress?.cumulative_trades ?? 0)
              }
              detail={
                scorecard && scorecard.tradesRequired > 0
                  ? `/ ${scorecard.tradesRequired.toLocaleString()} required`
                  : undefined
              }
            />
            <BirthKpiTile
              label={scorecard?.metricLabel ?? "Pass metric"}
              value={scorecard ? formatMetricValue(scorecard) : "—"}
              detail={scorecard ? formatMetricTarget(scorecard) : undefined}
              tone={metricTone as "default" | "success" | "warn" | "accent"}
            />
            <BirthKpiTile
              label="Stage wall"
              value={wallMinutes != null ? `${wallMinutes}m` : "—"}
              detail={
                scorecard?.learningAttempt
                  ? `attempt ${scorecard.learningAttempt}`
                  : sessionHud?.learningAttempt
                    ? `attempt ${sessionHud.learningAttempt}`
                    : scorecard?.subPhaseLabel ?? sessionHud?.subPhaseLabel
              }
              tone={wallMinutes != null && wallMinutes < 30 ? "warn" : "default"}
            />
          </div>

          {(running || finale) && progress ? (
            <div className="birth-mission-metrics-card birth-section-card shrink-0 space-y-1.5">
              <p className="font-mono text-[0.55rem] tracking-[0.14em] text-cyan-200/80 uppercase">
                Fitness landscape
              </p>
              <BirthMetricsStrip
                progress={progress}
                elapsedSeconds={elapsedSeconds}
                message={progressMessage}
                twinObservability={status?.twin_observability ?? null}
                embedded
              />
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
