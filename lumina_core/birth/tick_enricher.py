"""Enrich tick rows with regime and session metadata for birth SIM."""

from __future__ import annotations

from typing import Any, Callable

from pathlib import Path

import numpy as np

from lumina_core.birth.enrichment_cache import (
    finalize_enrichment_cache,
    try_apply_enrichment_cache,
)
from lumina_core.birth.data_source_honesty import real_data_percentage
from lumina_core.rl.trend_features import (
    ENRICH_VERSION,
    MIN_TREND_LOOKBACK,
    compute_trend_features_sliding_batch,
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


def _extract_ohlc_arrays(ticks: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(ticks)
    closes = np.empty(n, dtype=np.float64)
    highs = np.empty(n, dtype=np.float64)
    lows = np.empty(n, dtype=np.float64)
    for i, tick in enumerate(ticks):
        try:
            close = float(tick.get("close", tick.get("last", 0.0)) or 0.0)
        except (TypeError, ValueError):
            close = 0.0
        if close <= 0:
            close = 0.0
        try:
            high = float(tick.get("high", close) or close)
        except (TypeError, ValueError):
            high = close
        try:
            low = float(tick.get("low", close) or close)
        except (TypeError, ValueError):
            low = close
        closes[i] = close
        highs[i] = max(high, close)
        lows[i] = min(low, close)
    return closes, highs, lows


def enrich_ticks_for_sim(
    ticks: list[dict[str, Any]],
    *,
    on_progress: Callable[[int, int], None] | None = None,
    workspace_root: Path | str | None = None,
    raw_ticks_hash: str | None = None,
    enrich_version: str = ENRICH_VERSION,
) -> list[dict[str, Any]]:
    if not ticks:
        return ticks

    if workspace_root is not None and try_apply_enrichment_cache(
        workspace_root,
        ticks,
        raw_ticks_hash=raw_ticks_hash,
        enrich_version=enrich_version,
    ):
        return ticks

    closes, highs, lows = _extract_ohlc_arrays(ticks)
    for i, tick in enumerate(ticks):
        price = closes[i]
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

    feature_rows = compute_trend_features_sliding_batch(
        closes,
        highs,
        lows,
        on_progress=on_progress,
    )
    for i in range(MIN_TREND_LOOKBACK, len(ticks)):
        if closes[i] <= 0:
            continue
        tick = ticks[i]
        tick.update(feature_rows[i])
        tick["regime"] = regime_from_strength(float(feature_rows[i].get("trend_regime_strength", 0.0) or 0.0))
    if workspace_root is not None:
        finalize_enrichment_cache(
            workspace_root,
            ticks,
            raw_ticks_hash=raw_ticks_hash,
            enrich_version=enrich_version,
        )
    return ticks


__all__ = ["enrich_ticks_for_sim", "real_data_percentage"]
