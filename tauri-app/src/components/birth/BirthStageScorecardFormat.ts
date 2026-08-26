/** Pure format helpers for BirthStageScorecard (Tauri UI god split). */
import {
  formatBirthMetricTarget,
  formatBirthMetricValue,
} from "@/lib/birth/birthMetricFormat";
import { isStageGoalMet } from "@/lib/birth/birthStageScorecard";
import type { StageScorecardModel } from "@/lib/birthPhaseModel";
import {
  resolveBooleanConditionTone,
  resolveConditionTone,
  type ConditionTone,
} from "@/lib/conditionTone";

export function formatMetricValue(model: StageScorecardModel): string {
  return formatBirthMetricValue(model);
}

export function formatMetricTarget(model: StageScorecardModel): string {
  return formatBirthMetricTarget(model);
}

export function formatTrendSlope(slope: number | null): string {
  if (slope == null) return "—";
  if (Math.abs(slope) < 0.0001) return "flat";
  const pct = (slope * 100).toFixed(2);
  return slope > 0 ? `+${pct}%/step` : `${pct}%/step`;
}

export function showAdaptationHud(scorecard: StageScorecardModel): boolean {
  return (
    scorecard.adaptationEnabled &&
    scorecard.wallBehavior === "adaptive" &&
    (scorecard.volumeGateStatus != null ||
      scorecard.retriesThisStage > 0 ||
      scorecard.lastAdaptationSummary != null)
  );
}

export function formatDataWindow(scorecard: StageScorecardModel): string {
  if (scorecard.dataDaysLoaded == null || scorecard.dataDaysLoaded <= 0) return "—";
  if (
    scorecard.dataManifestDaysLoaded != null &&
    scorecard.dataManifestDaysLoaded > 0 &&
    scorecard.dataManifestDaysLoaded !== scorecard.dataDaysLoaded
  ) {
    return `${scorecard.dataManifestDaysLoaded}d cache -> ${scorecard.dataDaysLoaded}d target`;
  }
  return `${scorecard.dataDaysLoaded}d loaded`;
}

export function formatEvolutionAction(scorecard: StageScorecardModel): string {
  if (!scorecard.evolutionLastActionDetail) return "—";
  const prefix = scorecard.evolutionLastActionApplied
    ? "Applied"
    : scorecard.evolutionLastActionDetail.toLowerCase().includes("not stage1")
      ? "Skipped"
      : "Skipped";
  return `${prefix}: ${scorecard.evolutionLastActionDetail}`;
}

/** Pass criteria met: EdgeScore uses composite blockers, not hygiene target. */
export function isGoalMet(scorecard: StageScorecardModel): boolean {
  return isStageGoalMet(scorecard);
}

/** Single-instrument Hygiene WR readout (lifetime + rolling in hint — no triple cards). */
export function formatHygieneInstrumentValue(scorecard: StageScorecardModel): string {
  if (scorecard.hygieneWrEffective != null) {
    return `${(scorecard.hygieneWrEffective * 100).toFixed(1)}%`;
  }
  if (scorecard.hygieneWrLifetime != null) {
    return `${(scorecard.hygieneWrLifetime * 100).toFixed(1)}%`;
  }
  return "—";
}

/** True for stage-2 (30–70%) and stage-3 mixed occupancy (25–75%). */
export function shouldShowPositionFlat(scorecard: StageScorecardModel): boolean {
  const id = String(scorecard.passCriteriaId ?? "");
  return (
    (id === "range_edgescore" ||
      id === "range_hold_ratio" ||
      id === "range_roundtrip" ||
      id === "mixed_edgescore" ||
      id === "mixed_foundation") &&
    scorecard.stageRangeFlatRatio != null &&
    Number.isFinite(scorecard.stageRangeFlatRatio)
  );
}

/** Stage-3 hold% is diagnostic only (geometry HOLD is expected); occupancy is the gate. */
export function shouldShowHoldRatio(scorecard: StageScorecardModel): boolean {
  const id = String(scorecard.passCriteriaId ?? "");
  return (
    (id === "mixed_edgescore" || id === "mixed_foundation") &&
    scorecard.stageHoldRatio != null &&
    Number.isFinite(scorecard.stageHoldRatio)
  );
}

/** Position flat % for stage-2 range activity band (30–70%). */
export function formatPositionFlatValue(scorecard: StageScorecardModel): string {
  if (scorecard.stageRangeFlatRatio == null || !Number.isFinite(scorecard.stageRangeFlatRatio)) {
    return "—";
  }
  return `${(scorecard.stageRangeFlatRatio * 100).toFixed(1)}%`;
}

export function formatPositionFlatHint(scorecard: StageScorecardModel): string {
  const min =
    scorecard.stageRangeFlatMin != null
      ? (scorecard.stageRangeFlatMin * 100).toFixed(0)
      : "30";
  const max =
    scorecard.stageRangeFlatMax != null
      ? (scorecard.stageRangeFlatMax * 100).toFixed(0)
      : "70";
  const rt =
    scorecard.stageRangeRoundTrips != null
      ? ` · ${scorecard.stageRangeRoundTrips.toLocaleString()} round-trips`
      : "";
  return `need ${min}–${max}% flat (range activity)${rt}`;
}

export function positionFlatTone(scorecard: StageScorecardModel): ConditionTone {
  return resolveConditionTone({
    value: scorecard.stageRangeFlatRatio,
    min: scorecard.stageRangeFlatMin ?? 0.3,
    max: scorecard.stageRangeFlatMax ?? 0.7,
    direction: "band",
    criticalGap: 0.15,
  });
}

