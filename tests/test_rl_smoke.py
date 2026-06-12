from lumina_core.engine.engine_config import EngineConfig
from lumina_core.engine.lumina_engine import LuminaEngine
from lumina_core.rl import RLConfig, RLTradingEnvironment
from lumina_core.rl.observation_builder import OBSERVATION_DIM


def test_rl_trading_layer_smoke_init() -> None:
    """Smoke test: canonical 32-dim RL environment initializes."""
    engine = LuminaEngine(config=EngineConfig())
    rows = [
        {
            "timestamp": "2026-01-01T00:00:00Z",
            "last": 5000.0,
            "close": 5000.0,
            "bid": 4999.875,
            "ask": 5000.125,
            "volume": 100,
        }
        for _ in range(120)
    ]
    env = RLTradingEnvironment(engine, rows, config=RLConfig(trade_mode="sim"))
    obs, _ = env.reset(seed=42)
    assert obs.shape == (OBSERVATION_DIM,)
