from __future__ import annotations

from time import perf_counter
from types import SimpleNamespace


from lumina_core.rl import RLConfig, RLTradingEnvironment


class _MarketDataStub:
    def get_tape_snapshot(self):
        return {
            "volume_delta": 0.0,
            "avg_volume_delta_10": 0.0,
            "bid_ask_imbalance": 1.0,
            "cumulative_delta_10": 0.0,
        }


class _RiskControllerStub:
    def __init__(self, var_95: float = 0.0, es_95: float = 0.0) -> None:
        self._active_limits = SimpleNamespace(var_95_limit_usd=100.0, es_95_limit_usd=100.0)
        self._var_95 = float(var_95)
        self._es_95 = float(es_95)

    def get_var_es_snapshot(self, *, proposed_risk: float = 0.0):
        del proposed_risk
        return {
            "var_95_usd": self._var_95,
            "es_95_usd": self._es_95,
        }


class _EngineStub:
    def __init__(self, *, trade_mode: str = "sim", risk_controller: _RiskControllerStub | None = None):
        self.config = SimpleNamespace(
            instrument="MES JUN26",
            trade_mode=trade_mode,
            risk_controller={},
        )
        self.market_data = _MarketDataStub()
        self.AI_DRAWN_FIBS = {}
        self.world_model = {}
        self.risk_controller = risk_controller

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


def _sim_data(rows: int = 220) -> list[dict[str, float]]:
    return [{"close": 5000.0 + (i * 0.25)} for i in range(rows)]


def test_step_applies_stochastic_slippage_and_fees(monkeypatch) -> None:
    engine = _EngineStub(trade_mode="sim")
    cfg = RLConfig(
        slippage_points=0.25,
        slippage_sigma=0.1,
        slippage_volatility_factor=0.5,
        commission_per_side_usd=1.0,
        exchange_fee_per_side_usd=0.5,
        clearing_fee_per_side_usd=0.2,
        nfa_fee_per_side_usd=0.1,
        trade_mode="sim",
    )
    env = RLTradingEnvironment(engine, _sim_data(), config=cfg)
    env.reset()

    monkeypatch.setattr("lumina_core.rl.gym_environment.random.gauss", lambda _mu, _sigma: 0.3)
    _obs, _reward, _done, _truncated, info = env.step([1.0, 0.4, 0.01, 0.02])

    assert float(info["slippage_cost"]) >= 0.0
    assert float(info["fees_cost"]) > 0.0


def test_real_mode_fail_closed_blocks_entry_on_safety_breach(monkeypatch) -> None:
    engine = _EngineStub(trade_mode="real")
    cfg = RLConfig(
        slippage_points=0.25,
        slippage_sigma=1.0,
        slippage_volatility_factor=3.0,
        commission_per_side_usd=5.0,
        exchange_fee_per_side_usd=3.0,
        clearing_fee_per_side_usd=2.0,
        nfa_fee_per_side_usd=1.0,
        real_safety_threshold_usd=49999.0,
        real_safety_threshold_ratio=1.0,
        trade_mode="real",
    )
    env = RLTradingEnvironment(engine, _sim_data(), config=cfg)
    env.reset()

    monkeypatch.setattr("lumina_core.rl.gym_environment.random.gauss", lambda _mu, _sigma: 3.0)
    _obs, _reward, _done, _truncated, info = env.step([1.0, 1.0, 0.01, 0.02])

    assert bool(info["blocked_by_capital_preservation"]) is True
    assert "fail-closed" in str(info["block_reason"])


def test_sim_reward_penalizes_high_var_es() -> None:
    risk_stub = _RiskControllerStub(var_95=250.0, es_95=300.0)
    engine = _EngineStub(trade_mode="sim", risk_controller=risk_stub)
    cfg = RLConfig(
        sim_var_penalty_coeff=0.2,
        sim_es_penalty_coeff=0.3,
        trade_mode="sim",
    )
    env = RLTradingEnvironment(engine, _sim_data(), config=cfg)
    env.reset()

    _obs, reward, _done, _truncated, info = env.step([0.0, 0.0, 0.01, 0.02])

    assert float(info["var_es_penalty"]) > 0.0
    assert float(reward) < 0.0


def test_sim_step_loop_performance_guard() -> None:
    """Guardrail: SIM step loop should remain lightweight after risk-cost additions."""
    engine = _EngineStub(trade_mode="sim")
    env = RLTradingEnvironment(engine, _sim_data(rows=400), config=RLConfig(trade_mode="sim"))
    env.reset()

    start = perf_counter()
    for _ in range(180):
        _obs, _reward, done, _truncated, _info = env.step([0.0, 0.0, 0.01, 0.02])
        if done:
            env.reset()
    elapsed = perf_counter() - start

    assert elapsed < 8.0


# ---------------------------------------------------------------------------
# FASE 2 Meta-RL: DNA embedding tests
# ---------------------------------------------------------------------------


def test_observation_space_shape_is_28_with_dna_embedding() -> None:
    """FASE 2: observation space must be (28,) after Meta-RL expansion."""
    engine = _EngineStub()
    env = RLTradingEnvironment(engine, _sim_data(), config=RLConfig())
    assert env.observation_space.shape == (28,)


def test_set_dna_hash_changes_embedding_in_observation() -> None:
    """FASE 2: set_dna_hash() must be reflected in _get_observation() features 24-27."""
    engine = _EngineStub()
    env = RLTradingEnvironment(engine, _sim_data(), config=RLConfig())
    env.reset()

    env.set_dna_hash("")
    obs_no_hash, *_ = env.step([0.0, 0.0, 0.01, 0.02])
    dna_features_none = obs_no_hash[24:28].tolist()

    env.reset()
    env.set_dna_hash("abc123")
    obs_with_hash, *_ = env.step([0.0, 0.0, 0.01, 0.02])
    dna_features_abc = obs_with_hash[24:28].tolist()

    # Empty hash → all zeros embedding
    assert dna_features_none == [0.0, 0.0, 0.0, 0.0]
    # Non-empty hash → non-zero embedding bytes
    assert dna_features_abc != [0.0, 0.0, 0.0, 0.0]
    # Each byte normalised to [-1, 1]
    assert all(-1.0 <= v <= 1.0 for v in dna_features_abc)


def test_dna_embedding_is_deterministic() -> None:
    """FASE 2: same DNA hash always produces the same embedding."""
    engine = _EngineStub()
    env = RLTradingEnvironment(engine, _sim_data(), config=RLConfig())
    env.set_dna_hash("deterministic-test-hash")
    emb1 = env._dna_embedding()
    emb2 = env._dna_embedding()
    assert emb1 == emb2
