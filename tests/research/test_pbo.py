"""CSCV logit PBO: IS-best below median OOS."""

from __future__ import annotations

import itertools
import statistics

import pytest

from lumina_research.validation.pbo import PBOError, probability_of_backtest_overfitting


@pytest.mark.unit
def test_stable_ranking_has_low_pbo() -> None:
    # 4 configs × 8 slices. Config 0 strictly dominates every slice.
    scores = [
        [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0],
        [5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0],
        [2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0],
        [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    ]
    result = probability_of_backtest_overfitting(scores)
    assert result.formulation == "cscv_logit_bailey_2014"
    assert result.pbo == 0.0
    assert result.n_configs == 4
    assert result.n_slices == 8


@pytest.mark.unit
def test_anti_correlated_is_oos_has_high_pbo() -> None:
    # Each config wins exactly one slice and loses the rest: the IS-best is
    # below the OOS median on every CSCV split (literal-median PBO = 1).
    scores = [[10.0 if slice_id == cfg else -1.0 for slice_id in range(8)] for cfg in range(8)]
    result = probability_of_backtest_overfitting(scores)
    assert result.pbo > 0.50
    assert result.pbo == pytest.approx(1.0)


@pytest.mark.unit
def test_single_config_cannot_estimate_pbo() -> None:
    with pytest.raises(PBOError, match="at least 2 configs"):
        probability_of_backtest_overfitting([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]])


@pytest.mark.unit
def test_pbo_equals_share_of_is_best_below_median_oos() -> None:
    scores = [
        [10.0, 9.0, 8.0, 1.0, 0.0, -1.0, -2.0, -3.0],
        [0.0, 1.0, 2.0, 3.0, 10.0, 9.0, 8.0, 7.0],
        [4.0, 4.0, 4.0, 4.0, 4.0, 4.0, 4.0, 4.0],
        [3.0, 5.0, 2.0, 6.0, 1.0, 7.0, 0.0, 8.0],
    ]
    result = probability_of_backtest_overfitting(scores)
    width = 8
    k = 4
    n_below = 0
    n_combos = 0
    for is_idx in itertools.combinations(range(width), k):
        oos_idx = tuple(index for index in range(width) if index not in is_idx)
        is_scores = [statistics.fmean(row[i] for i in is_idx) for row in scores]
        oos_scores = [statistics.fmean(row[i] for i in oos_idx) for row in scores]
        best = max(range(len(is_scores)), key=lambda i: is_scores[i])
        n_combos += 1
        if oos_scores[best] < statistics.median(oos_scores):
            n_below += 1
    assert n_combos == result.n_combinations
    assert result.pbo == pytest.approx(n_below / float(n_combos))
    assert result.n_below_median == n_below
