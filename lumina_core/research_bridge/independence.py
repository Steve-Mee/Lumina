"""D11 independence: different hypothesis+family AND pairwise corr strictly < 0.5."""

from __future__ import annotations

import math
from collections.abc import Sequence

from lumina_core.research_bridge.binding_policy import independent as policy_independent

MIN_CORR_BARS = 8
CORR_STRICT_MAX = 0.5


class IndependenceRefused(ValueError):
    """Correlation cannot be computed without inventing a series."""


def pairwise_correlation(
    left: Sequence[float] | None,
    right: Sequence[float] | None,
) -> tuple[float | None, str]:
    """Pearson corr. Too short, non-finite, or zero-variance → unavailable."""
    if left is None or right is None:
        return None, "survivors_corr_unavailable"
    if isinstance(left, (str, bytes)) or isinstance(right, (str, bytes)):
        return None, "survivors_corr_unavailable"
    xs = _finite_series(left)
    ys = _finite_series(right)
    if xs is None or ys is None:
        return None, "survivors_corr_unavailable"
    n = min(len(xs), len(ys))
    if n < MIN_CORR_BARS:
        return None, "survivors_corr_unavailable"
    a = xs[:n]
    b = ys[:n]
    mean_a = sum(a) / float(n)
    mean_b = sum(b) / float(n)
    num = 0.0
    den_a = 0.0
    den_b = 0.0
    for left_v, right_v in zip(a, b, strict=True):
        da = left_v - mean_a
        db = right_v - mean_b
        num += da * db
        den_a += da * da
        den_b += db * db
    if den_a <= 0.0 or den_b <= 0.0:
        return None, "survivors_corr_unavailable"
    corr = num / math.sqrt(den_a * den_b)
    if not math.isfinite(corr):
        return None, "survivors_corr_unavailable"
    if corr > 1.0:
        corr = 1.0
    if corr < -1.0:
        corr = -1.0
    return float(corr), "ok"


def d11_independent(
    *,
    hypothesis_id: str,
    family: str,
    other_hypothesis_id: str,
    other_family: str,
    config_id: str,
    other_config_id: str,
    left_returns: Sequence[float] | None,
    right_returns: Sequence[float] | None,
    correlation: float | None = None,
) -> tuple[bool, str]:
    """Both clauses required. ``correlation`` is used when series are omitted."""
    corr = correlation
    reason = "ok"
    if corr is None:
        corr, reason = pairwise_correlation(left_returns, right_returns)
        if reason != "ok":
            return False, reason
    return policy_independent(
        hypothesis_id=hypothesis_id,
        family=family,
        other_hypothesis_id=other_hypothesis_id,
        other_family=other_family,
        config_id=config_id,
        other_config_id=other_config_id,
        correlation=corr,
    )


def independent_set(
    rows: Sequence[object],
) -> tuple[tuple[object, ...], str]:
    """Largest set where every pair is D11-independent. Empty → not independent."""
    items = tuple(rows)
    if len(items) < 2:
        return (), "survivors_insufficient"
    chosen: list[object] = []
    for candidate in items:
        ok = True
        for existing in chosen:
            pair_ok, reason = _pair(candidate, existing)
            if pair_ok is not True:
                ok = False
                if not chosen:
                    return (), reason
                break
        if ok:
            chosen.append(candidate)
    if len(chosen) < 2:
        return (), "survivors_not_independent"
    return tuple(chosen), "independent"


def _pair(left: object, right: object) -> tuple[bool, str]:
    return d11_independent(
        hypothesis_id=str(getattr(left, "hypothesis_id", "") or ""),
        family=str(getattr(left, "family", "") or ""),
        other_hypothesis_id=str(getattr(right, "hypothesis_id", "") or ""),
        other_family=str(getattr(right, "family", "") or ""),
        config_id=str(getattr(left, "config_id", "") or ""),
        other_config_id=str(getattr(right, "config_id", "") or ""),
        left_returns=getattr(left, "returns", None),
        right_returns=getattr(right, "returns", None),
        correlation=None,
    )


def _finite_series(values: Sequence[float]) -> tuple[float, ...] | None:
    out: list[float] = []
    try:
        rows = list(values)
    except TypeError:
        return None
    for item in rows:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None
        number = float(item)
        if not math.isfinite(number):
            return None
        out.append(number)
    return tuple(out)
