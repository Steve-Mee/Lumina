from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.birth.config import BirthRewardConfig
from lumina_core.birth.tick_enricher import enrich_ticks_for_sim
from lumina_core.rl import RLConfig, RLTradingEnvironment


class _MarketDataStub:
    def get_tape_snapshot(self):
        return {
            "volume_delta": 0.0,
            "avg_volume_delta_10": 0.0,
            "bid_ask_imbalance": 1.0,
            "cumulative_delta_10": 0.0,
        }


class _EngineStub:
    def __init__(self) -> None:
        self.config = SimpleNamespace(
            instrument="MES JUN26",
            trade_mode="birth",
            risk_controller={},
        )
        self.market_data = _MarketDataStub()
        self.AI_DRAWN_FIBS = {}
        self.world_model = {}

    def detect_market_regime(self, _df):
        return "NEUTRAL"

    def get_current_dream_snapshot(self):
        return {
            "confidence": 0.0,
            "confluence_score": 0.0,
            "stop": 0.0,
            "target": 0.0,
            "fib_levels": {},
        }


def _rising_ticks(n: int) -> list[dict]:
    return enrich_ticks_for_sim(
        [{"last": 5000.0 + i * 2.0, "volume": 100, "close": 5000.0 + i * 2.0} for i in range(n)]
    )


@pytest.mark.unit
def test_birth_env_expectancy_reward_on_trade_close() -> None:
    reward_cfg = BirthRewardConfig(
        enabled=True,
        expectancy_coeff=0.5,
        volatility_penalty_coeff=0.0,
        trend_align_bonus_coeff=0.0,
        drawdown_penalty_coeff=0.0,
        sharpe_bonus_coeff=0.0,
        min_risk_usd=25.0,
    )
    env = RLTradingEnvironment(
        _EngineStub(),
        _rising_ticks(200),
        config=RLConfig(trade_mode="birth", reward=reward_cfg),
    )
    env.reset()
    _obs, reward, _done, _trunc, info = env.step([1.0, 0.1, 0.0075, 0.013])
    if info.get("trade_closed"):
        assert "reward_components" in info
        assert info["reward_components"].get("r_multiple") is not None
    else:
        assert reward == 0.0 or info.get("rl_close_accounting_net_usd", 0) != 0


@pytest.mark.unit
def test_real_mode_uses_legacy_reward_not_expectancy_components(monkeypatch) -> None:
    reward_cfg = BirthRewardConfig(enabled=True)
    env = RLTradingEnvironment(
        _EngineStub(),
        [{"close": 5000.0 + i * 0.25} for i in range(220)],
        config=RLConfig(
            trade_mode="real",
            reward=reward_cfg,
            real_safety_threshold_usd=49999.0,
            real_safety_threshold_ratio=1.0,
        ),
    )
    env.config.trade_mode = "real"
    env.trade_mode = "real"
    env.reset()
    monkeypatch.setattr("lumina_core.rl.gym_environment.random.gauss", lambda _mu, _sigma: 0.0)
    _obs, reward, _done, _trunc, info = env.step([1.0, 0.1, 0.01, 0.02])
    assert info.get("reward_components") == {}
    assert not info.get("trade_closed", False) or "r_multiple" not in (info.get("reward_components") or {})
