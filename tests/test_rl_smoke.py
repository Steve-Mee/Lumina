from lumina_core.engine.engine_config import EngineConfig
from lumina_core.engine.lumina_engine import LuminaEngine
from lumina_core.engine.rl.ppo_trainer import PPOTrainer
from lumina_core.engine.rl.rl_trading_environment import RLTradingEnvironment
from lumina_core.runtime_context import RuntimeContext


def test_rl_trading_layer_smoke_init() -> None:
    """Smoke test: RL layer moet initialiseren via de standaard engine-context flow."""
    engine = LuminaEngine(config=EngineConfig())
    ctx = RuntimeContext(engine=engine)

    env = RLTradingEnvironment(ctx)
    trainer = PPOTrainer(ctx)

    obs, _ = env.reset(seed=42)
    action = trainer.predict_action(obs)

    assert obs.shape == (23,)
    assert set(action.keys()) == {"signal", "qty_pct", "stop_mult", "target_mult"}
