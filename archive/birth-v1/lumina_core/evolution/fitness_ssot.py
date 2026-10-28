"""Truthful multi-day fitness SSOT — RNG/proxy is test-only.

Production SIM evolution must use historical ticks + true backtest.
Missing market data is fail-closed (fitness = -inf), never a silent RNG win.
"""
from __future__ import annotations

import os
from typing import Any

from lumina_core.evolution.multi_day_sim_types import ShadowFill, SimResult


def heuristic_fitness_allowed(*, runner_flag: bool = False) -> bool:
    """True only for explicit test/lab opt-in. Production stays fail-closed."""
    if runner_flag:
        return True
    raw = str(os.environ.get("LUMINA_ALLOW_RNG_FITNESS", "") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def fail_closed_sim_result(
    *,
    dna_hash: str,
    days: int,
    shadow_mode: bool,
    reason: str,
) -> SimResult:
    _ = reason
    return SimResult(
        dna_hash=dna_hash,
        day_count=days,
        avg_pnl=0.0,
        max_drawdown_ratio=0.0,
        regime_fit_bonus=0.0,
        fitness=float("-inf"),
        shadow_mode=shadow_mode,
        hypothetical_fills=[] if shadow_mode else None,
    )


def rng_heuristic_daily_pnl(
    *,
    days: int,
    base_pnl: float,
    base_drawdown_abs: float,
    baseline_equity: float,
    rng: Any,
    shadow_mode: bool,
) -> tuple[list[float], float, list[ShadowFill]]:
    """Legacy RNG perturbation — callers must already have heuristic_fitness_allowed()."""
    pnl_values: list[float] = []
    max_drawdown_ratio = 0.0
    fills: list[ShadowFill] = []
    for day_index in range(1, days + 1):
        day_pnl = base_pnl * (1.0 + rng.uniform(-0.2, 0.2))
        day_dd_abs = base_drawdown_abs * (1.0 + rng.uniform(-0.15, 0.15))
        day_dd_ratio = max(0.0, day_dd_abs / baseline_equity)
        pnl_values.append(day_pnl)
        max_drawdown_ratio = max(max_drawdown_ratio, day_dd_ratio)
        if shadow_mode:
            side = "BUY" if day_pnl >= 0.0 else "SELL"
            qty = max(1, int(abs(day_pnl) // 25) + 1)
            entry_price = round(100.0 + rng.uniform(-3.0, 3.0), 4)
            exit_price = round(entry_price + (day_pnl / max(1, qty * 10.0)), 4)
            fills.append(
                ShadowFill(
                    day_index=day_index,
                    side=side,
                    qty=qty,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    pnl=float(day_pnl),
                    reason="shadow_validation_no_order_execution",
                )
            )
    return pnl_values, max_drawdown_ratio, fills


class BirthTickCacheMarketData:
    """MDS adapter over Birth historical tick cache (truthful post-birth SIM)."""

    def __init__(self, ticks: list[dict[str, Any]]) -> None:
        self._ticks = list(ticks)

    def load_historical_ohlc_extended(self, **_kwargs: Any) -> list[dict[str, Any]]:
        return list(self._ticks)


def birth_tick_cache_mds(workspace_root: Any) -> BirthTickCacheMarketData | None:
    try:
        from lumina_core.birth.tick_cache_persist import load_ticks_cache

        ticks = load_ticks_cache(workspace_root)
    except Exception:
        return None
    if not ticks:
        return None
    return BirthTickCacheMarketData(ticks)
