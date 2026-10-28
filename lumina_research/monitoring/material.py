"""Short-horizon material-break tests: IC halved, Sharpe <50% OOS, vol-scaled DD."""

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
from lumina_research.monitoring.statistics import live_noise_vol, rolling_mean
from lumina_research.monitoring.types import ContinuityRefused, DecayAssessment, VolRegime, stage_from_rank

# Detector parameters. Not floors. MATERIAL_DD_MULT stays 1.50.
_QUIET_DIFF_SIGMA_MULT = 1.5
_QUIET_LARGE_DIFF_MAX = 2
_RESTORE_SLOP_SIGMA = 0.5
_BLOM_A = 0.375
_BLOM_B = 0.25
_MAD_TO_SIGMA = float(statistics.NormalDist().inv_cdf(0.75))


def assess_material(
    series: Sequence[float],
    oos: Sequence[float],
    config: ContinuityConfig,
    *,
    vol_regime: VolRegime = "normal",
) -> DecayAssessment:
    """Ready only after the packaged short window. Severity 0–2 (deweight/suspend).

    Drawdown is never skipped because the regime label is high_vol. High-vol noise
    is handled by scaling the expected OOS DD by live sigma and sample length.
    A crash-recover on a quiet tape still trips the 1.5x OOS DD floor.
    """
    label = str(vol_regime)
    if label != "high_vol" and label != "normal":
        raise ContinuityRefused("unknown vol regime")
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
    noise = live_noise_vol(series, window=window)
    base = noise if noise is not None and noise > 0.0 else live_stdev
    vol_scale = 1.0
    if oos_stdev > 0.0 and base > oos_stdev:
        vol_scale = oos_stdev / base
    ic_hit = _ic_halved(live_mean, oos_mean)
    sharpe_hit = _sharpe_halved(live_mean, max(base * vol_scale, 1e-12), oos_mean, oos_stdev)
    dd_hit = _drawdown_breach(series, oos_values, oos_stdev, window=window)
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


def _drawdown_breach(
    series: Sequence[float],
    oos: Sequence[float],
    oos_stdev: float,
    *,
    window: int,
) -> bool:
    """Vol-scaled DD vs the length-adjusted OOS DD distribution. Never skipped.

    Quiet crash-recover: MAD vol at or below OOS, at most two large first-diffs
    (the drop and the restore), last print back near the peak, and max DD still
    >= 1.5x the OOS expected DD. That is the high-vol VIX / quiet-tape hole.

    Loud tape: compare live max DD to 1.5x OOS expected DD times live/OOS sigma
    times Blom expected-range(n_live)/expected-range(n_oos). High-vol noise of
    ordinary size does not trip; a quiet-tape crash still does.
    """
    live_dd = _max_drawdown(series)
    expected = _oos_expected_dd(oos, oos_stdev)
    raw_floor = MATERIAL_DD_MULT * expected
    if live_dd < raw_floor:
        return False
    if _quiet_crash_recover(series, oos_stdev=oos_stdev, window=window, raw_floor=raw_floor):
        return True
    sigma = _live_dd_sigma(series, window=window)
    vol_ratio = max(sigma / max(oos_stdev, 1e-12), 1.0)
    length_factor = 1.0
    if sigma > oos_stdev:
        length_factor = max(
            _expected_unit_range(len(series)) / max(_expected_unit_range(len(oos)), 1e-12),
            1.0,
        )
    return live_dd >= raw_floor * vol_ratio * length_factor


def _quiet_crash_recover(
    series: Sequence[float],
    *,
    oos_stdev: float,
    window: int,
    raw_floor: float,
) -> bool:
    if _time_underwater(series, raw_floor) < 1:
        return False
    if _robust_diff_vol(series, window=window) > max(oos_stdev, 0.0):
        return False
    if not _restored_to_peak(series, slop=_RESTORE_SLOP_SIGMA * max(oos_stdev, 0.0)):
        return False
    return _n_large_diffs(series, oos_stdev=oos_stdev, window=window) <= _QUIET_LARGE_DIFF_MAX


def _oos_expected_dd(oos: Sequence[float], oos_stdev: float) -> float:
    oos_range = max(oos) - min(oos) if oos else 0.0
    return max(oos_range, 2.0 * max(oos_stdev, 0.0), 1e-12)


def _live_dd_sigma(series: Sequence[float], *, window: int) -> float:
    noisy = live_noise_vol(series, window=window)
    fast = 0.0 if noisy is None else float(noisy)
    return max(fast, _robust_diff_vol(series, window=window))


def _window_diffs(series: Sequence[float], *, window: int) -> tuple[float, ...]:
    if window < 2:
        raise ContinuityRefused("drawdown window must be >= 2")
    chunk = tuple(float(item) for item in series[-min(window, len(series)) :])
    if any(not math.isfinite(item) for item in chunk):
        raise ContinuityRefused("non-finite live metric")
    if len(chunk) < 2:
        return ()
    return tuple(chunk[index] - chunk[index - 1] for index in range(1, len(chunk)))


def _robust_diff_vol(series: Sequence[float], *, window: int) -> float:
    items = _window_diffs(series, window=window)
    if not items:
        return 0.0
    med = float(statistics.median(items))
    mad = float(statistics.median(tuple(abs(item - med) for item in items)))
    return (mad / _MAD_TO_SIGMA) / math.sqrt(2.0)


def _n_large_diffs(series: Sequence[float], *, oos_stdev: float, window: int) -> int:
    cap = _QUIET_DIFF_SIGMA_MULT * max(oos_stdev, 1e-12)
    return sum(1 for item in _window_diffs(series, window=window) if abs(item) > cap)


def _restored_to_peak(series: Sequence[float], *, slop: float) -> bool:
    if not series:
        return False
    peak = max(float(item) for item in series)
    return float(series[-1]) >= peak - max(slop, 0.0)


def _time_underwater(series: Sequence[float], depth: float) -> int:
    peak = float("-inf")
    longest = 0
    current = 0
    for item in series:
        value = float(item)
        if not math.isfinite(value):
            raise ContinuityRefused("non-finite live metric")
        if value > peak:
            peak = value
        if peak - value >= depth:
            current += 1
            if current > longest:
                longest = current
        else:
            current = 0
    return int(longest)


def _expected_unit_range(n: int) -> float:
    """Blom expected range of n iid N(0, 1) samples. Used only to vol-adjust DD."""
    if n <= 1:
        return 0.0
    inner = (float(n) - _BLOM_A) / (float(n) + _BLOM_B)
    inner = min(max(inner, 1e-12), 1.0 - 1e-12)
    return 2.0 * float(statistics.NormalDist().inv_cdf(inner))


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
