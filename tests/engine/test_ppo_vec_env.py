"""Birth PPO DummyVecEnv + hyperparam alignment (lungs GPU path)."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from lumina_core.birth.foundation_metrics import S5_SHARPE_FLOOR
from lumina_core.rl.gym_environment import RLConfig
from lumina_core.rl.ppo_vec_env import (
    align_ppo_hyperparams,
    make_birth_ppo_env,
    transfer_ppo_policy_weights,
    _resolve_ppo_n_envs,
)


def test_s5_sharpe_floor_unchanged_by_vecenv() -> None:
    assert S5_SHARPE_FLOOR == -2.0


def test_n_envs_cpu_is_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lumina_core.rl.ppo_vec_env._resolve_ppo_device", lambda: "cpu")
    assert _resolve_ppo_n_envs() == 1


def test_n_envs_gpu_accelerated_caps_at_8(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lumina_core.rl.ppo_vec_env._resolve_ppo_device", lambda: "cuda")
    monkeypatch.setattr(
        "lumina_core.hardware_intelligence.get_or_create_hardware_profile",
        lambda: {"profile": "gpu_accelerated", "detection": {"cpu_cores": 32}},
    )
    assert _resolve_ppo_n_envs() == 8


def test_n_envs_cpu_efficient_profile_is_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lumina_core.rl.ppo_vec_env._resolve_ppo_device", lambda: "cuda")
    monkeypatch.setattr(
        "lumina_core.hardware_intelligence.get_or_create_hardware_profile",
        lambda: {"profile": "cpu_efficient", "detection": {"cpu_cores": 32}},
    )
    assert _resolve_ppo_n_envs() == 1


def test_align_hyperparams_batch_divides_rollout() -> None:
    aligned = align_ppo_hyperparams(
        {"n_steps": 1024, "batch_size": 256, "learning_rate": 3e-4},
        n_envs=8,
    )
    assert aligned["n_steps"] == 128
    assert aligned["batch_size"] == 256
    assert (aligned["n_steps"] * 8) % aligned["batch_size"] == 0


def test_align_hyperparams_single_env_keeps_n_steps() -> None:
    aligned = align_ppo_hyperparams({"n_steps": 1024, "batch_size": 256}, n_envs=1)
    assert aligned["n_steps"] == 1024
    assert aligned["batch_size"] == 256


def _stub_engine() -> SimpleNamespace:
    return SimpleNamespace(
        config=SimpleNamespace(instrument="MES", trade_mode="sim", risk_controller={})
    )


def _stub_bars(n: int = 40) -> list[dict[str, float | str]]:
    return [
        {
            "timestamp": "2026-01-01T00:00:00Z",
            "last": 5000.0,
            "close": 5000.0,
            "bid": 4999.875,
            "ask": 5000.125,
            "volume": 100,
        }
        for _ in range(n)
    ]


def test_make_birth_ppo_env_single_is_gym() -> None:
    env = make_birth_ppo_env(
        engine=_stub_engine(),
        bars=_stub_bars(),
        rl_cfg=RLConfig(trade_mode="sim"),
        dna_hash="abc",
        n_envs=1,
    )
    from lumina_core.rl.gym_environment import RLTradingEnvironment

    assert isinstance(env, RLTradingEnvironment)
    obs, _info = env.reset(seed=1)
    assert obs.shape[0] >= 1


def test_make_birth_ppo_env_dummy_vec_width() -> None:
    pytest.importorskip("stable_baselines3")
    env = make_birth_ppo_env(
        engine=_stub_engine(),
        bars=_stub_bars(),
        rl_cfg=RLConfig(trade_mode="sim"),
        dna_hash=None,
        n_envs=4,
    )
    assert int(getattr(env, "num_envs", 0) or 0) == 4
    reset_out = env.reset()
    obs = reset_out[0] if isinstance(reset_out, tuple) else reset_out
    arr = np.asarray(obs)
    assert arr.shape[0] == 4
    actions = np.stack([env.action_space.sample() for _ in range(4)])
    stepped = env.step(actions)
    rewards = stepped[1]
    assert len(np.asarray(rewards).reshape(-1)) == 4


def test_transfer_ppo_policy_weights_roundtrip() -> None:
    class _Pol:
        def __init__(self, w: float) -> None:
            self._w = {"k": w}

        def state_dict(self) -> dict[str, float]:
            return dict(self._w)

        def load_state_dict(self, state: dict[str, float]) -> None:
            self._w = dict(state)

    src = SimpleNamespace(policy=_Pol(2.5))
    dst = SimpleNamespace(policy=_Pol(0.0))
    assert transfer_ppo_policy_weights(src, dst) is True
    assert dst.policy.state_dict() == {"k": 2.5}


def test_transfer_ppo_policy_weights_missing_policy() -> None:
    assert transfer_ppo_policy_weights(SimpleNamespace(), SimpleNamespace()) is False
