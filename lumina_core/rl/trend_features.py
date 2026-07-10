"""Trend indicator helpers for RL observation enrichment (ADR-0018)."""

from __future__ import annotations

from typing import Any, Callable, Sequence

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
