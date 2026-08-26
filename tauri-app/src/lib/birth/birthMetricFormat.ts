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
    // Missing process-R after trades is fail-closed, not "still syncing".
    if (model.passCriteriaId === "closed_loop") {
      return "—";
    }
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
  if (model.passCriteriaId === "closed_loop") {
    return `${Number(model.metricValue).toFixed(2)}R`;
  }
  if (
    model.passCriteriaId === "mixed_regimes" ||
    model.passCriteriaId === "viable_plant" ||
    model.passCriteriaId === "probe_handoff"
  ) {
    const sign = Number(model.metricValue) > 0 ? "+" : "";
    return `${sign}${(Number(model.metricValue) * 100).toFixed(1)}pp`;
  }
  // EdgeScore and ratio metrics are stored in [0, 1]; display as percent.
  return `${(model.metricValue * 100).toFixed(0)}%`;
}

export function formatBirthMetricValuePrecise(model: ScorecardMetricLike): string {
  const id = String(model.passCriteriaId ?? "");
  if (
    id === "closed_loop" ||
    id === "mixed_regimes" ||
    id === "viable_plant" ||
    id === "probe_handoff" ||
    id === "mixed_constitution"
  ) {
    return formatBirthMetricValue(model);
  }
  if (model.metricValue == null) {
    return (model.tradesDone ?? 0) > 0 ? "syncing…" : "—";
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
 * Champion EdgeScore is only frozen after pass-gate volume.
 * Backend used to publish 0.0 before lock → UI showed a fake "0%".
 */
export function formatBirthChampionEdgeScore(progress: {
  best_edgescore?: number | null;
  best_edgescore_at_trade?: number | null;
  edgescore_champion_min_trades?: number | null;
  edgescore_champion_locked?: boolean | null;
  stage_trades?: number | null;
  stage_pass_gate_trades?: number | null;
  stage_target_trades?: number | null;
  swarm_rejected_no_lift?: boolean | null;
  policy_swarm_rejected_no_lift?: boolean | null;
}): { value: string; hint: string; tone: "default" | "ok" | "warn" } {
  const locked = progress.edgescore_champion_locked === true;
  const best = progress.best_edgescore;
  const atTrade = Number(progress.best_edgescore_at_trade ?? 0);
  const hasLockedScore =
    locked ||
    (best != null && Number.isFinite(best) && Number(best) > 0 && atTrade > 0);

  const swarmReject =
    progress.swarm_rejected_no_lift === true ||
    progress.policy_swarm_rejected_no_lift === true;

  if (hasLockedScore) {
    return {
      value: formatBirthEdgeScorePercent(best),
      hint: swarmReject
        ? "frozen after swarm — no tournament lift"
        : atTrade > 0
          ? `best this stage @ ${atTrade.toLocaleString()} trades`
          : "best EdgeScore this stage",
      tone: swarmReject ? "warn" : "ok",
    };
  }

  const stageTrades = Math.max(0, Number(progress.stage_trades ?? 0));
  const minTrades = Math.max(
    1,
    Number(
      progress.edgescore_champion_min_trades ??
        progress.stage_pass_gate_trades ??
        progress.stage_target_trades ??
        200,
    ),
  );
  if (stageTrades < minTrades) {
    return {
      value: "—",
      hint: `locks after ${minTrades.toLocaleString()} stage trades (${stageTrades.toLocaleString()} now)`,
      tone: "default",
    };
  }
  return {
    value: "—",
    hint: "no champion locked yet",
    tone: "default",
  };
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
    if (id === "range_edgescore" || id === "selectivity") {
      return "occupancy 30-70% | round-trips | median loss R <= 1.5 | settlement >=70%";
    }
    if (id === "mixed_edgescore" || id === "mixed_regimes") {
      return "occupancy 25–75% | edge >= -5pp vs first-touch | median loss R <= 1.5 | settlement >=70%";
    }
    if (id === "viable_plant") {
      return "skill WR >= first-touch AND mean R >= E_mech-0.10 | occupancy 25-75% | process-R";
    }
    if (id === "probe_handoff") {
      return "holdout edge >= -3pp | Sharpe > -2 | DD <= 25%";
    }
    return "median loss R <= 1.5 | settlement >=70% | entropy alive | net RR >= 0.80";
  }
  if (model.metricTarget != null) {
    return `need ${(model.metricTarget * 100).toFixed(0)}%`;
  }
  return String(model.goalLabel ?? "");
}

/** Detail line under a scorecard metric (MetricsStrip / MissionControl). */
export function formatBirthMetricDetail(model: ScorecardMetricLike): string {
  if (model.metricValue == null) {
    if (model.passCriteriaId === "closed_loop") {
      return (model.tradesDone ?? 0) > 0
        ? "median loss R missing (fail-closed)"
        : "—";
    }
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
  if (model.passCriteriaId === "closed_loop") {
    const cap = model.metricMax ?? 1.5;
    return `${Number(model.metricValue).toFixed(2)}R | need ≤ ${cap}R`;
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
        : "pass if occupancy 25–75% and edge ≥ −5pp";
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
