"""Z-test, percentile, downward CUSUM, and SPRT versus a promotion-time OOS distribution."""

from __future__ import annotations

import math
import statistics
from typing import Sequence, assert_never

from lumina_core.agent_orchestration.schemas_research import DecayMethod
from lumina_research.monitoring.config import ContinuityConfig
from lumina_research.monitoring.types import ContinuityRefused, DecayAssessment, stage_from_rank


def rolling_mean(values: Sequence[float], window: int) -> float:
    if window < 1:
        raise ContinuityRefused("window must be >= 1")
    if len(values) < window:
        raise ContinuityRefused("insufficient observations for rolling window")
    chunk = tuple(float(item) for item in values[-window:])
    if any(not math.isfinite(item) for item in chunk):
        raise ContinuityRefused("non-finite live metric")
    return float(statistics.fmean(chunk))


def z_score(*, live_mean: float, oos_mean: float, oos_stdev: float, n: int) -> float:
    if n < 1:
        raise ContinuityRefused("z-test requires n >= 1")
    if not math.isfinite(live_mean) or not math.isfinite(oos_mean) or not math.isfinite(oos_stdev):
        raise ContinuityRefused("non-finite z-test inputs")
    if oos_stdev < 0.0:
        raise ContinuityRefused("OOS stdev cannot be negative")
    if oos_stdev == 0.0:
        if live_mean >= oos_mean:
            return 0.0
        return float("-inf")
    se = oos_stdev / math.sqrt(float(n))
    return (live_mean - oos_mean) / se


def empirical_percentile(live: float, oos: Sequence[float]) -> float:
    cleaned = tuple(float(item) for item in oos)
    if not cleaned:
        raise ContinuityRefused("OOS distribution is empty")
    if any(not math.isfinite(item) for item in cleaned) or not math.isfinite(live):
        raise ContinuityRefused("non-finite percentile inputs")
    return float(sum(1 for item in cleaned if item <= live) / len(cleaned))


def cusum_down(values: Sequence[float], *, mu0: float, k: float) -> tuple[float, ...]:
    if not math.isfinite(mu0) or not math.isfinite(k) or k < 0.0:
        raise ContinuityRefused("illegal CUSUM parameters")
    score = 0.0
    path: list[float] = []
    for item in values:
        value = float(item)
        if not math.isfinite(value):
            raise ContinuityRefused("non-finite CUSUM observation")
        score = max(0.0, score + (mu0 - value) - k)
        path.append(score)
    return tuple(path)


def sprt_llr(values: Sequence[float], *, mu0: float, mu1: float, sigma: float) -> float:
    if not math.isfinite(mu0) or not math.isfinite(mu1) or not math.isfinite(sigma):
        raise ContinuityRefused("non-finite SPRT parameters")
    if sigma <= 0.0:
        if all(float(item) == mu0 for item in values):
            return 0.0
        return float("inf") if mu1 < mu0 else float("-inf")
    acc = 0.0
    for item in values:
        value = float(item)
        if not math.isfinite(value):
            raise ContinuityRefused("non-finite SPRT observation")
        acc += ((mu1 - mu0) / (sigma * sigma)) * (value - 0.5 * (mu0 + mu1))
    return float(acc)


def sprt_threshold(*, alpha: float, beta: float) -> float:
    if alpha <= 0.0 or alpha >= 1.0 or beta <= 0.0 or beta >= 1.0:
        raise ContinuityRefused("SPRT error rates must be in (0, 1)")
    return math.log((1.0 - beta) / alpha)


def live_noise_vol(values: Sequence[float], *, window: int) -> float | None:
    """First-difference vol of the last window. Robust to a single mean-shift jump."""
    if window < 3 or len(values) < 3:
        return None
    chunk = tuple(float(item) for item in values[-window:])
    if any(not math.isfinite(item) for item in chunk):
        raise ContinuityRefused("non-finite live metric")
    diffs = tuple(chunk[index] - chunk[index - 1] for index in range(1, len(chunk)))
    if len(diffs) < 2:
        return None
    return float(statistics.pstdev(diffs)) / math.sqrt(2.0)


def effective_sigma(oos_stdev: float, series: Sequence[float], *, window: int) -> float:
    """Regime-conditional variance: never below OOS vol, never changes packaged thresholds."""
    baseline = oos_stdev if oos_stdev > 0.0 else 0.0
    live = live_noise_vol(series, window=window)
    if live is None:
        return baseline if baseline > 0.0 else 1.0
    if baseline <= 0.0:
        return live if live > 0.0 else 1.0
    return max(baseline, live)


