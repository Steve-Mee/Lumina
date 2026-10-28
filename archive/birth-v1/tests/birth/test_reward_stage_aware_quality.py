"""Stage-aware reward: range uses mean-reversion + WR quality; trend keeps align."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthRewardConfig
from lumina_core.rl.reward_shaper import (
    RewardShapingState,
    TradeCloseContext,
    compute_expectancy_reward,
)


def _ctx(**kwargs: object) -> TradeCloseContext:
    base = dict(
        net_pnl=50.0,
        equity=50_000.0,
        stop_pct=0.0012,
        side=1,
        trend_regime_strength=-0.5,  # short-term down → long fade is good
        trend_atr_norm=0.0002,
        var_es_penalty=0.0,
        curriculum_regime="stage2_range",
        expectancy_gap=0.10,
        tick_regime="NEUTRAL",
    )
    base.update(kwargs)
    return TradeCloseContext(**base)  # type: ignore[arg-type]


@pytest.mark.unit
def test_range_prefers_mean_reversion_bonus() -> None:
    cfg = BirthRewardConfig(trend_align_bonus_coeff=0.2)
    state = RewardShapingState()
    # Long fade against negative strength → positive dir bonus
    r_fade, c_fade = compute_expectancy_reward(_ctx(side=1, trend_regime_strength=-0.5), state, cfg)
    r_chase, c_chase = compute_expectancy_reward(_ctx(side=1, trend_regime_strength=0.5), state, cfg)
    assert c_fade["direction_mode"] == 1.0  # mean reversion
    assert c_fade["direction_bonus"] >= c_chase["direction_bonus"]
    assert r_fade >= r_chase - 1e-9


@pytest.mark.unit
def test_trend_curriculum_uses_trend_align() -> None:
    cfg = BirthRewardConfig(trend_align_bonus_coeff=0.2)
    state = RewardShapingState()
    r, c = compute_expectancy_reward(
        _ctx(curriculum_regime="stage1_trend", tick_regime="TREND_UP", side=1, trend_regime_strength=0.8),
        state,
        cfg,
    )
    assert c["direction_mode"] == 0.0
    assert c["direction_bonus"] > 0
    assert r != 0


@pytest.mark.unit
def test_expectancy_gap_amplifies_wins() -> None:
    cfg = BirthRewardConfig()
    state = RewardShapingState(recent_pnls=[-10.0] * 20)
    r_gap, c_gap = compute_expectancy_reward(_ctx(expectancy_gap=0.15, net_pnl=40.0), state, cfg)
    r_ok, c_ok = compute_expectancy_reward(_ctx(expectancy_gap=0.0, net_pnl=40.0), state, cfg)
    assert c_gap["wr_quality_term"] > 0
    assert r_gap >= r_ok


@pytest.mark.unit
def test_expectancy_gap_penalizes_losses() -> None:
    cfg = BirthRewardConfig()
    state = RewardShapingState()
    r_gap, c_gap = compute_expectancy_reward(
        _ctx(expectancy_gap=0.15, net_pnl=-40.0), state, cfg
    )
    r_ok, _ = compute_expectancy_reward(_ctx(expectancy_gap=0.0, net_pnl=-40.0), state, cfg)
    assert c_gap["wr_quality_term"] < 0
    assert r_gap <= r_ok
