"""Birth-SIM close booking: clip exam PnL, attach replayable close fields."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.notional_cap import (
    birth_close_cap_usd,
    clip_birth_exam_pnl,
)


def book_birth_close_net_usd(
    raw_net_usd: float,
    *,
    is_birth: bool,
    trade_closed: bool,
    entry_price: float,
    qty: int,
) -> tuple[float, float]:
    """Return (booked_net, cap_usd). Non-birth or open bars pass through raw."""
    raw = float(raw_net_usd)
    if not (is_birth and trade_closed):
        return raw, 0.0
    # Exam qty is 1 in birth SIM even if a leak tried to size up.
    cap = birth_close_cap_usd(entry_price=float(entry_price), qty=1)
    return clip_birth_exam_pnl(raw, entry_price=float(entry_price), qty=1), cap


def gym_step_info(
    *,
    realized_pnl: float,
    booked_net: float,
    training_reward: float,
    slippage_cost: float,
    fees_cost: float,
    equity: float,
    drawdown: float,
    sharpe: float,
    var_es_penalty: float,
    reward_components: dict[str, float],
    trade_closed: bool,
    close_reason: str,
    entry_stop_pct: float,
    entry_target_pct: float,
    blocked_by_capital_preservation: bool,
    block_reason: str,
    qty: int,
    risk_usd: float,
    cap_usd: float,
    gap: bool,
    entry_price: float,
    point_value: float,
) -> dict[str, Any]:
    trade_r = (
        float(booked_net) / max(float(risk_usd), 1e-9)
        if trade_closed and float(risk_usd) > 0.0
        else None
    )
    return {
        "model_close_gross_pnl_usd": realized_pnl,
        "rl_close_accounting_net_usd": booked_net,
        "training_reward": training_reward,
        "slippage_cost": slippage_cost,
        "fees_cost": fees_cost,
        "equity": equity,
        "drawdown": drawdown,
        "sharpe": sharpe,
        "var_es_penalty": var_es_penalty,
        "reward_components": reward_components,
        "trade_closed": trade_closed,
        "close_reason": close_reason,
        "entry_stop_pct": entry_stop_pct,
        "entry_target_pct": entry_target_pct,
        "blocked_by_capital_preservation": blocked_by_capital_preservation,
        "block_reason": block_reason,
        "qty": qty,
        "risk_usd": risk_usd if trade_closed else 0.0,
        "trade_r": trade_r,
        "cap_usd": cap_usd,
        "gap": bool(gap),
        "entry_price": entry_price,
        "point_value": point_value,
    }


def birth_close_info_fields(
    *,
    booked_net: float,
    cap_usd: float,
    qty: int,
    gap: bool,
    close_reason: str,
    entry_price: float,
    exit_price: float,
    stop_pct: float,
    point_value: float,
) -> dict[str, Any]:
    return {
        "cap_usd": float(cap_usd),
        "gap": bool(gap),
        "entry_price": float(entry_price),
        "exit_price": float(exit_price),
        "close_stop_pct": float(stop_pct),
        "point_value": float(point_value),
        "exam_qty": 1,
        "fill_qty": int(qty),
        "rl_close_accounting_net_usd": float(booked_net),
    }


__all__ = ["birth_close_info_fields", "book_birth_close_net_usd", "gym_step_info"]