def assess_decay(
    series: Sequence[float],
    oos: Sequence[float],
    config: ContinuityConfig,
) -> DecayAssessment:
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
        )
    live_mean = rolling_mean(series, window)
    sigma = effective_sigma(oos_stdev, series, window=window)
    scale = 1.0
    if oos_stdev > 0.0 and sigma > oos_stdev:
        scale = oos_stdev / sigma
    percentile_live = oos_mean + (live_mean - oos_mean) * scale
    percentile = empirical_percentile(percentile_live, oos_values)
    z_value = z_score(live_mean=live_mean, oos_mean=oos_mean, oos_stdev=sigma, n=window)
    k = config.cusum_k * sigma
    cusum_path = cusum_down(series, mu0=oos_mean, k=k)
    cusum = cusum_path[-1]
    mu1 = oos_mean - config.sprt_delta * sigma
    llr = sprt_llr(tuple(series)[-window:], mu0=oos_mean, mu1=mu1, sigma=sigma)
    a_limit = sprt_threshold(alpha=config.sprt_alpha, beta=config.sprt_beta)
    z_sev = _lower_severity(z_value, config.z_deweight, config.z_suspend, config.z_retire)
    pct_sev = _lower_severity(
        percentile, config.percentile_deweight, config.percentile_suspend, config.percentile_retire
    )
    cusum_sev = _upper_severity(cusum, config.cusum_h_deweight, config.cusum_h_suspend, config.cusum_h_retire)
    sprt_sev = _upper_severity(llr, a_limit * 0.5, a_limit * 0.75, a_limit)
    method = config.method
    chosen = _select(method, z_sev=z_sev, pct_sev=pct_sev, cusum_sev=cusum_sev, sprt_sev=sprt_sev)
    statistic, threshold = _display(method, z_value, percentile, cusum, llr, config, a_limit)
    votes_deweight = sum(1 for item in (z_sev, pct_sev, cusum_sev, sprt_sev) if item >= 1)
    votes_suspend = sum(1 for item in (z_sev, pct_sev, cusum_sev, sprt_sev) if item >= 2)
    votes_retire = sum(1 for item in (z_sev, pct_sev, cusum_sev, sprt_sev) if item >= 3)
    return DecayAssessment(
        method=method,
        severity=chosen,
        stage=stage_from_rank(chosen),
        statistic=statistic,
        threshold=threshold,
        live_mean=live_mean,
        oos_mean=oos_mean,
        oos_stdev=oos_stdev,
        percentile=percentile,
        cusum=cusum,
        sprt_llr=llr,
        window=window,
        votes_deweight=votes_deweight,
        votes_suspend=votes_suspend,
        votes_retire=votes_retire,
        ready=True,
    )


def _select(
    method: DecayMethod,
    *,
    z_sev: int,
    pct_sev: int,
    cusum_sev: int,
    sprt_sev: int,
) -> int:
    if method == "ztest":
        return z_sev
    if method == "percentile":
        return pct_sev
    if method == "cusum":
        return cusum_sev
    if method == "sprt":
        return sprt_sev
    if method == "combined":
        votes_deweight = sum(1 for item in (z_sev, pct_sev, cusum_sev, sprt_sev) if item >= 1)
        votes_suspend = sum(1 for item in (z_sev, pct_sev, cusum_sev, sprt_sev) if item >= 2)
        votes_retire = sum(1 for item in (z_sev, pct_sev, cusum_sev, sprt_sev) if item >= 3)
        if votes_retire >= 2:
            return 3
        if votes_suspend >= 2 or (votes_retire >= 1 and votes_deweight >= 2):
            return 2
        if votes_deweight >= 2:
            return 1
        # ADR-0058: a single extreme CUSUM may suspend. The live monitor still
        # confirms CONFIRM_WINDOWS consecutive ready assessments before applying,
        # so a one-bar high-vol spike does not change the book.
        if cusum_sev >= 2:
            return cusum_sev
        return 0
    assert_never(method)


def _lower_severity(value: float, deweight: float, suspend: float, retire: float) -> int:
    if value <= retire:
        return 3
    if value <= suspend:
        return 2
    if value <= deweight:
        return 1
    return 0


def _upper_severity(value: float, deweight: float, suspend: float, retire: float) -> int:
    if value >= retire:
        return 3
    if value >= suspend:
        return 2
    if value >= deweight:
        return 1
    return 0


def _display(
    method: DecayMethod,
    z_value: float,
    percentile: float,
    cusum: float,
    llr: float,
    config: ContinuityConfig,
    a_limit: float,
) -> tuple[float, float]:
    if method == "ztest":
        return z_value, config.z_deweight
    if method == "percentile":
        return percentile, config.percentile_deweight
    if method == "cusum":
        return cusum, config.cusum_h_deweight
    if method == "sprt":
        return llr, a_limit
    if method == "combined":
        return cusum, config.cusum_h_deweight
    assert_never(method)
