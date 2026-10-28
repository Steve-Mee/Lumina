"""Peek next-tick paper MAE/MFE for PATH_SHAPE K3 DEAD. Does not write stash."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.sim_runner_entry_telem import tick_hl


def _peek_excursion_usd(
    stash: dict[str, Any],
    tick: dict[str, Any] | None,
) -> tuple[float | None, float | None]:
    """Identical pnl_h/pnl_l math as apply_open_excursion. No stash writes."""
    prev_mae = stash.get("mae_usd")
    prev_mfe = stash.get("mfe_usd")
    if not isinstance(tick, dict):
        return prev_mae if prev_mae is None else float(prev_mae), (prev_mfe if prev_mfe is None else float(prev_mfe))
    hl = tick_hl(tick)
    if hl is None:
        return prev_mae if prev_mae is None else float(prev_mae), (prev_mfe if prev_mfe is None else float(prev_mfe))
    high, low = hl
    try:
        entry = float(stash.get("entry_price") or 0.0)
        side = int(stash.get("side") or 0)
    except (TypeError, ValueError):
        return prev_mae if prev_mae is None else float(prev_mae), (prev_mfe if prev_mfe is None else float(prev_mfe))
    if side == 0 or entry <= 0.0:
        return prev_mae if prev_mae is None else float(prev_mae), (prev_mfe if prev_mfe is None else float(prev_mfe))
    from lumina_core.birth.notional_cap import birth_gym_point_value

    pv = float(birth_gym_point_value())
    pnl_h = (high - entry) * float(side) * 1.0 * pv
    pnl_l = (low - entry) * float(side) * 1.0 * pv
    adverse = min(0.0, min(pnl_h, pnl_l))
    favorable = max(0.0, max(pnl_h, pnl_l))
    peek_mae = adverse if prev_mae is None else min(float(prev_mae), adverse)
    peek_mfe = favorable if prev_mfe is None else max(float(prev_mfe), favorable)
    return peek_mae, peek_mfe


def _r_from_usd(usd: float | None, intended: float | None) -> float | None:
    if usd is None or intended is None:
        return None
    try:
        denom = float(intended)
        if denom <= 0.0:
            return None
        return float(usd) / denom
    except (TypeError, ValueError):
        return None


__all__ = ["_peek_excursion_usd", "_r_from_usd"]
