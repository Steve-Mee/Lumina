"""Probability of Backtest Overfitting — CSCV logit formulation.

Bailey, Borwein, López de Prado, Zhu (2014), "The Probability of Backtest
Overfitting".

Split the metric matrix (configs × slices) into all combinations that assign
S/2 slices to IS and the rest to OOS. For each combination, take the IS-best
config and look at its relative OOS rank ω ∈ (0, 1). The logit is
λ = ln(ω / (1-ω)). PBO is the share of combinations with λ < 0, which is
exactly the share where the IS-best config scores below the median OOS.

A single config cannot estimate PBO (doubt = reject at the gate).
"""

from __future__ import annotations

import itertools
import math
import statistics
from typing import Sequence

from lumina_research.validation.types import PBOSnapshot

PBO_FORMULATION = "cscv_logit_bailey_2014"


class PBOError(ValueError):
    """PBO/CSCV cannot be formed from the score matrix."""


def probability_of_backtest_overfitting(
    scores: Sequence[Sequence[float]],
    *,
    n_slices: int | None = None,
) -> PBOSnapshot:
    """`scores[config][slice]` performance (higher is better), even number of slices."""
    matrix = tuple(tuple(float(value) for value in row) for row in scores)
    if len(matrix) < 2:
        raise PBOError("PBO requires at least 2 configs; a single trial is uninformative")
    width = len(matrix[0])
    if width < 4 or width % 2 != 0:
        raise PBOError("CSCV requires an even n_slices >= 4")
    if any(len(row) != width for row in matrix):
        raise PBOError("all configs must have the same number of slices")
    if any(not math.isfinite(value) for row in matrix for value in row):
        raise PBOError("PBO scores must be finite")
    if n_slices is not None and n_slices != width:
        raise PBOError("n_slices does not match the score matrix")
    k = width // 2
    n_configs = len(matrix)
    n_below = 0
    logits: list[float] = []
    combinations = tuple(itertools.combinations(range(width), k))
    for is_idx in combinations:
        oos_idx = tuple(index for index in range(width) if index not in is_idx)
        is_scores = [_mean_at(row, is_idx) for row in matrix]
        oos_scores = [_mean_at(row, oos_idx) for row in matrix]
        best_is = _argmax(is_scores)
        omega = _relative_rank(oos_scores, best_is)
        logit = math.log(omega / (1.0 - omega))
        logits.append(logit)
        oos_median = float(statistics.median(oos_scores))
        if oos_scores[best_is] < oos_median:
            n_below += 1
    n_combinations = len(combinations)
    pbo = n_below / float(n_combinations)
    return PBOSnapshot(
        pbo=float(pbo),
        n_slices=width,
        n_combinations=n_combinations,
        n_configs=n_configs,
        n_below_median=n_below,
        formulation=PBO_FORMULATION,
        logit_mean=float(statistics.fmean(logits)),
    )


def slice_series(returns: Sequence[float], n_slices: int) -> tuple[float, ...]:
    """Mean return per contiguous slice. Used to build the CSCV matrix."""
    if n_slices < 4 or n_slices % 2 != 0:
        raise PBOError("n_slices must be even and >= 4")
    series = tuple(float(item) for item in returns)
    if len(series) < n_slices:
        raise PBOError("not enough observations to form CSCV slices")
    width, remainder = divmod(len(series), n_slices)
    means: list[float] = []
    cursor = 0
    for slice_id in range(n_slices):
        extra = 1 if slice_id < remainder else 0
        end = cursor + width + extra
        chunk = series[cursor:end]
        if not chunk:
            raise PBOError("empty CSCV slice")
        means.append(float(statistics.fmean(chunk)))
        cursor = end
    return tuple(means)


def _mean_at(row: Sequence[float], indices: Sequence[int]) -> float:
    return float(statistics.fmean(row[index] for index in indices))


def _argmax(values: Sequence[float]) -> int:
    best_index = 0
    best_value = values[0]
    for index, value in enumerate(values):
        if value > best_value:
            best_value = value
            best_index = index
    return best_index


def _relative_rank(oos_scores: Sequence[float], selected: int) -> float:
    """Performance percentile of the IS-best config on OOS, mapped to (0, 1).

    Higher ω = better OOS. PBO = share of combinations with ω < 0.5, i.e. the
    IS-best config scores below the median OOS. Ties are broken pessimistically
    (the selected config does not outrank equals).
    """
    selected_score = oos_scores[selected]
    n = len(oos_scores)
    n_strictly_worse = sum(1 for value in oos_scores if value < selected_score)
    omega = (n_strictly_worse + 1) / (n + 1)
    if omega <= 0.0 or omega >= 1.0:
        raise PBOError("relative rank must lie in (0, 1)")
    return float(omega)
