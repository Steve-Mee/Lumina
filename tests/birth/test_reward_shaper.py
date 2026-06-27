from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthRewardConfig
from lumina_core.rl.reward_shaper import (
    RewardShapingState,
    TradeCloseContext,
    compute_expectancy_reward,
    compute_legacy_reward,
)


def _cfg() -> BirthRewardConfig:
    return BirthRewardConfig(
        expectancy_coeff=0.5,
        quality_win_bonus_coeff=0.25,
        loss_asymmetry_coeff=1.25,
        volatility_penalty_coeff=0.0,
        trend_align_bonus_coeff=0.0,
        drawdown_penalty_coeff=0.0,
        sharpe_bonus_coeff=0.0,
        min_risk_usd=50.0,
        reward_clip=10.0,
    )


@pytest.mark.unit
def test_large_win_rewards_higher_than_small_win_same_risk() -> None:
    cfg = _cfg()
    state = RewardShapingState()
    base = dict(equity=50_000.0, stop_pct=0.01, side=1, trend_regime_strength=0.0, trend_atr_norm=0.0)
    reward_big, _ = compute_expectancy_reward(
        TradeCloseContext(net_pnl=100.0, **base),
        state,
        cfg,
    )
    reward_small, _ = compute_expectancy_reward(
        TradeCloseContext(net_pnl=25.0, **base),
        state,
        cfg,
    )
    assert reward_big > reward_small


@pytest.mark.unit
def test_loss_asymmetry_penalizes_losses_more_than_symmetric() -> None:
    cfg = _cfg()
    state = RewardShapingState()
    base = dict(equity=50_000.0, stop_pct=0.01, side=1)
    win, _ = compute_expectancy_reward(
        TradeCloseContext(net_pnl=50.0, trend_regime_strength=0.0, trend_atr_norm=0.0, **base),
        state,
        cfg,
    )
    loss, _ = compute_expectancy_reward(
        TradeCloseContext(net_pnl=-50.0, trend_regime_strength=0.0, trend_atr_norm=0.0, **base),
        state,
        cfg,
    )
    assert win > 0
    assert loss < 0
    assert abs(loss) > win


@pytest.mark.unit
def test_trend_bonus_only_when_aligned() -> None:
    cfg = _cfg()
    cfg = BirthRewardConfig(
        expectancy_coeff=0.5,
        trend_align_bonus_coeff=0.2,
        volatility_penalty_coeff=0.0,
        drawdown_penalty_coeff=0.0,
        sharpe_bonus_coeff=0.0,
        min_risk_usd=50.0,
    )
    state = RewardShapingState()
    base = dict(net_pnl=50.0, equity=50_000.0, stop_pct=0.01, trend_atr_norm=0.0)
    aligned, comp_aligned = compute_expectancy_reward(
        TradeCloseContext(side=1, trend_regime_strength=0.8, **base),
        state,
        cfg,
    )
    counter, comp_counter = compute_expectancy_reward(
        TradeCloseContext(side=-1, trend_regime_strength=0.8, **base),
        state,
        cfg,
    )
    assert comp_aligned["trend_bonus"] > 0
    assert comp_counter["trend_bonus"] == 0.0
    assert aligned > counter


@pytest.mark.unit
def test_high_atr_reduces_risk_adjusted_reward() -> None:
    cfg = _cfg()
    cfg = BirthRewardConfig(
        expectancy_coeff=0.5,
        volatility_penalty_coeff=0.5,
        drawdown_penalty_coeff=0.0,
        sharpe_bonus_coeff=0.0,
        min_risk_usd=50.0,
    )
    state = RewardShapingState()
    base = dict(net_pnl=50.0, equity=50_000.0, stop_pct=0.01, side=1, trend_regime_strength=0.0)
    low_vol, _ = compute_expectancy_reward(TradeCloseContext(trend_atr_norm=0.0001, **base), state, cfg)
    high_vol, _ = compute_expectancy_reward(TradeCloseContext(trend_atr_norm=0.01, **base), state, cfg)
    assert low_vol > high_vol


@pytest.mark.unit
def test_legacy_reward_matches_net_pnl_minus_portfolio_terms() -> None:
    reward = compute_legacy_reward(
        net_pnl=10.0,
        drawdown=0.1,
        sharpe=0.5,
        drawdown_penalty_coeff=0.2,
        sharpe_bonus_coeff=0.05,
        var_es_penalty=1.0,
    )
    assert reward == pytest.approx(10.0 - 0.02 + 0.025 - 1.0)
