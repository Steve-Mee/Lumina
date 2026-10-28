"""Regime detection may size/throttle. It must not switch strategy."""

from __future__ import annotations

import pytest

from lumina_research.evolution.regime import (
    RegimeObservation,
    RegimePolicy,
    RegimePolicyError,
    detect_regime,
    throttled_quantity,
)
from lumina_research.evolution.types import default_parent


@pytest.mark.unit
def test_high_vol_and_down_trend_throttle_quantity_not_kind() -> None:
    policy = RegimePolicy()
    parent = default_parent()
    high_down = policy.act(RegimeObservation(vol="high", trend="down"))
    low_up = policy.act(RegimeObservation(vol="low", trend="up"))
    assert high_down.throttle is True
    assert high_down.size_multiplier == pytest.approx(0.375)
    assert low_up.throttle is False
    assert low_up.size_multiplier == pytest.approx(1.0)
    qty = throttled_quantity(parent, high_down)
    assert qty < parent.quantity
    assert parent.kind == "planted_edge"


@pytest.mark.unit
def test_strategy_switch_is_refused() -> None:
    policy = RegimePolicy()
    obs = RegimeObservation(vol="high", trend="up")
    with pytest.raises(RegimePolicyError, match="cannot switch strategies"):
        policy.switch_strategy(obs, "mean_reversion")
    with pytest.raises(RegimePolicyError, match="cannot switch strategies"):
        policy.act(obs, strategy_id="trend_follow")
    with pytest.raises(TypeError):

        class _Switched(RegimePolicy):  # type: ignore[misc]
            pass


@pytest.mark.unit
def test_detect_regime_labels_vol_and_trend() -> None:
    high = tuple([0.05, -0.05, 0.06, -0.04] * 20)
    low = tuple([0.001] * 80)
    obs_high = detect_regime(high)
    obs_low = detect_regime(low)
    assert obs_high.vol in {"high", "low"}
    assert obs_low.trend in {"up", "down"}
    short = detect_regime((0.01, -0.01))
    assert short.vol == "low"
    assert short.trend == "up"


@pytest.mark.unit
def test_unknown_regime_labels_fail_closed() -> None:
    policy = RegimePolicy()
    obs = RegimeObservation(vol="low", trend="up")
    object.__setattr__(obs, "vol", "medium")
    with pytest.raises(RegimePolicyError, match="unknown volatility"):
        policy.act(obs)
    obs2 = RegimeObservation(vol="low", trend="up")
    object.__setattr__(obs2, "trend", "sideways")
    with pytest.raises(RegimePolicyError, match="unknown trend"):
        policy.act(obs2)
