"""Range patience reward shaping for birth stage 2."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthRewardConfig
from lumina_core.rl.reward_shaper import range_patience_step_reward


@pytest.mark.unit
def test_range_patience_bonus_for_flat_position() -> None:
    cfg = BirthRewardConfig(enabled=True, range_flat_bonus_coeff=0.003)
    bonus = range_patience_step_reward(
        regime="RANGING",
        position_flat=True,
        trade_closed=False,
        cfg=cfg,
    )
    assert bonus == pytest.approx(0.003)


@pytest.mark.unit
def test_range_patience_churn_penalty_on_close() -> None:
    cfg = BirthRewardConfig(
        enabled=True,
        range_flat_bonus_coeff=0.003,
        range_churn_penalty_coeff=0.005,
    )
    net = range_patience_step_reward(
        regime="NEUTRAL",
        position_flat=True,
        trade_closed=True,
        cfg=cfg,
    )
    assert net == pytest.approx(-0.002)


@pytest.mark.unit
def test_range_patience_inactive_on_trend_ticks() -> None:
    cfg = BirthRewardConfig(enabled=True, range_flat_bonus_coeff=0.003)
    assert range_patience_step_reward(
        regime="TREND_UP",
        position_flat=True,
        trade_closed=False,
        cfg=cfg,
    ) == 0.0
