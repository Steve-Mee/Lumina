"""Gym occupancy reward + S3 in-band HOLD tax (M5 pressure valve)."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.stage3_inband_idle import (
    S3_INBAND_DEFAULT_HOLD_TAX,
    s3_inband_hold_tax,
)


def apply_gym_birth_occupancy_reward(
    env: Any,
    *,
    row: dict[str, Any],
    side_bucket: int,
    trade_closed: bool,
    close_stop_pct: float,
    close_net: float,
) -> float:
    """Range-patience + S3 idle tax. Gym occupancy counters stay here (M5)."""
    from lumina_core.rl.reward_shaper import range_patience_step_reward

    tick_regime = str(row.get("regime", "NEUTRAL"))
    is_range_tick = (
        str(tick_regime).upper() in {"NEUTRAL", "RANGING"}
        or "RANGE" in str(tick_regime).upper()
    )
    if is_range_tick:
        env._range_total_bars = int(getattr(env, "_range_total_bars", 0) or 0) + 1
        if int(env._position) == 0:
            env._range_flat_bars = int(getattr(env, "_range_flat_bars", 0) or 0) + 1
    stage_flat_ratio = None
    if int(getattr(env, "_range_total_bars", 0) or 0) >= 20:
        stage_flat_ratio = float(env._range_flat_bars) / float(
            max(1, env._range_total_bars)
        )
    reward_cfg = env._reward_cfg()
    exp_floor = float(getattr(env.config, "stage2_expectancy_floor", -0.15) or -0.15)
    exp_gap = float(getattr(env.config, "expectancy_gap", 0.0) or 0.0)
    recent = list(getattr(env._reward_state, "recent_pnls", []) or [])
    if len(recent) >= 20:
        wr = float(sum(1 for p in recent if float(p) > 0.0)) / float(len(recent))
        live_exp = wr - 0.50
        exp_gap = max(exp_gap, max(0.0, exp_floor - live_exp))
    trade_r = None
    if trade_closed:
        risk_usd = float(getattr(env, "_close_risk_usd", 0.0) or 0.0)
        if risk_usd <= 1e-12:
            risk_usd = (
                abs(float(close_stop_pct))
                * abs(float(getattr(env, "_close_entry_price", 0.0) or 0.0))
                * float(getattr(env, "_close_qty", 1) or 1)
                * 5.0
            )
        trade_r = float(close_net) / max(risk_usd, 1e-9)
    ft_press = float(getattr(env.config, "first_touch_training_pressure", 0.0) or 0.0)
    cfg_flat = getattr(env.config, "stage_cumulative_flat", None)
    try:
        cumulative_flat = float(cfg_flat) if cfg_flat is not None else None
    except (TypeError, ValueError):
        cumulative_flat = None
    regime = str(getattr(env.config, "curriculum_regime", "") or "")
    mode = str(getattr(env.config, "participation_mode", "") or "")
    pos = int(env._position)
    policy_n = int(getattr(env.config, "stage_policy_trades", 0) or 0)
    lo = float(getattr(env.config, "participation_band_lo", 0.25) or 0.25)
    hi = float(getattr(env.config, "participation_band_hi", 0.75) or 0.75)
    tax_mag = float(
        getattr(reward_cfg, "s3_inband_hold_tax", S3_INBAND_DEFAULT_HOLD_TAX)
        or S3_INBAND_DEFAULT_HOLD_TAX
    )
    tax_flat = (
        float(cumulative_flat)
        if cumulative_flat is not None
        else float(stage_flat_ratio or 0.5)
    )
    tax = s3_inband_hold_tax(
        curriculum_regime=regime,
        participation_mode=mode,
        position=pos,
        cumulative_flat=tax_flat,
        band_lo=lo,
        band_hi=hi,
        policy_trades=policy_n,
        action_side=int(side_bucket),
        tax=tax_mag,
    )
    if tax < 0.0:
        env._s3_inband_hold_tax_steps = int(
            getattr(env, "_s3_inband_hold_tax_steps", 0) or 0
        ) + 1
    bonus = range_patience_step_reward(
        regime=tick_regime,
        position_flat=int(env._position) == 0,
        trade_closed=bool(trade_closed),
        cfg=reward_cfg,
        stage_flat_ratio=stage_flat_ratio,
        expectancy_gap=exp_gap,
        trade_r_multiple=trade_r,
        first_touch_training_pressure=ft_press,
        curriculum_regime=regime,
        participation_mode=mode,
        position=pos,
        policy_trades=policy_n,
        band_lo=lo,
        band_hi=hi,
        action_side=int(side_bucket),
        cumulative_flat=cumulative_flat,
    )
    return float(bonus)


__all__ = ["apply_gym_birth_occupancy_reward"]
