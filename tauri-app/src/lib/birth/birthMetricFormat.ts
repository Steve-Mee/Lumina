/** Shared Stage scorecard metric formatting (Starship EdgeScore honesty). */

export type ScorecardMetricLike = {
  metricValue?: number | null;
  metricTarget?: number | null;
  metricMin?: number | null;
  metricMax?: number | null;
  metricLabel?: string | null;
  passCriteriaId?: string | null;
  tradesDone?: number;
  goalLabel?: string | null;
};

function isEdgeScoreMetric(model: ScorecardMetricLike): boolean {
  const id = String(model.passCriteriaId ?? "");
  return (
    (id === "trend_edgescore" || id === "range_edgescore" || id === "mixed_edgescore") &&
    String(model.metricLabel ?? "").toLowerCase() === "edgescore"
  );
}

export function formatBirthMetricValue(model: ScorecardMetricLike): string {
  if (model.metricValue == null) {
    if (
      (model.passCriteriaId === "trend_winrate" || model.passCriteriaId === "trend_edgescore") &&
      (model.tradesDone ?? 0) > 0
    ) {
      return "syncing…";
    }
    return "—";
  }
  if (model.passCriteriaId === "mixed_constitution") {
    return String(Math.round(model.metricValue));
  }
  // EdgeScore and ratio metrics are stored in [0, 1]; display as percent.
  return `${(model.metricValue * 100).toFixed(0)}%`;
}

export function formatBirthMetricValuePrecise(model: ScorecardMetricLike): string {
  if (model.metricValue == null) {
    return (model.tradesDone ?? 0) > 0 ? "syncing…" : "—";
  }
  if (model.passCriteriaId === "mixed_constitution") {
    return String(Math.round(model.metricValue));
  }
  return `${(model.metricValue * 100).toFixed(1)}%`;
}

/** Format a raw EdgeScore / champion score in [0, 1] as a percent string. */
export function formatBirthEdgeScorePercent(
  value: number | null | undefined,
  options?: { precise?: boolean },
): string {
  if (value == null || !Number.isFinite(value)) {
    return "—";
  }
  return options?.precise
    ? `${(Number(value) * 100).toFixed(1)}%`
    : `${(Number(value) * 100).toFixed(0)}%`;
}

/**
 * Expectancy proxy is WR−50% on [-0.5, 0.5] (e.g. -0.17 => -17%).
 * Reject legacy USD-mean leftovers (|value| ≫ 0.5) so UI never shows -149358%.
 */
export function isBirthExpectancyProxyValid(value: number | null | undefined): boolean {
  return value != null && Number.isFinite(value) && Math.abs(Number(value)) <= 0.55;
}

/** Expectancy proxy is WR-50% (e.g. -0.17 => -17%); floor default -15%. */
export function formatBirthExpectancyPercent(
  value: number | null | undefined,
  options?: { floor?: number },
): { value: string; hint: string } {
  const floor = options?.floor ?? -0.15;
  const hint = `WR-50% | need >= ${(floor * 100).toFixed(0)}%`;
  if (!isBirthExpectancyProxyValid(value)) {
    return {
      value: "—",
      hint:
        value != null && Number.isFinite(value)
          ? `${hint} · stale scale (restart birth)`
          : hint,
    };
  }
  const pct = Number(value) * 100;
  const sign = pct > 0 ? "+" : "";
  return {
    value: `${sign}${pct.toFixed(0)}%`,
    hint,
  };
}

export function formatBirthMetricTarget(model: ScorecardMetricLike): string {
  if (model.passCriteriaId === "mixed_constitution") {
    return "need 0";
  }
  if (model.passCriteriaId === "range_hold_ratio" || model.passCriteriaId === "range_roundtrip") {
    const min = model.metricMin != null ? (model.metricMin * 100).toFixed(0) : "30";
    const max = model.metricMax != null ? (model.metricMax * 100).toFixed(0) : "70";
    return `target ${min}–${max}%`;
  }
  if (isEdgeScoreMetric(model)) {
    const id = String(model.passCriteriaId ?? "");
    if (id === "range_edgescore") {
      return "flat 30-70% | round-trips | entropy alive | expectancy >= -15%";
    }
    if (id === "mixed_edgescore") {
      return "hygiene WR>=35% (lifetime or rolling) | hold cap | entropy alive | expectancy >= -15%";
    }
    return "hygiene WR>=35% (lifetime or rolling) | hold band | entropy alive | expectancy >= -15%";
  }
  if (model.metricTarget != null) {
    return `need ${(model.metricTarget * 100).toFixed(0)}%`;
  }
  return String(model.goalLabel ?? "");
}

/** Detail line under a scorecard metric (MetricsStrip / MissionControl). */
export function formatBirthMetricDetail(model: ScorecardMetricLike): string {
  if (model.metricValue == null) {
    if (
      (model.passCriteriaId === "trend_winrate" ||
        model.passCriteriaId === "trend_edgescore" ||
        model.passCriteriaId === "range_edgescore" ||
        model.passCriteriaId === "mixed_edgescore") &&
      (model.tradesDone ?? 0) > 0
    ) {
      return "syncing after next rollout or backend restart";
    }
    return "—";
  }
  if (model.passCriteriaId === "mixed_constitution") {
    return `${Math.round(model.metricValue)} violations`;
  }
  if (isEdgeScoreMetric(model)) {
    const value = `${(model.metricValue * 100).toFixed(0)}%`;
    const target = formatBirthMetricTarget(model);
    return `${value} | ${target}`;
  }
  const value = `${(model.metricValue * 100).toFixed(1)}%`;
  if (model.passCriteriaId === "range_hold_ratio" || model.passCriteriaId === "range_roundtrip") {
    return `${value} (${formatBirthMetricTarget(model)})`;
  }
  if (model.passCriteriaId === "mixed_foundation") {
    const need =
      model.metricTarget != null
        ? `pass if ≥${(model.metricTarget * 100).toFixed(0)}% (all trades)`
        : "pass if ≥35% (all trades)";
    return `${value} · ${need}`;
  }
  if (model.metricTarget != null) {
    return `${value} → need ${(model.metricTarget * 100).toFixed(0)}%`;
  }
  return value;
}

export function isBirthEdgeScoreCriteria(passCriteriaId: string | null | undefined): boolean {
  const id = String(passCriteriaId ?? "");
  return id === "trend_edgescore" || id === "range_edgescore" || id === "mixed_edgescore";
}