export function formatHoldRatioValue(scorecard: StageScorecardModel): string {
  if (scorecard.stageHoldRatio == null || !Number.isFinite(scorecard.stageHoldRatio)) {
    return "—";
  }
  return `${(scorecard.stageHoldRatio * 100).toFixed(1)}%`;
}

export function formatHoldRatioHint(_scorecard: StageScorecardModel): string {
  return "diagnostic only · occupancy is the pass gate";
}

export function holdRatioTone(_scorecard: StageScorecardModel): ConditionTone {
  return "default";
}

/** Hygiene WR: higher is better vs floor. Stage-2 uses lifetime vs durable C-band. */
export function hygieneConditionTone(scorecard: StageScorecardModel): ConditionTone {
  const id = String(scorecard.passCriteriaId ?? "");
  const slope = scorecard.winrateTrendSlope;
  const improving = slope == null ? null : slope > 0.00005;
  if (id === "range_edgescore") {
    const life = scorecard.hygieneWrLifetime;
    const roll = scorecard.hygieneWrRolling ?? scorecard.rollingWinrate500;
    const wrFloor = 0.35;
    const lifeMin = wrFloor - 0.05;
    const rollLift =
      roll != null && Number.isFinite(roll) && roll + 1e-12 >= wrFloor &&
      (life == null || life + 1e-12 < wrFloor);
    return resolveConditionTone({
      value: life ?? null,
      target: rollLift ? lifeMin : wrFloor,
      direction: "higher",
      improving,
      criticalGap: 0.05,
    });
  }
  const value = scorecard.hygieneWrEffective ?? scorecard.hygieneWrLifetime;
  const floor = scorecard.hygieneWrFloor;
  return resolveConditionTone({
    value,
    target: floor,
    direction: "higher",
    improving,
    criticalGap: 0.08,
  });
}

/**
 * Live EdgeScore / primary pass metric.
 * Composite: met when goal met; else slope / gap heuristics.
 */
export function edgeScoreConditionTone(
  scorecard: StageScorecardModel,
  options?: { goalMet?: boolean },
): ConditionTone {
  if (scorecard.blockerDetail) {
    // Explicit stage blocker → red unless metric is still climbing.
    const slope = scorecard.winrateTrendSlope;
    if (slope != null && slope > 0.00005) return "warn";
    return "danger";
  }
  if (options?.goalMet) return "ok";
  const id = String(scorecard.passCriteriaId ?? "");
  if (
    id === "trend_edgescore" ||
    id === "range_edgescore" ||
    id === "mixed_edgescore"
  ) {
    // No single numeric target for composite EdgeScore — volume progress = orange.
    const tradesOk =
      scorecard.tradesRequired <= 0 ||
      scorecard.tradesDone >= scorecard.tradesRequired;
    if (tradesOk && scorecard.metricValue != null && scorecard.metricValue >= 0.45) {
      return "warn";
    }
    if (scorecard.tradesDone > 0) return "warn";
    return "default";
  }
  return resolveConditionTone({
    value: scorecard.metricValue,
    target: scorecard.metricTarget,
    min: scorecard.metricMin,
    max: scorecard.metricMax,
    direction:
      scorecard.passCriteriaId === "closed_loop"
        ? "lower"
        : scorecard.metricMin != null && scorecard.metricMax != null
          ? "band"
          : "higher",
    improving:
      scorecard.winrateTrendSlope == null
        ? null
        : scorecard.winrateTrendSlope > 0.00005,
    criticalGap: scorecard.passCriteriaId === "closed_loop" ? 0.5 : 0.08,
  });
}

/** Stage volume toward pass gate. */
export function volumeConditionTone(
  tradesDone: number,
  passGate: number | null,
): ConditionTone {
  if (passGate == null || passGate <= 0) {
    return tradesDone > 0 ? "ok" : "default";
  }
  if (tradesDone >= passGate) return "ok";
  if (tradesDone <= 0) return "default";
  // Any progress under the gate is "going the right way".
  return "warn";
}

export function expectancyConditionTone(
  value: number | null | undefined,
  floor: number = -0.15,
): ConditionTone {
  return resolveConditionTone({
    value: value ?? null,
    target: floor,
    direction: "higher",
    criticalGap: 0.1,
  });
}

export function entropyConditionTone(
  alive: boolean | null | undefined,
  missing: boolean,
): ConditionTone {
  if (missing) return "warn";
  return resolveBooleanConditionTone(alive);
}

export function formatHygieneInstrumentHint(scorecard: StageScorecardModel): string {
  const floor =
    scorecard.hygieneWrFloor != null
      ? `≥${(scorecard.hygieneWrFloor * 100).toFixed(0)}%`
      : "≥35%";
  const life =
    scorecard.hygieneWrLifetime != null
      ? `${(scorecard.hygieneWrLifetime * 100).toFixed(1)}%`
      : "—";
  const roll =
    scorecard.hygieneWrRolling != null || scorecard.rollingWinrate500 != null
      ? `${(((scorecard.hygieneWrRolling ?? scorecard.rollingWinrate500) as number) * 100).toFixed(1)}%`
      : null;
  const covered = scorecard.rollingWindowTradesCovered;
  const rollNote =
    roll == null
      ? null
      : scorecard.rollingWrEligible === false
        ? `roll ${roll} (${covered ?? 0}/400)`
        : scorecard.rollingWrEligible === true
          ? `roll ${roll} eligible`
          : `roll ${roll}`;
  const source = scorecard.hygieneWrSource ? ` · ${scorecard.hygieneWrSource}` : "";
  return [`life ${life}`, rollNote, `need ${floor}${source}`].filter(Boolean).join(" · ");
}
