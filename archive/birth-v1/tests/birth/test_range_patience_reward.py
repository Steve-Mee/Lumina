"""Range patience reward shaping for birth stage 2."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthRewardConfig
from lumina_core.rl.reward_shaper import range_patience_step_reward


@pytest.mark.unit
def test_range_patience_bonus_for_flat_when_under_active() -> None:
    """Flat bonus only when stage is under-flat (<30%) — classic patience."""
    cfg = BirthRewardConfig(enabled=True, range_flat_bonus_coeff=0.003)
    bonus = range_patience_step_reward(
        regime="RANGING",
        position_flat=True,
        trade_closed=False,
        cfg=cfg,
        stage_flat_ratio=0.20,
    )
    assert bonus == pytest.approx(0.003)


@pytest.mark.unit
def test_range_patience_penalizes_flat_when_over_flat() -> None:
    """Chronic 95%+ flat must not receive flat bonus (forensics Stage2 stall)."""
    cfg = BirthRewardConfig(enabled=True, range_flat_bonus_coeff=0.003)
    bonus = range_patience_step_reward(
        regime="RANGING",
        position_flat=True,
        trade_closed=False,
        cfg=cfg,
        stage_flat_ratio=0.96,
    )
    assert bonus < 0


@pytest.mark.unit
def test_range_patience_rewards_position_when_over_flat() -> None:
    cfg = BirthRewardConfig(enabled=True, range_flat_bonus_coeff=0.003)
    bonus = range_patience_step_reward(
        regime="NEUTRAL",
        position_flat=False,
        trade_closed=False,
        cfg=cfg,
        stage_flat_ratio=0.90,
    )
    assert bonus == pytest.approx(0.003)


@pytest.mark.unit
def test_range_patience_quality_mode_on_expectancy_gap() -> None:
    """In-band + expectancy gap: quality R-multiple shapes reward, not flat keep-alive."""
    from lumina_core.birth.config import BirthRewardConfig

    cfg = BirthRewardConfig(enabled=True, range_quality_boost_coeff=0.15, range_flat_bonus_coeff=0.003)
    win = range_patience_step_reward(
        regime="NEUTRAL",
        position_flat=False,
        trade_closed=True,
        cfg=cfg,
        stage_flat_ratio=0.50,
        expectancy_gap=0.10,
        trade_r_multiple=1.0,
    )
    loss = range_patience_step_reward(
        regime="NEUTRAL",
        position_flat=False,
        trade_closed=True,
        cfg=cfg,
        stage_flat_ratio=0.50,
        expectancy_gap=0.10,
        trade_r_multiple=-1.0,
    )
    assert win > 0.0
    assert loss < 0.0
    assert win > loss


def test_range_patience_churn_penalty_on_close_under_active() -> None:
    cfg = BirthRewardConfig(
        enabled=True,
        range_flat_bonus_coeff=0.003,
        range_churn_penalty_coeff=0.005,
    )
    # Flat empty bonus + mild churn on non-loss close (r_mult=0 → 0.35 * churn).
    net = range_patience_step_reward(
        regime="NEUTRAL",
        position_flat=True,
        trade_closed=True,
        cfg=cfg,
        stage_flat_ratio=0.15,
        trade_r_multiple=0.0,
    )
    assert net == pytest.approx(0.003 - 0.005 * 0.35)


@pytest.mark.unit
def test_under_flat_stop_out_extra_penalty() -> None:
    """Stop-out under over-trading band is punished harder than a flat keep-alive."""
    cfg = BirthRewardConfig(
        enabled=True,
        range_flat_bonus_coeff=0.003,
        range_churn_penalty_coeff=0.005,
        range_quality_boost_coeff=0.15,
    )
    stop_out = range_patience_step_reward(
        regime="NEUTRAL",
        position_flat=False,
        trade_closed=True,
        cfg=cfg,
        stage_flat_ratio=0.25,
        expectancy_gap=0.10,
        trade_r_multiple=-1.0,
    )
    assert stop_out < -0.01


@pytest.mark.unit
def test_range_patience_inactive_on_trend_ticks() -> None:
    cfg = BirthRewardConfig(enabled=True, range_flat_bonus_coeff=0.003)
    assert range_patience_step_reward(
        regime="TREND_UP",
        position_flat=True,
        trade_closed=False,
        cfg=cfg,
        stage_flat_ratio=0.5,
    ) == 0.0
