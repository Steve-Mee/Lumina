"""Enrich tick rows with regime and session metadata for birth SIM."""

from __future__ import annotations

from typing import Any


def enrich_ticks_for_sim(ticks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not ticks:
        return ticks
    lookback = 20
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
        if i < lookback:
            tick["regime"] = str(tick.get("regime", "NEUTRAL"))
            continue
        window_start = max(0, i - lookback)
        start_price = float(ticks[window_start].get("last", price) or price)
        if start_price <= 0:
            tick["regime"] = "NEUTRAL"
            continue
        ret = (price - start_price) / start_price
        if ret > 0.0015:
            tick["regime"] = "TREND_UP"
        elif ret < -0.0015:
            tick["regime"] = "TREND_DOWN"
        else:
            tick["regime"] = "NEUTRAL"
        tick["bar_index"] = i
    return ticks


def real_data_percentage(ticks: list[dict[str, Any]]) -> float:
    if not ticks:
        return 0.0
    real = sum(1 for t in ticks if str(t.get("source", "")).lower().startswith("real"))
    return round((float(real) / float(len(ticks))) * 100.0, 3)
