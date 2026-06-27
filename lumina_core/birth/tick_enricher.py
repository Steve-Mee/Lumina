"""Enrich tick rows with regime and session metadata for birth SIM."""

from __future__ import annotations

from typing import Any

from lumina_core.rl.trend_features import (
    MIN_TREND_LOOKBACK,
    compute_trend_features_from_ticks,
    regime_from_strength,
)

_IMBALANCE_LOOKBACK = 20


def _apply_zero_trend_defaults(tick: dict[str, Any]) -> None:
    tick.setdefault("trend_regime_strength", 0.0)
    tick.setdefault("trend_adx_7", 0.0)
    tick.setdefault("trend_adx_14", 0.0)
    tick.setdefault("trend_adx_21", 0.0)
    tick.setdefault("trend_slope_5", 0.0)
    tick.setdefault("trend_slope_15", 0.0)
    tick.setdefault("trend_slope_30", 0.0)
    tick.setdefault("trend_slope_60", 0.0)
    tick.setdefault("trend_direction", 0.0)
    tick.setdefault("trend_duration_norm", 0.0)
    tick.setdefault("trend_atr_norm", 0.0)
    tick.setdefault("trend_atr_ratio", 0.0)


def enrich_ticks_for_sim(ticks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not ticks:
        return ticks
    for i, tick in enumerate(ticks):
        try:
            price = float(tick.get("last", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        bid = float(tick.get("bid", price - 0.125) or price - 0.125)
        ask = float(tick.get("ask", price + 0.125) or price + 0.125)
        spread = max(0.25, ask - bid)
        tick["imbalance"] = max(0.5, min(2.0, 1.0 + (ask - bid) / spread * 0.15))
        tick["bar_index"] = i

        if i < MIN_TREND_LOOKBACK:
            tick["regime"] = str(tick.get("regime", "NEUTRAL"))
            _apply_zero_trend_defaults(tick)
            continue

        window = ticks[max(0, i - MIN_TREND_LOOKBACK) : i + 1]
        features = compute_trend_features_from_ticks(window)
        tick.update(features)
        tick["regime"] = regime_from_strength(float(features.get("trend_regime_strength", 0.0) or 0.0))
    return ticks


def real_data_percentage(ticks: list[dict[str, Any]]) -> float:
    if not ticks:
        return 0.0
    real = sum(1 for t in ticks if str(t.get("source", "")).lower().startswith("real"))
    return round((float(real) / float(len(ticks))) * 100.0, 3)
