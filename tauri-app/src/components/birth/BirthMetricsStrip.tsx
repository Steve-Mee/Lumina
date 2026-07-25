import type { BirthProgressPayload, TwinObservabilityPayload } from "@/lib/birthClient";
import {
  extractBirthSessionHud,
  extractPpoProgress,
  extractSimProgress,
  extractStageScorecard,
} from "@/lib/birthPhaseModel";
import { formatTwinPct } from "@/lib/twinClient";
import { cn } from "@/lib/utils";

import { BirthFieldCard } from "@/components/birth/BirthFieldCard";
import { BirthSessionTelemetry } from "@/components/birth/BirthSessionTelemetry";
import { useLiveBirthElapsedSec } from "@/hooks/useLiveBirthElapsedSec";

interface BirthMetricsStripProps {
  progress: BirthProgressPayload | undefined;
  elapsedSeconds?: number;
  message?: string;
  embedded?: boolean;
  twinObservability?: TwinObservabilityPayload | null;
  className?: string;
}

function formatTwinAgree(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v))) return "—";
  return formatTwinPct(Number(v));
}

function MetricField({
  label,
  value,
  detail,
  barPct,
}: {
  label: string;
  value: string;
  detail?: string;
  barPct: number;
}) {
  const pct = Math.min(100, Math.max(0, barPct));
  return (
    <div className="risk-envelope-field-card birth-metric-field space-y-1">
      <div className="flex items-baseline justify-between gap-2">
        <p className="risk-envelope-field-label mb-0 truncate">{label}</p>
        <p className="shrink-0 font-mono text-[11px] tabular-nums text-cyan-100">{value}</p>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/8">
        <div
          className="birth-metric-bar-fill h-full rounded-full bg-gradient-to-r from-cyan-500/80 to-violet-400/80 transition-[width] duration-500 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
      {detail ? (
        <p className="risk-envelope-field-hint mb-0 truncate" title={detail}>
          {detail}
        </p>
      ) : null}
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
  const value = `${(scorecard.metricValue * 100).toFixed(1)}%`;
  if (scorecard.passCriteriaId === "range_hold_ratio" || scorecard.passCriteriaId === "range_roundtrip") {
    const min = scorecard.metricMin != null ? (scorecard.metricMin * 100).toFixed(0) : "30";
    const max = scorecard.metricMax != null ? (scorecard.metricMax * 100).toFixed(0) : "70";
    return `${value} (target ${min}–${max}%)`;
  }
  if (scorecard.passCriteriaId === "mixed_foundation") {
    const need =
      scorecard.metricTarget != null
        ? `pass if ≥${(scorecard.metricTarget * 100).toFixed(0)}% (all trades)`
        : "pass if ≥35% (all trades)";
    return `${value} · ${need}`;
  }
  if (scorecard.metricTarget != null) {
    return `${value} → need ${(scorecard.metricTarget * 100).toFixed(0)}%`;
  }
  return value;
}

function formatPassMetricValue(
  scorecard: NonNullable<ReturnType<typeof extractStageScorecard>>,
): string {
  if (scorecard.metricValue == null) {
    return scorecard.tradesDone > 0 ? "syncing…" : "—";
  }
  if (scorecard.passCriteriaId === "mixed_constitution") {
    return String(Math.round(scorecard.metricValue));
  }
  return `${(scorecard.metricValue * 100).toFixed(1)}%`;
}

function formatHoldDetail(
  scorecard: NonNullable<ReturnType<typeof extractStageScorecard>>,
): string {
  if (scorecard.stageHoldRatio == null) return "—";
  const pct = (scorecard.stageHoldRatio * 100).toFixed(1);
  const max =
    scorecard.stageHoldMax != null
      ? (scorecard.stageHoldMax * 100).toFixed(0)
      : "70";
  const ok = scorecard.stageHoldRatio <= (scorecard.stageHoldMax ?? 0.7);
  return `${pct}% · need ≤${max}%${ok ? " ✓" : ""}`;
}

function formatRollingDetail(
  scorecard: NonNullable<ReturnType<typeof extractStageScorecard>>,
): string {
  if (scorecard.rollingWinrate500 == null) return "—";
  const pct = (scorecard.rollingWinrate500 * 100).toFixed(1);
  const floor =
    scorecard.metricTarget != null
      ? (scorecard.metricTarget * 100).toFixed(0)
      : "35";
  const source = String(scorecard.rollingWinrateSource ?? "").toLowerCase();
  if (source === "lifetime_fallback" || source === "") {
    const covered = scorecard.rollingWindowTradesCovered;
    if (covered != null && covered > 0 && covered < 200) {
      return `${pct}% · ≈ lifetime (building last-500 · ${covered} known)`;
    }
    return `${pct}% · ≈ lifetime (window building)`;
  }
  if (source === "partial_window") {
    const covered = scorecard.rollingWindowTradesCovered ?? 0;
    return `${pct}% · partial last ${covered} · OF ≥${floor}%`;
  }
  return `${pct}% · OF last 500 ≥${floor}%`;
}

export function BirthMetricsStrip({
  progress,
  elapsedSeconds,
  message,
  embedded = false,
  twinObservability = null,
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

  const tradeDetail =
    sim.target > 0
      ? `${sim.done.toLocaleString()} / ${sim.target.toLocaleString()}`
      : `${sim.done.toLocaleString()} trades`;

  return (
    <div
      className={cn(
        "birth-metrics-strip",
        embedded
          ? "birth-metrics-strip--embedded birth-intel-field-grid"
          : "space-y-2",
        className,
      )}
    >
      {loadingHistory ? (
        <>
          <MetricField
            label="Historical data load"
            value={`${historyPct.toFixed(0)}%`}
            detail={
              loadingTotal > 0 && loadingChunk > 0
                ? `Chunk ${loadingChunk}/${loadingTotal} · ${Number(progress?.bars_loaded ?? 0).toLocaleString()} bars`
                : `${overallPct.toFixed(1)}% overall`
            }
            barPct={historyPct}
          />
          {!embedded ? (
            <MetricField
              label="Overall progress"
              value={`${overallPct.toFixed(1)}%`}
              barPct={overallPct}
            />
          ) : null}
        </>
      ) : enrichingRegimes ? (
        <>
          <MetricField
            label="Regime map"
            value={`${regimePct.toFixed(0)}%`}
            detail={
              loadingTotal > 0 && loadingChunk > 0
                ? `${loadingChunk.toLocaleString()}/${loadingTotal.toLocaleString()} ticks`
                : `${overallPct.toFixed(1)}% overall`
            }
            barPct={regimePct}
          />
          {!embedded ? (
            <MetricField
              label="Overall progress"
              value={`${overallPct.toFixed(1)}%`}
              barPct={overallPct}
            />
          ) : null}
        </>
      ) : embedded &&
        showPpoBatch &&
        ppo.steps > 0 &&
        scorecard?.passCriteriaId !== "mixed_foundation" ? (
        <MetricField label="PPO batch" value={ppo.label} barPct={overallPct} />
      ) : (
        <MetricField
          label={scorecard ? "Stage trades" : "Simulation trades"}
          value={tradeDetail}
          barPct={sim.pct}
        />
      )}
      {/* Raptor v11: stage3 foundation metrics also in Mission Control (embedded). */}
      {scorecard && scorecard.passCriteriaId !== "polish_complete" ? (
        <MetricField
          label={scorecard.metricLabel}
          value={formatPassMetricValue(scorecard)}
          detail={formatPassMetricDetail(scorecard)}
          barPct={scorecard.metricPct}
        />
      ) : null}
      {scorecard && scorecard.passCriteriaId === "mixed_foundation" ? (
        <>
          <MetricField
            label="Hold ratio"
            value={
              scorecard.stageHoldRatio != null
                ? `${(scorecard.stageHoldRatio * 100).toFixed(1)}%`
                : "—"
            }
            detail={formatHoldDetail(scorecard)}
            barPct={
              scorecard.stageHoldRatio != null
                ? Math.min(100, Math.max(0, scorecard.stageHoldRatio * 100))
                : 0
            }
          />
          <MetricField
            label="Rolling winrate (500)"
            value={
              scorecard.rollingWinrate500 != null
                ? `${(scorecard.rollingWinrate500 * 100).toFixed(1)}%`
                : "—"
            }
            detail={formatRollingDetail(scorecard)}
            barPct={
              scorecard.rollingWinrate500 != null
                ? Math.min(100, Math.max(0, scorecard.rollingWinrate500 * 100))
                : 0
            }
          />
        </>
      ) : null}
      {!embedded && showPpoBatch && ppo.steps > 0 ? (
        <MetricField label="PPO batch" value={ppo.label} barPct={overallPct} />
      ) : !embedded && !scorecard && ppo.steps > 0 ? (
        <MetricField label="PPO refinement" value={ppo.label} barPct={overallPct} />
      ) : !embedded && !loadingHistory && !enrichingRegimes && !scorecard ? (
        <MetricField
          label="Overall progress"
          value={`${overallPct.toFixed(1)}%`}
          barPct={overallPct}
        />
      ) : null}
      {sessionHud ? (
        <BirthSessionTelemetry
          hud={sessionHud}
          elapsedSec={liveElapsedSec}
          embeddedGrid={embedded}
        />
      ) : elapsedLabel ? (
        <BirthFieldCard label="Elapsed" value={elapsedLabel} />
      ) : null}
      {twinObservability ? (
        <BirthFieldCard
          label="Twin"
          tip="Approval Twin observability (judgment layer — never bypasses capital gates)"
          value={`mode ${String(twinObservability.mode ?? "shadow")}`}
          hint={[
            `Steve ${formatTwinAgree(twinObservability.twin_steve_agreement_pct ?? twinObservability.twin_agreement_pct)}`,
            `roll w50 ${formatTwinAgree(twinObservability.rolling_agreement_w50)}`,
            `risk ${twinObservability.risk_flags_caught ?? 0}c/${twinObservability.risk_flags_missed ?? 0}m`,
            twinObservability.mode_promotion_progress
              ? `assisted ${twinObservability.mode_promotion_progress.assisted_ready ? "ready" : "gated"} · full_auto ${twinObservability.mode_promotion_progress.full_auto_ready ? "ready" : "gated"}`
              : null,
          ]
            .filter(Boolean)
            .join(" · ")}
          className="birth-intel-field-span"
        />
      ) : null}
      {message ? (
        <BirthFieldCard label="Status" className="birth-intel-field-span birth-status-line">
          <p className="truncate font-mono text-sm text-cyan-100" title={message}>
            {message}
          </p>
        </BirthFieldCard>
      ) : null}
    </div>
  );
}
