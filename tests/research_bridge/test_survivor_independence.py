"""D11: both family and corr < 0.5 required. 0.5 is not independent."""

from __future__ import annotations

import pytest

from lumina_core.research_bridge.independence import CORR_STRICT_MAX, d11_independent, pairwise_correlation


@pytest.mark.unit
def test_same_family_low_corr_not_independent() -> None:
    ok, reason = d11_independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="trend",
        config_id="c1",
        other_config_id="c2",
        left_returns=(0.01, -0.02, 0.03, -0.01, 0.02, -0.03, 0.01, -0.02),
        right_returns=(0.0, 0.01, -0.01, 0.02, -0.02, 0.0, 0.01, -0.01),
    )
    assert ok is False
    assert reason == "survivors_same_family"


@pytest.mark.unit
def test_different_family_high_corr_not_independent() -> None:
    series = (0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08)
    ok, reason = d11_independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="c1",
        other_config_id="c2",
        left_returns=series,
        right_returns=series,
    )
    assert ok is False
    assert reason == "survivors_corr_not_independent"


@pytest.mark.unit
def test_different_family_low_corr_independent() -> None:
    left = (1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0)
    right = (0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0)
    corr, status = pairwise_correlation(left, right)
    assert status == "ok"
    assert corr is not None and corr < CORR_STRICT_MAX
    ok, reason = d11_independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="c1",
        other_config_id="c2",
        left_returns=left,
        right_returns=right,
    )
    assert ok is True
    assert reason == "independent"


@pytest.mark.unit
def test_missing_series_unavailable() -> None:
    ok, reason = d11_independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="c1",
        other_config_id="c2",
        left_returns=None,
        right_returns=(0.1,) * 8,
    )
    assert ok is False
    assert reason == "survivors_corr_unavailable"


@pytest.mark.unit
def test_threshold_is_strictly_less_than_half() -> None:
    ok, reason = d11_independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="c1",
        other_config_id="c2",
        left_returns=(0.0,) * 8,
        right_returns=(1.0,) * 8,
        correlation=0.5,
    )
    assert ok is False
    assert reason == "survivors_corr_not_independent"
    ok, reason = d11_independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="c1",
        other_config_id="c2",
        left_returns=(0.0,) * 8,
        right_returns=(1.0,) * 8,
        correlation=0.499,
    )
    assert ok is True
