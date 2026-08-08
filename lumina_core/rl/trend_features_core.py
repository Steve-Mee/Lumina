"""Trend indicator helpers for RL observation enrichment (ADR-0018)."""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd

MIN_TREND_LOOKBACK = 60
DEFAULT_TREND_ADX_THRESHOLD = 23.0
ENRICH_VERSION = "trend_features_v1"
SLOPE_PERIODS = (5, 15, 30, 60)
ADX_PERIODS = (7, 14, 21)
ATR_PERIOD = 14

_TREND_FEATURE_KEYS = (
    "trend_regime_strength",
    "trend_adx_7",
    "trend_adx_14",
    "trend_adx_21",
    "trend_slope_5",
    "trend_slope_15",
    "trend_slope_30",
    "trend_slope_60",
    "trend_direction",
    "trend_duration_norm",
    "trend_atr_norm",
    "trend_atr_ratio",
)


def _to_float_series(values: Sequence[float]) -> pd.Series:
    return pd.Series(np.asarray(values, dtype=np.float64))


def _true_range_series(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
) -> pd.Series:
    high = _to_float_series(highs)
    low = _to_float_series(lows)
    close = _to_float_series(closes)
    return pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)


def _extract_ohlc_from_ticks(ticks: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    closes: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    for tick in ticks:
        try:
            close = float(tick.get("close", tick.get("last", 0.0)) or 0.0)
        except (TypeError, ValueError):
            close = 0.0
        if close <= 0:
            continue
        try:
            high = float(tick.get("high", close) or close)
        except (TypeError, ValueError):
            high = close
        try:
            low = float(tick.get("low", close) or close)
        except (TypeError, ValueError):
            low = close
        closes.append(close)
        highs.append(max(high, close))
        lows.append(min(low, close))
    if not closes:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64), np.array([], dtype=np.float64)
    return (
        np.asarray(closes, dtype=np.float64),
        np.asarray(highs, dtype=np.float64),
        np.asarray(lows, dtype=np.float64),
    )


def compute_atr(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int = ATR_PERIOD) -> float:
    if len(closes) < 2:
        return 0.0
    tr = _true_range_series(highs, lows, closes)
    atr = tr.rolling(max(1, period)).mean()
    val = float(atr.iloc[-1]) if len(atr) else 0.0
    return val if np.isfinite(val) else 0.0


def _adx_from_tr(
    highs: Sequence[float],
    lows: Sequence[float],
    tr: pd.Series,
    period: int,
) -> float:
    if len(tr) < period + 1:
        return 0.0
    high = _to_float_series(highs)
    low = _to_float_series(lows)
    atr = tr.rolling(period).mean()
    up = (high - high.shift()).clip(lower=0)
    down = (low.shift() - low).clip(lower=0)
    plus_di = 100 * (up.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan))
    minus_di = 100 * (down.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan))
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.rolling(period).mean()
    val = float(adx.iloc[-1]) if len(adx) else 0.0
    return val if np.isfinite(val) else 0.0


def compute_adx(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int,
) -> float:
    if len(closes) < period + 1:
        return 0.0
    tr = _true_range_series(highs, lows, closes)
    return _adx_from_tr(highs, lows, tr, period)


def linear_regression_slope(closes: Sequence[float], period: int) -> float:
    if len(closes) < period or period < 2:
        return 0.0
    window = np.asarray(closes[-period:], dtype=np.float64)
    if np.any(window <= 0):
        return 0.0
    x = np.arange(period, dtype=np.float64)
    x_mean = x.mean()
    y_mean = window.mean()
    denom = float(np.sum((x - x_mean) ** 2))
    if denom <= 1e-12:
        return 0.0
    slope = float(np.sum((x - x_mean) * (window - y_mean)) / denom)
    return slope


def _normalize_slope(slope: float, mean_price: float) -> float:
    if mean_price <= 0:
        return 0.0
    normalized = (slope / mean_price) * 1000.0
    return float(np.clip(normalized, -1.0, 1.0))


def trend_persistence(closes: Sequence[float], *, max_duration: int = MIN_TREND_LOOKBACK) -> tuple[float, float]:
    if len(closes) < 3:
        return 0.0, 0.0
    arr = np.asarray(closes, dtype=np.float64)
    deltas = np.diff(arr)
    direction = 0.0
    if len(deltas) == 0:
        return 0.0, 0.0
    last_delta = float(deltas[-1])
    if last_delta > 0:
        direction = 1.0
    elif last_delta < 0:
        direction = -1.0
    duration = 0
    for delta in reversed(deltas):
        if direction > 0 and delta > 0:
            duration += 1
        elif direction < 0 and delta < 0:
            duration += 1
        elif direction == 0:
            break
        else:
            break
    duration_norm = float(min(1.0, duration / max(1, max_duration)))
    return direction, duration_norm


def regime_strength_score(
    *,
    adx_14: float,
    slope_15: float,
    direction: float,
    duration_norm: float,
    trend_threshold: float = DEFAULT_TREND_ADX_THRESHOLD,
) -> float:
    threshold = max(1.0, float(trend_threshold))
    adx_component = min(1.0, adx_14 / threshold)
    slope_component = min(1.0, abs(slope_15) * 500.0)
    sign = float(np.sign(slope_15)) if slope_15 != 0 else direction
    strength = sign * adx_component * (0.5 + 0.5 * duration_norm) * slope_component
    return float(np.clip(strength, -1.0, 1.0))


def _zero_trend_features() -> dict[str, float]:
    return {key: 0.0 for key in _TREND_FEATURE_KEYS}


