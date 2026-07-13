from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from lumina_core.ppo_trainer import PPOTrainer


def _engine_stub() -> SimpleNamespace:
    engine = SimpleNamespace(rl_policy_model=None, config=SimpleNamespace(trade_mode="sim", risk_controller={}))

    def _set_rl_policy(model: object) -> None:
        engine.rl_policy_model = model

    engine.set_rl_policy = _set_rl_policy
    return engine


@pytest.mark.unit
def test_create_fresh_birth_policy_is_callable() -> None:
    trainer = PPOTrainer(engine=_engine_stub())
    assert callable(getattr(trainer, "create_fresh_birth_policy", None))


@pytest.mark.unit
def test_create_fresh_birth_policy_force_reinit_installs_model(tmp_path: Path) -> None:
    trainer = PPOTrainer(engine=_engine_stub(), model_dir=tmp_path / "ppo")
    fake_model = SimpleNamespace(predict=lambda *_a, **_k: (None, None))

    with patch("stable_baselines3.PPO", create=True, return_value=fake_model):
        with patch.object(PPOTrainer, "_bootstrap_birth_env", return_value=MagicMock()):
            model = trainer.create_fresh_birth_policy(allow_load_existing=False, force_reinit=True)

    assert model is fake_model
    assert trainer._resolve_active_model() is fake_model


@pytest.mark.unit
def test_create_fresh_birth_policy_loads_existing_when_allowed(tmp_path: Path) -> None:
    trainer = PPOTrainer(engine=_engine_stub(), model_dir=tmp_path / "ppo")
    trainer.model_dir.mkdir(parents=True, exist_ok=True)
    policy_path = trainer.model_dir / "lumina_ppo_policy.zip"
    policy_path.write_bytes(b"stub")
    loaded = SimpleNamespace(predict=lambda *_a, **_k: (None, None))

    with patch.object(PPOTrainer, "load_weights", return_value=loaded) as load_weights:
        model = trainer.create_fresh_birth_policy(allow_load_existing=True, force_reinit=False)

    load_weights.assert_called_once_with(str(policy_path))
    assert model is loaded


@pytest.mark.unit
def test_save_final_birth_policy_delegates_to_save_weights(tmp_path: Path) -> None:
    trainer = PPOTrainer(engine=_engine_stub(), model_dir=tmp_path / "ppo")
    target = tmp_path / "state" / "birth_policy.zip"

    with patch.object(PPOTrainer, "save_weights", return_value=str(target)) as save_weights:
        trainer.save_final_birth_policy(str(target))

    save_weights.assert_called_once_with(str(target))


@pytest.mark.unit
def test_update_from_buffer_accepts_birth_phase_kwarg() -> None:
    trainer = PPOTrainer(engine=_engine_stub())
    buffer = MagicMock()
    buffer.trajectories = []

    result = trainer.update_from_buffer(buffer=buffer, timesteps=1000, birth_phase=True)
    assert result is None


@pytest.mark.unit
def test_final_birth_polish_delegates_to_update_from_buffer() -> None:
    trainer = PPOTrainer(engine=_engine_stub())
    buffer = MagicMock()
    sentinel = SimpleNamespace()

    with patch.object(PPOTrainer, "update_from_buffer", return_value=sentinel) as update:
        result = trainer.final_birth_polish(buffer, timesteps=12_000)

    update.assert_called_once_with(
        buffer=buffer,
        timesteps=12_000,
        birth_phase=True,
    )
    assert result is sentinel
