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


def training_reward_after_book(
    env: Any,
    *,
    is_birth: bool,
    trade_closed: bool,
    booked_net: float,
    prev_equity: float,
    close_stop_pct: float,
    close_side: int,
    row: dict[str, Any],
    var_es_penalty: float,
) -> tuple[float, dict[str, float]]:
    """Birth close = signed process-R. Non-birth close = expectancy shaper."""
    from lumina_core.rl.reward_shaper import (
        TradeCloseContext,
        compute_expectancy_reward,
        compute_legacy_reward,
        trend_features_from_tick,
        update_trade_stats,
    )

    components: dict[str, float] = {}
    if env._uses_expectancy_reward():
        if not trade_closed:
            return (-var_es_penalty if var_es_penalty > 0 else 0.0), components
        if is_birth:
            from lumina_core.birth.s5_process_decomp import birth_close_process_r

            reward = birth_close_process_r(
                float(booked_net),
                float(getattr(env, "_close_risk_usd", 0.0) or 0.0),
            )
            components = {"r_multiple": float(reward), "process_r": float(reward)}
            update_trade_stats(
                env._reward_state,
                float(booked_net),
                window=env._reward_cfg().rolling_trade_window,
            )
            return float(reward), components
        trend_strength, atr_norm = trend_features_from_tick(row)
        env._reward_state.drawdown = env._drawdown()
        env._reward_state.sharpe = env._rolling_sharpe()
        ctx = TradeCloseContext(
            net_pnl=float(booked_net),
            equity=float(prev_equity),
            stop_pct=float(close_stop_pct),
            side=int(close_side),
            trend_regime_strength=trend_strength,
            trend_atr_norm=atr_norm,
            var_es_penalty=float(var_es_penalty),
            curriculum_regime=str(getattr(env.config, "curriculum_regime", "") or ""),
            expectancy_gap=float(getattr(env.config, "expectancy_gap", 0.0) or 0.0),
            tick_regime=str(row.get("regime", "NEUTRAL") or "NEUTRAL"),
            risk_usd=float(getattr(env, "_close_risk_usd", 0.0) or 0.0) or None,
            qty=int(getattr(env, "_close_qty", 0) or 0) or None,
        )
        reward, components = compute_expectancy_reward(ctx, env._reward_state, env._reward_cfg())
        update_trade_stats(
            env._reward_state,
            float(booked_net),
            window=env._reward_cfg().rolling_trade_window,
        )
        return float(reward), components
    reward_cfg = env._reward_cfg()
    reward = compute_legacy_reward(
        net_pnl=float(booked_net),
        drawdown=env._drawdown(),
        sharpe=env._rolling_sharpe(),
        drawdown_penalty_coeff=reward_cfg.drawdown_penalty_coeff,
        sharpe_bonus_coeff=reward_cfg.sharpe_bonus_coeff,
        var_es_penalty=float(var_es_penalty),
    )
    return float(reward), components


__all__ = [
    "birth_close_info_fields",
    "book_birth_close_net_usd",
    "gym_step_info",
    "training_reward_after_book",
]
