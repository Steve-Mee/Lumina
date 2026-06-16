import type { BirthProgressPayload } from "@/lib/birthClient";
import {
  extractStageScorecard,
  type StageScorecardModel,
} from "@/lib/birthPhaseModel";
import { cn } from "@/lib/utils";

interface BirthStageScorecardProps {
  progress: BirthProgressPayload | undefined;
  variant?: "default" | "compact";
  className?: string;
}

function formatMetricValue(model: StageScorecardModel): string {
  if (model.metricValue == null) {
    if (model.passCriteriaId === "trend_winrate" && model.tradesDone > 0) {
      return "syncing…";
    }
    return "—";
  }
  if (model.passCriteriaId === "mixed_constitution") {
    return String(Math.round(model.metricValue));
  }
  return `${(model.metricValue * 100).toFixed(0)}%`;
}

function formatMetricTarget(model: StageScorecardModel): string {
  if (model.passCriteriaId === "mixed_constitution") {
    return "need 0";
  }
  if (model.passCriteriaId === "range_hold_ratio" || model.passCriteriaId === "range_roundtrip") {
    const min = model.metricMin != null ? (model.metricMin * 100).toFixed(0) : "30";
    const max = model.metricMax != null ? (model.metricMax * 100).toFixed(0) : "70";
    return `target ${min}–${max}%`;
  }
  if (model.metricTarget != null) {
    return `need ${(model.metricTarget * 100).toFixed(0)}%`;
  }
  return "";
}

function healthClass(health: StageScorecardModel["health"]): string {
  if (health === "advancing") return "text-emerald-300";
  if (health === "stale") return "text-amber-300";
  return "text-cyan-200/80";
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
    <div className="space-y-1">
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="font-mono text-[10px] tracking-wide text-muted-foreground uppercase">
          {label}
        </span>
        <span className="font-mono text-[11px] text-cyan-200/90">{detail}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/8">
        <div
          className="h-full rounded-full bg-gradient-to-r from-cyan-500/80 to-violet-400/80 transition-[width] duration-500 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function BirthStageScorecard({
  progress,
  variant = "default",
  className,
}: BirthStageScorecardProps) {
  const scorecard = extractStageScorecard(progress);
  if (!scorecard) return null;

  const compact = variant === "compact";
  const metricDetail = `${formatMetricValue(scorecard)} ${formatMetricTarget(scorecard)}`.trim();
  const heartbeatLabel =
    scorecard.heartbeatSec != null
      ? `Updated ${scorecard.heartbeatSec}s ago`
      : "Awaiting update";

  if (compact) {
    return (
      <p
        className={cn(
          "birth-stage-scorecard-compact font-mono text-[11px] text-cyan-200/85",
          className,
        )}
      >
        {scorecard.stageLabel} · {scorecard.tradesDone}/{scorecard.tradesRequired} trades
        {scorecard.metricValue != null ? ` · ${scorecard.metricLabel} ${formatMetricValue(scorecard)}` : ""}
        {scorecard.learningAttempt > 0 ? ` · attempt ${scorecard.learningAttempt}` : ""}
        {scorecard.explorationActive ? " · explore" : ""}
        {scorecard.stageWallRemainingSec != null
          ? ` · wall ${Math.ceil(scorecard.stageWallRemainingSec / 60)}m`
          : ""}
      </p>
    );
  }

  return (
    <div
      className={cn(
        "birth-stage-scorecard space-y-3 rounded-lg border border-cyan-500/20 bg-cyan-950/10 p-3",
        className,
      )}
    >
      <div className="space-y-0.5">
        <p className="font-mono text-xs font-medium tracking-wide text-foreground">
          {scorecard.stageLabel}
        </p>
        <p className="font-mono text-[10px] text-muted-foreground">
          Goal: {scorecard.goalLabel}
        </p>
      </div>

      <ProgressBar
        label="Stage trades"
        value={scorecard.tradesPct}
        detail={
          scorecard.tradesRequired > 0
            ? `${scorecard.tradesDone.toLocaleString()} / ${scorecard.tradesRequired.toLocaleString()}`
            : `${scorecard.tradesDone.toLocaleString()}`
        }
      />

      {scorecard.passCriteriaId !== "polish_complete" ? (
        <ProgressBar
          label={scorecard.metricLabel}
          value={scorecard.metricPct}
          detail={metricDetail}
        />
      ) : null}

      {(scorecard.passCriteriaId === "range_hold_ratio" ||
        scorecard.passCriteriaId === "range_roundtrip") ? (
        <p className="font-mono text-[10px] text-muted-foreground">
          {scorecard.passCriteriaId === "range_roundtrip" ? "Position flat band" : "Range hold band"}:{" "}
          {scorecard.metricMin != null ? `${(scorecard.metricMin * 100).toFixed(0)}%` : "30%"}
          {" – "}
          {scorecard.metricMax != null ? `${(scorecard.metricMax * 100).toFixed(0)}%` : "70%"}
          {scorecard.passCriteriaId === "range_roundtrip" &&
          scorecard.stageRangeRoundTrips != null
            ? ` · round trips ${scorecard.stageRangeRoundTrips.toLocaleString()}`
            : ""}
        </p>
      ) : null}

      <div className="space-y-1 font-mono text-[10px] text-muted-foreground">
        <p>
          Sub-phase: {scorecard.subPhaseLabel}
          {scorecard.learningAttempt > 0 ? ` · attempt ${scorecard.learningAttempt}` : ""}
          {scorecard.explorationActive ? " · exploration" : ""}
          {scorecard.stageWallRemainingSec != null
            ? ` · wall ${Math.ceil(scorecard.stageWallRemainingSec / 60)}m left`
            : ""}
        </p>
        {scorecard.patternsMined > 0 ? (
          <p>Patterns: {scorecard.patternsMined.toLocaleString()} mined</p>
        ) : null}
        <p className={healthClass(scorecard.health)}>
          {heartbeatLabel} · {scorecard.healthHint}
        </p>
      </div>
    </div>
  );
}
