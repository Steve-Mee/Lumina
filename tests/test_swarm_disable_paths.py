from types import SimpleNamespace

from lumina_core.engine.lumina_engine import LuminaEngine


def test_lumina_engine_does_not_initialize_swarm_when_disabled(monkeypatch):
    monkeypatch.setattr(
        "lumina_core.engine.lumina_engine.BibleEngine",
        lambda *args, **kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "lumina_core.engine.fast_path_engine.FastPathEngine",
        lambda *args, **kwargs: SimpleNamespace(),
        raising=False,
    )

    class _StubBacktester:
        def __init__(self, *_args, **_kwargs):
            pass

    class _StubRLTradingEnvironment:
        def __init__(self, *_args, **_kwargs):
            pass

    class _StubPPOTrainer:
        def __init__(self, *_args, **_kwargs):
            pass

    class _StubInfiniteSimulator:
        def __init__(self, *_args, **_kwargs):
            pass

    class _StubEmotionalTwin:
        def __init__(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr(
        "lumina_core.engine.realistic_backtester_engine.RealisticBacktesterEngine",
        _StubBacktester,
    )
    monkeypatch.setattr(
        "lumina_core.engine.advanced_backtester_engine.AdvancedBacktesterEngine",
        _StubBacktester,
    )
    monkeypatch.setattr(
        "lumina_core.engine.rl.rl_trading_environment.RLTradingEnvironment",
        _StubRLTradingEnvironment,
    )
    monkeypatch.setattr(
        "lumina_core.engine.rl.ppo_trainer.PPOTrainer",
        _StubPPOTrainer,
    )
    monkeypatch.setattr(
        "lumina_core.engine.infinite_simulator.InfiniteSimulator",
        _StubInfiniteSimulator,
    )
    monkeypatch.setattr(
        "lumina_core.engine.emotional_twin_agent.EmotionalTwinAgent",
        _StubEmotionalTwin,
    )

    config = SimpleNamespace(
        bible_file="dummy.json",
        instrument="MES JUN26",
        trade_mode="paper",
        max_risk_percent=1.0,
        drawdown_kill_percent=8.0,
        swarm_enabled=False,
    )

    engine = LuminaEngine(config=config)  # type: ignore[arg-type]

    assert engine.swarm is None
