"""Short-horizon material-break tests: IC halved, Sharpe <50% OOS, DD >= 1.5x."""

from __future__ import annotations

import math
import statistics
from typing import Sequence

from lumina_research.monitoring.acceptance import (
    MATERIAL_DD_MULT,
    MATERIAL_IC_RATIO,
    MATERIAL_SHARPE_RATIO,
)
from lumina_research.monitoring.config import ContinuityConfig
from lumina_research.monitoring.statistics import rolling_mean
from lumina_research.monitoring.types import ContinuityRefused, DecayAssessment, stage_from_rank


def assess_material(
    series: Sequence[float],
    oos: Sequence[float],
    config: ContinuityConfig,
) -> DecayAssessment:
    """Ready only after the packaged short window. Severity 0–2 (deweight/suspend)."""
    oos_values = tuple(float(item) for item in oos)
    if not oos_values:
        raise ContinuityRefused("OOS distribution is empty")
    if any(not math.isfinite(item) for item in oos_values):
        raise ContinuityRefused("non-finite OOS value")
    oos_mean = float(statistics.fmean(oos_values))
    oos_stdev = float(statistics.pstdev(oos_values)) if len(oos_values) >= 2 else 0.0
    window = int(config.window)
    if len(series) < config.min_observations or len(series) < window:
        return DecayAssessment(
            method=config.method,
            severity=0,
            stage="active",
            statistic=0.0,
            threshold=0.0,
            live_mean=None,
            oos_mean=oos_mean,
            oos_stdev=oos_stdev,
            percentile=None,
            cusum=None,
            sprt_llr=None,
            window=window,
            votes_deweight=0,
            votes_suspend=0,
            votes_retire=0,
            ready=False,
            horizon="short",
        )
    live_mean = rolling_mean(series, window)
    live_chunk = tuple(float(item) for item in series[-window:])
    live_stdev = float(statistics.pstdev(live_chunk)) if len(live_chunk) >= 2 else 0.0
    ic_hit = _ic_halved(live_mean, oos_mean)
    sharpe_hit = _sharpe_halved(live_mean, live_stdev, oos_mean, oos_stdev)
    dd_hit = _drawdown_breach(series, oos_values, oos_stdev)
    hits = (ic_hit, sharpe_hit, dd_hit)
    n_hits = sum(1 for item in hits if item)
    severity = 0
    if n_hits >= 1:
        severity = 1
    if n_hits >= 2:
        severity = 2
    return DecayAssessment(
        method=config.method,
        severity=severity,
        stage=stage_from_rank(severity),
        statistic=float(n_hits),
        threshold=1.0,
        live_mean=live_mean,
        oos_mean=oos_mean,
        oos_stdev=oos_stdev,
        percentile=None,
        cusum=None,
        sprt_llr=None,
        window=window,
        votes_deweight=1 if severity >= 1 else 0,
        votes_suspend=1 if severity >= 2 else 0,
        votes_retire=0,
        ready=True,
        horizon="short",
    )


def _ic_halved(live_mean: float, oos_mean: float) -> bool:
    if oos_mean > 0.0:
        return live_mean < MATERIAL_IC_RATIO * oos_mean
    if oos_mean < 0.0:
        return live_mean < oos_mean - abs(MATERIAL_IC_RATIO * oos_mean)
    return live_mean < 0.0


def _sharpe_halved(live_mean: float, live_stdev: float, oos_mean: float, oos_stdev: float) -> bool:
    expected = _ratio(oos_mean, oos_stdev)
    live = _ratio(live_mean, live_stdev)
    if expected > 0.0:
        return live < MATERIAL_SHARPE_RATIO * expected
    if expected < 0.0:
        return live < expected
    return live < 0.0


def _ratio(mean: float, stdev: float) -> float:
    if stdev > 0.0:
        return mean / stdev
    if mean > 0.0:
        return math.inf
    if mean < 0.0:
        return -math.inf
    return 0.0


def _drawdown_breach(series: Sequence[float], oos: Sequence[float], oos_stdev: float) -> bool:
    live_dd = _max_drawdown(series)
    oos_range = max(oos) - min(oos) if oos else 0.0
    expected = max(oos_range, 2.0 * max(oos_stdev, 0.0), 1e-12)
    return live_dd >= MATERIAL_DD_MULT * expected


def _max_drawdown(series: Sequence[float]) -> float:
    peak = float("-inf")
    worst = 0.0
    for item in series:
        value = float(item)
        if not math.isfinite(value):
            raise ContinuityRefused("non-finite live metric")
        if value > peak:
            peak = value
        draw = peak - value
        if draw > worst:
            worst = draw
    return float(worst)
