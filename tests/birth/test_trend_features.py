from __future__ import annotations

import numpy as np
import pytest

from lumina_core.rl.trend_features import (
    compute_adx,
    compute_atr,
    compute_trend_features_for_window,
    linear_regression_slope,
    regime_from_strength,
    regime_strength_score,
    trend_persistence,
)


def _rising_closes(n: int, start: float = 5000.0, step: float = 2.0) -> tuple[list[float], list[float], list[float]]:
    closes = [start + i * step for i in range(n)]
    return closes, closes, closes


def _flat_closes(n: int, price: float = 5000.0) -> tuple[list[float], list[float], list[float]]:
    closes = [price] * n
    return closes, closes, closes


@pytest.mark.unit
def test_linear_regression_slope_rising_is_positive() -> None:
    closes, _, _ = _rising_closes(20)
    slope = linear_regression_slope(closes, 15)
    assert slope > 0


@pytest.mark.unit
def test_linear_regression_slope_flat_is_near_zero() -> None:
    closes, _, _ = _flat_closes(20)
    slope = linear_regression_slope(closes, 15)
    assert abs(slope) < 1e-6


@pytest.mark.unit
def test_trend_persistence_rising_series() -> None:
    closes, _, _ = _rising_closes(30)
    direction, duration = trend_persistence(closes)
    assert direction == 1.0
    assert duration > 0.0


@pytest.mark.unit
def test_compute_adx_and_atr_on_rising_series() -> None:
    closes, highs, lows = _rising_closes(80)
    adx = compute_adx(highs, lows, closes, 14)
    atr = compute_atr(highs, lows, closes, 14)
    assert adx >= 0.0
    assert atr > 0.0


@pytest.mark.unit
def test_regime_strength_positive_on_uptrend() -> None:
    strength = regime_strength_score(
        adx_14=30.0,
        slope_15=0.5,
        direction=1.0,
        duration_norm=0.8,
        trend_threshold=23.0,
    )
    assert strength > 0.0
    assert strength <= 1.0


@pytest.mark.unit
def test_compute_trend_features_rising_window() -> None:
    closes, highs, lows = _rising_closes(80)
    features = compute_trend_features_for_window(closes, highs, lows)
    assert features["trend_slope_15"] > 0
    assert features["trend_slope_60"] > 0
    assert features["trend_direction"] == 1.0
    assert features["trend_adx_14"] >= 0.0
    assert -1.0 <= features["trend_regime_strength"] <= 1.0


@pytest.mark.unit
def test_regime_from_strength_thresholds() -> None:
    assert regime_from_strength(0.5) == "TREND_UP"
    assert regime_from_strength(-0.5) == "TREND_DOWN"
    assert regime_from_strength(0.05) == "NEUTRAL"


@pytest.mark.unit
def test_short_window_returns_zeros() -> None:
    closes, highs, lows = _rising_closes(1)
    features = compute_trend_features_for_window(closes, highs, lows)
    assert features["trend_regime_strength"] == 0.0
    assert features["trend_slope_60"] == 0.0
