"""CSCV logit PBO: IS-best below median OOS."""

from __future__ import annotations

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
    # Best IS half is worst OOS half for every split of first-4 vs last-4 style.
    scores = [
        [10.0, 10.0, 10.0, 10.0, -10.0, -10.0, -10.0, -10.0],
        [-10.0, -10.0, -10.0, -10.0, 10.0, 10.0, 10.0, 10.0],
        [1.0, 1.0, 1.0, 1.0, -1.0, -1.0, -1.0, -1.0],
        [-1.0, -1.0, -1.0, -1.0, 1.0, 1.0, 1.0, 1.0],
    ]
    result = probability_of_backtest_overfitting(scores)
    assert result.pbo > 0.50


@pytest.mark.unit
def test_single_config_cannot_estimate_pbo() -> None:
    with pytest.raises(PBOError, match="at least 2 configs"):
        probability_of_backtest_overfitting([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]])
