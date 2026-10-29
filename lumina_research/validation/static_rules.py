"""Static-rule OOS tests (researchers A2). WFE is not required without a fit step.

DSR and PBO floors are unchanged. These tests replace the WFE requirement only
when ``has_fit_step`` is false. See ADR-0061.
"""

from __future__ import annotations

import math
from typing import Sequence

STATIC_POSITIVE_SHARE_MIN = 0.60
STATIC_DECAY_SPEARMAN = -0.50


def positive_share(values: Sequence[float]) -> float:
    series = tuple(float(item) for item in values if math.isfinite(item))
    if not series:
        return math.nan
    return float(sum(1 for item in series if item > 0.0) / len(series))


def spearman_rho(values: Sequence[float]) -> float:
    series = tuple(float(item) for item in values if math.isfinite(item))
    n = len(series)
    if n < 3:
        return math.nan
    ranks_y = _ranks(series)
    ranks_x = tuple(float(index + 1) for index in range(n))
    return _pearson(ranks_x, ranks_y)


def structural_decay(values: Sequence[float]) -> bool:
    """True when OOS window means show a structural decline over time.

    Fail-closed: too few finite windows counts as decay (cannot prove stability).
    """
    series = tuple(float(item) for item in values if math.isfinite(item))
    if len(series) < 6:
        return True
    rho = spearman_rho(series)
    if not math.isfinite(rho):
        return True
    return rho < STATIC_DECAY_SPEARMAN


def _ranks(values: Sequence[float]) -> tuple[float, ...]:
    ordered = sorted((value, index) for index, value in enumerate(values))
    ranks = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index
        while end + 1 < len(ordered) and ordered[end + 1][0] == ordered[index][0]:
            end += 1
        avg = 0.5 * (index + end) + 1.0
        for cursor in range(index, end + 1):
            ranks[ordered[cursor][1]] = avg
        index = end + 1
    return tuple(ranks)


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    n = len(xs)
    if n != len(ys) or n < 3:
        return math.nan
    mean_x = sum(xs) / float(n)
    mean_y = sum(ys) / float(n)
    num = 0.0
    den_x = 0.0
    den_y = 0.0
    for x_val, y_val in zip(xs, ys, strict=True):
        dx = x_val - mean_x
        dy = y_val - mean_y
        num += dx * dy
        den_x += dx * dx
        den_y += dy * dy
    if den_x <= 1e-18 or den_y <= 1e-18:
        return 0.0
    return num / math.sqrt(den_x * den_y)
