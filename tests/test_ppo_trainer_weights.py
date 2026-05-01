from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from lumina_core.engine.canonical_training import PPOTrainer


class _PolicyStub:
    def __init__(self) -> None:
        self._state = {"w": 1.0, "b": -1.0}

    def state_dict(self):
        return dict(self._state)

    def load_state_dict(self, state, strict=True):
        del strict
        self._state = dict(state)


class _ModelStub:
    def __init__(self) -> None:
        self.policy = _PolicyStub()

    def save(self, path: str) -> None:
        Path(path).write_text("stub", encoding="utf-8")


class _EngineStub:
    def __init__(self) -> None:
        self.rl_policy_model = _ModelStub()
        self.config = SimpleNamespace(trade_mode="sim", risk_controller={})

    def set_rl_policy(self, model) -> None:
        self.rl_policy_model = model


def test_set_and_get_weights_roundtrip() -> None:
    engine = _EngineStub()
    trainer = PPOTrainer(engine=engine)

    ok = trainer.set_weights({"w": 2.5, "b": 3.5})

    assert ok is True
    assert trainer.get_weights() == {"w": 2.5, "b": 3.5}


def test_save_weights_writes_zip_target(tmp_path: Path) -> None:
    engine = _EngineStub()
    trainer = PPOTrainer(engine=engine)

    target = tmp_path / "weights.zip"
    path = trainer.save_weights(target)

    assert path == str(target)
    assert target.exists()


def test_set_weights_returns_false_without_active_model() -> None:
    engine = _EngineStub()
    engine.rl_policy_model = None
    trainer = PPOTrainer(engine=engine)

    assert trainer.set_weights({"w": 1.0}) is False
