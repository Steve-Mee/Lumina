import type { BirthProgressPayload } from "@/lib/birthClient";
import {
  extractBirthSessionHud,
  extractPpoProgress,
  extractSimProgress,
  extractStageScorecard,
} from "@/lib/birthPhaseModel";
import { cn } from "@/lib/utils";

import { BirthSessionTelemetry } from "@/components/birth/BirthSessionTelemetry";
import { useLiveBirthElapsedSec } from "@/hooks/useLiveBirthElapsedSec";

interface BirthMetricsStripProps {
  progress: BirthProgressPayload | undefined;
  elapsedSeconds?: number;
  message?: string;
  embedded?: boolean;
  className?: string;
}

function ProgressBar({
  label,
  value,
  detail,
}: {
  label: string;
  value: number;
  detail: string;
}) {
  const pct = Math.min(100, Math.max(0, value));
  return (
    <div className="birth-metric-bar space-y-1.5">
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="font-mono text-[10px] tracking-wide text-muted-foreground uppercase">
          {label}
        </span>
        <span className="font-mono text-[11px] text-cyan-200/90">{detail}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/8">
        <div
          className="birth-metric-bar-fill h-full rounded-full bg-gradient-to-r from-cyan-500/80 to-violet-400/80 transition-[width] duration-500 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function formatPassMetricDetail(
  scorecard: NonNullable<ReturnType<typeof extractStageScorecard>>,
): string {
  if (scorecard.metricValue == null) {
    if (scorecard.passCriteriaId === "trend_winrate" && scorecard.tradesDone > 0) {
      return "syncing after next rollout or backend restart";
    }
    return "—";
  }
  if (scorecard.passCriteriaId === "mixed_constitution") {
    return `${Math.round(scorecard.metricValue)} violations`;
  }
  const value = `${(scorecard.metricValue * 100).toFixed(0)}%`;
  if (scorecard.passCriteriaId === "range_hold_ratio" || scorecard.passCriteriaId === "range_roundtrip") {
    const min = scorecard.metricMin != null ? (scorecard.metricMin * 100).toFixed(0) : "30";
    const max = scorecard.metricMax != null ? (scorecard.metricMax * 100).toFixed(0) : "70";
    return `${value} (target ${min}–${max}%)`;
  }
  if (scorecard.metricTarget != null) {
    return `${value} → need ${(scorecard.metricTarget * 100).toFixed(0)}%`;
  }
  return value;
}

export function BirthMetricsStrip({
  progress,
  elapsedSeconds,
  message,
  embedded = false,
  className,
}: BirthMetricsStripProps) {
  const sim = extractSimProgress(progress);
  const ppo = extractPpoProgress(progress);
  const scorecard = extractStageScorecard(progress);
  const sessionHud = extractBirthSessionHud(progress);
  const liveElapsedSec = useLiveBirthElapsedSec(progress, elapsedSeconds);
  const overallPct = Number(progress?.progress_pct ?? sim.pct);
  const subPhase = String(progress?.sub_phase ?? progress?.phase ?? "").toLowerCase();
  const loadingHistory = subPhase === "loading_history";
  const enrichingRegimes = subPhase === "enriching_regimes";
  const loadingChunk = Number(progress?.loading_chunk ?? 0);
  const loadingTotal = Number(progress?.chunk_total ?? 0);
  const historyPct =
    loadingHistory && loadingTotal > 0
      ? Math.min(100, Math.max(0, (loadingChunk / loadingTotal) * 100))
      : overallPct;
  const regimePct =
    enrichingRegimes && loadingTotal > 0
      ? Math.min(100, Math.max(0, (loadingChunk / loadingTotal) * 100))
      : overallPct;
  const showPpoBatch =
    subPhase === "ppo_training" ||
    subPhase === "curriculum_learning" ||
    subPhase === "curriculum_research";

  const elapsedLabel =
    liveElapsedSec != null && liveElapsedSec >= 0
      ? `${Math.floor(liveElapsedSec / 60)}m ${Math.floor(liveElapsedSec % 60)}s`
      : null;

  return (
    <div
      className={cn(
        "birth-metrics-strip rounded-lg border border-white/8",
        embedded ? "birth-metrics-strip--embedded space-y-2 p-2" : "space-y-4 p-3",
        className,
      )}
    >
      {loadingHistory ? (
        <>
          <ProgressBar
            label="Historical data load"
            value={historyPct}
            detail={
              loadingTotal > 0 && loadingChunk > 0
                ? `Chunk ${loadingChunk}/${loadingTotal} · ${Number(progress?.bars_loaded ?? 0).toLocaleString()} bars`
                : `${overallPct.toFixed(1)}% overall`
            }
          />
          {!embedded ? (
            <ProgressBar
              label="Overall progress"
              value={overallPct}
              detail={`${overallPct.toFixed(1)}%`}
            />
          ) : null}
        </>
      ) : enrichingRegimes ? (
        <>
          <ProgressBar
            label="Regime map"
            value={regimePct}
            detail={
              loadingTotal > 0 && loadingChunk > 0
                ? `${loadingChunk.toLocaleString()}/${loadingTotal.toLocaleString()} ticks`
                : `${overallPct.toFixed(1)}% overall`
            }
          />
          {!embedded ? (
            <ProgressBar
              label="Overall progress"
              value={overallPct}
              detail={`${overallPct.toFixed(1)}%`}
            />
          ) : null}
        </>
      ) : embedded && showPpoBatch && ppo.steps > 0 ? (
        <ProgressBar label="PPO batch" value={overallPct} detail={ppo.label} />
      ) : (
      <ProgressBar
        label={scorecard ? "Stage trades" : "Simulation trades"}
        value={sim.pct}
        detail={
          sim.target > 0
            ? `${sim.done.toLocaleString()} / ${sim.target.toLocaleString()}`
            : `${sim.done.toLocaleString()} trades`
        }
      />
      )}
      {!embedded && scorecard && scorecard.passCriteriaId !== "polish_complete" ? (
        <ProgressBar
          label={scorecard.metricLabel}
          value={scorecard.metricPct}
          detail={formatPassMetricDetail(scorecard)}
        />
      ) : null}
      {!embedded && showPpoBatch && ppo.steps > 0 ? (
        <ProgressBar label="PPO batch" value={overallPct} detail={ppo.label} />
      ) : !embedded && !scorecard && ppo.steps > 0 ? (
        <ProgressBar label="PPO refinement" value={overallPct} detail={ppo.label} />
      ) : !embedded && !loadingHistory && !enrichingRegimes && !scorecard ? (
        <ProgressBar
          label="Overall progress"
          value={overallPct}
          detail={`${overallPct.toFixed(1)}%`}
        />
      ) : null}
      {sessionHud ? (
        <BirthSessionTelemetry hud={sessionHud} elapsedSec={liveElapsedSec} className="px-0.5" />
      ) : elapsedLabel ? (
        <div className="font-mono text-[10px] text-muted-foreground">
          Elapsed {elapsedLabel}
        </div>
      ) : null}
      {message ? (
        <div className="birth-status-line font-mono text-[10px] text-muted-foreground">
          <span className="block truncate text-right text-cyan-200/70" title={message}>
            {message}
          </span>
        </div>
      ) : null}
    </div>
  );
}
