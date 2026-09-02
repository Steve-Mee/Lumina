"""PnL increment units for Birth drawdown yardsticks.

``sim_runner`` appends ``rl_close_accounting_net_usd`` — already USD.
Do not convert that live series again. This helper is the SSOT multiplier
for point-like increments (tests / stray paths). Birth geometry uses
``MES_POINT_VALUE_USD`` (same constant as ``intended_risk_usd``), not a
guessed NQ $20.
"""

from __future__ import annotations

from lumina_core.birth.birth_trade_geometry import MES_POINT_VALUE_USD

# Live sim_runner settlement is already USD (gym ``rl_close_accounting_net_usd``).
SIM_RUNNER_PNL_ALREADY_USD = True
# File:line of the live append: lumina_core/birth/sim_runner.py:653-659
POINT_TO_USD = float(MES_POINT_VALUE_USD)


def pnl_increments_to_usd(
    series: list[float],
    *,
    unit: str = "usd",
) -> list[float]:
    """Convert increments to USD once. Identity when ``unit`` is already USD."""
    raw = [float(x) for x in series]
    key = str(unit or "usd").strip().lower()
    if key in {"usd", "dollar", "dollars"}:
        return raw
    if key in {"points", "point", "nq_points", "mes_points"}:
        return [x * POINT_TO_USD for x in raw]
    if key in {"ticks", "tick"}:
        return [x * 0.25 * POINT_TO_USD for x in raw]
    return raw


__all__ = [
    "POINT_TO_USD",
    "SIM_RUNNER_PNL_ALREADY_USD",
    "pnl_increments_to_usd",
]
