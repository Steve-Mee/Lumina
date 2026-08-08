"""Numpy-backed trend feature batch helpers (M5)."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, Sequence

import numpy as np

from lumina_core.rl.trend_features_core import (
    ADX_PERIODS,
    ATR_PERIOD,
    DEFAULT_TREND_ADX_THRESHOLD,
    MIN_TREND_LOOKBACK,
    SLOPE_PERIODS,
    _extract_ohlc_from_ticks,
    _normalize_slope,
    _zero_trend_features,
    linear_regression_slope,
    regime_strength_score,
    trend_persistence,
)

def _numpy_true_range(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
) -> np.ndarray:
    n = len(closes)
    if n == 0:
        return np.array([], dtype=np.float64)
    tr = np.empty(n, dtype=np.float64)
    tr[0] = max(0.0, highs[0] - lows[0])
    prev_close = closes[0]
    for i in range(1, n):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - prev_close),
            abs(lows[i] - prev_close),
        )
        prev_close = closes[i]
    return tr


def _numpy_rolling_mean(values: np.ndarray, period: int) -> np.ndarray:
    if len(values) == 0:
        return np.array([], dtype=np.float64)
    window = max(1, period)
    if len(values) < window:
        return np.full(len(values), np.nan, dtype=np.float64)
    kernel = np.ones(window, dtype=np.float64) / float(window)
    rolled = np.convolve(values, kernel, mode="valid")
    prefix = np.full(window - 1, np.nan, dtype=np.float64)
    return np.concatenate([prefix, rolled])


def _numpy_ewm(values: np.ndarray, period: int) -> np.ndarray:
    if len(values) == 0:
        return np.array([], dtype=np.float64)
    alpha = 1.0 / max(1, period)
    out = np.empty(len(values), dtype=np.float64)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1.0 - alpha) * out[i - 1]
    return out


def _numpy_adx_last(
    highs: np.ndarray,
    lows: np.ndarray,
    tr: np.ndarray,
    period: int,
) -> float:
    if len(tr) < period + 1:
        return 0.0
    atr = _numpy_rolling_mean(tr, period)
    up = np.maximum(highs - np.roll(highs, 1), 0.0)
    down = np.maximum(np.roll(lows, 1) - lows, 0.0)
    up[0] = 0.0
    down[0] = 0.0
    atr_safe = np.where(atr > 0, atr, np.nan)
    plus_di = 100.0 * (_numpy_ewm(up, period) / atr_safe)
    minus_di = 100.0 * (_numpy_ewm(down, period) / atr_safe)
    denom = plus_di + minus_di
    dx = 100.0 * np.abs(plus_di - minus_di) / np.where(denom > 0, denom, np.nan)
    adx = _numpy_rolling_mean(dx, period)
    val = float(adx[-1]) if len(adx) else 0.0
    return val if np.isfinite(val) else 0.0


def _build_trend_feature_dict(
    *,
    price: float,
    w_close: np.ndarray,
    w_high: np.ndarray,
    w_low: np.ndarray,
    w_tr: np.ndarray,
    slopes_at_index: dict[int, float],
    trend_adx_threshold: float = DEFAULT_TREND_ADX_THRESHOLD,
) -> dict[str, float]:
    if price <= 0:
        return _zero_trend_features()

    atr_series = _numpy_rolling_mean(w_tr, ATR_PERIOD)
    atr = float(atr_series[-1]) if len(atr_series) else 0.0
    if not np.isfinite(atr):
        atr = 0.0

    adx_raw = {period: _numpy_adx_last(w_high, w_low, w_tr, period) for period in ADX_PERIODS}
    mean_price = float(np.mean(w_close[-60:])) if len(w_close) >= 1 else price
    slope_norm = {
        period: _normalize_slope(slopes_at_index.get(period, 0.0), mean_price) for period in SLOPE_PERIODS
    }
    direction, duration_norm = trend_persistence(w_close)

    atr_norm = atr / price if price > 0 else 0.0

    atr_ratio = 0.0
    recent_atr = atr_series[-MIN_TREND_LOOKBACK:]
    recent_atr = recent_atr[np.isfinite(recent_atr)]
    if len(recent_atr) > 0 and atr > 0:
        mean_atr = float(recent_atr.mean())
        if mean_atr > 1e-12:
            atr_ratio = float(np.clip(atr / mean_atr, 0.0, 3.0) / 3.0)

    regime_strength = regime_strength_score(
        adx_14=adx_raw[14],
        slope_15=slope_norm[15],
        direction=direction,
        duration_norm=duration_norm,
        trend_threshold=trend_adx_threshold,
    )

    return {
        "trend_regime_strength": regime_strength,
        "trend_adx_7": min(1.0, adx_raw[7] / 100.0),
        "trend_adx_14": min(1.0, adx_raw[14] / 100.0),
        "trend_adx_21": min(1.0, adx_raw[21] / 100.0),
        "trend_slope_5": slope_norm[5],
        "trend_slope_15": slope_norm[15],
        "trend_slope_30": slope_norm[30],
        "trend_slope_60": slope_norm[60],
        "trend_direction": direction,
        "trend_duration_norm": duration_norm,
        "trend_atr_norm": float(atr_norm),
        "trend_atr_ratio": float(atr_ratio),
    }


def _precompute_slopes(closes: np.ndarray) -> dict[int, np.ndarray]:
    from numpy.lib.stride_tricks import sliding_window_view

    n = len(closes)
    out: dict[int, np.ndarray] = {}
    for period in SLOPE_PERIODS:
        arr = np.zeros(n, dtype=np.float64)
        if n < period:
            out[period] = arr
            continue
        windows = sliding_window_view(closes, period)
        x = np.arange(period, dtype=np.float64)
        x_mean = x.mean()
        denom = float(np.sum((x - x_mean) ** 2))
        if denom <= 1e-12:
            out[period] = arr
            continue
        y_mean = windows.mean(axis=1)
        numer = np.sum((x - x_mean) * (windows - y_mean[:, None]), axis=1)
        valid = np.all(windows > 0, axis=1)
        slopes = np.zeros(windows.shape[0], dtype=np.float64)
        slopes[valid] = numer[valid] / denom
        arr[period - 1 :] = slopes
        out[period] = arr
    return out


def compute_trend_features_for_window(
    closes: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    *,
    trend_adx_threshold: float = DEFAULT_TREND_ADX_THRESHOLD,
) -> dict[str, float]:
    close_arr = np.asarray(closes, dtype=np.float64)
    high_arr = np.asarray(highs, dtype=np.float64)
    low_arr = np.asarray(lows, dtype=np.float64)
    if len(close_arr) < 2:
        return _zero_trend_features()

    price = float(close_arr[-1])
    if price <= 0:
        return _zero_trend_features()

    tr = _numpy_true_range(high_arr, low_arr, close_arr)
    slopes_at_index = {
        period: linear_regression_slope(close_arr, period) for period in SLOPE_PERIODS
    }
    return _build_trend_feature_dict(
        price=price,
        w_close=close_arr,
        w_high=high_arr,
        w_low=low_arr,
        w_tr=tr,
        slopes_at_index=slopes_at_index,
        trend_adx_threshold=trend_adx_threshold,
    )


def compute_trend_features_sliding_batch_reference(
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    *,
    lookback: int = MIN_TREND_LOOKBACK,
    on_progress: Callable[[int, int], None] | None = None,
    progress_stride: int = 2000,
) -> list[dict[str, float]]:
    """Reference O(n*lookback) sliding batch — used for golden equivalence tests."""
    n = len(closes)
    out = [_zero_trend_features() for _ in range(n)]
    if n <= lookback:
        return out

    total = n - lookback
    for offset, i in enumerate(range(lookback, n)):
        start = i - lookback
        out[i] = compute_trend_features_for_window(
            closes[start : i + 1],
            highs[start : i + 1],
            lows[start : i + 1],
        )
        if on_progress is not None and progress_stride > 0:
            processed = offset + 1
            if processed == total or processed % progress_stride == 0:
                on_progress(processed, total)
    return out


def compute_trend_features_sliding_batch(
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    *,
    lookback: int = MIN_TREND_LOOKBACK,
    on_progress: Callable[[int, int], None] | None = None,
    progress_stride: int = 2000,
) -> list[dict[str, float]]:
    """Compute per-tick trend features using fixed-size sliding windows (O(n) slopes + TR)."""
    n = len(closes)
    out = [_zero_trend_features() for _ in range(n)]
    if n <= lookback:
        return out

    tr_full = _numpy_true_range(highs, lows, closes)
    slopes_pre = _precompute_slopes(closes)
    effective_stride = progress_stride if n <= 100_000 else max(progress_stride, 5000)
    total = n - lookback

    for offset, i in enumerate(range(lookback, n)):
        w_start = i - lookback
        w_close = closes[w_start : i + 1]
        w_high = highs[w_start : i + 1]
        w_low = lows[w_start : i + 1]
        w_tr = tr_full[w_start : i + 1]
        price = float(closes[i])
        slopes_at_index = {period: float(slopes_pre[period][i]) for period in SLOPE_PERIODS}
        out[i] = _build_trend_feature_dict(
            price=price,
            w_close=w_close,
            w_high=w_high,
            w_low=w_low,
            w_tr=w_tr,
            slopes_at_index=slopes_at_index,
        )
        if on_progress is not None and effective_stride > 0:
            processed = offset + 1
            if processed == total or processed % effective_stride == 0:
                on_progress(processed, total)
    return out


def compute_trend_features_from_ticks(
    ticks: list[dict[str, Any]],
    *,
    trend_adx_threshold: float = DEFAULT_TREND_ADX_THRESHOLD,
) -> dict[str, float]:
    closes, highs, lows = _extract_ohlc_from_ticks(ticks)
    if len(closes) < 2:
        return _zero_trend_features()
    return compute_trend_features_for_window(
        closes,
        highs,
        lows,
        trend_adx_threshold=trend_adx_threshold,
    )


def regime_from_strength(strength: float, *, threshold: float = 0.15) -> str:
    if strength > threshold:
        return "TREND_UP"
    if strength < -threshold:
        return "TREND_DOWN"
    return "NEUTRAL"
