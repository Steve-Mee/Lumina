"""Fail-closed Birth physics probe: missing SB3/torch never starts Birth."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from lumina_core.birth.physics_preflight import (
    CUDA_REQUIRED,
    INSTALL_HINT,
    PHYSICS_UNAVAILABLE,
    BirthPhysicsProbe,
    birth_exception_attention,
    enforce_birth_physics,
    import_sb3_ppo,
    is_physics_failure,
    probe_birth_physics,
    reject_birth_if_physics_missing,
    trainer_requires_physics,
)

pytestmark = pytest.mark.unit


def _importer(**modules: Any) -> Any:
    def load(name: str) -> Any:
        if name in modules:
            value = modules[name]
            if isinstance(value, BaseException):
                raise value
            return value
        raise ModuleNotFoundError(name)

    return load


def _torch(*, cuda: bool, device: str = "NVIDIA GeForce RTX 5070 Ti") -> Any:
    return SimpleNamespace(
        cuda=SimpleNamespace(
            is_available=lambda: cuda,
            get_device_name=lambda _idx: device,
        )
    )


def _sb3(*, ppo: Any = object) -> Any:
    return SimpleNamespace(PPO=ppo)


def test_probe_fails_closed_when_sb3_missing() -> None:
    result = probe_birth_physics(
        importer=_importer(
            torch=_torch(cuda=True),
            gymnasium=SimpleNamespace(),
            stable_baselines3=ModuleNotFoundError("No module named 'stable_baselines3'"),
        ),
        has_nvidia=True,
    )
    assert result.ok is False
    assert result.retryable is False
    assert result.reason == PHYSICS_UNAVAILABLE
    assert "stable_baselines3" in result.missing
    assert INSTALL_HINT in result.human_message
    assert "WIPE_FULL" in result.human_message
    assert "wipe_and_retry" not in result.recommended_actions


def test_probe_fails_closed_when_torch_missing() -> None:
    result = probe_birth_physics(
        importer=_importer(
            torch=ModuleNotFoundError("No module named 'torch'"),
            gymnasium=SimpleNamespace(),
            stable_baselines3=_sb3(),
        ),
        has_nvidia=True,
    )
    assert result.ok is False
    assert result.retryable is False
    assert "torch" in result.missing


def test_probe_requires_cuda_on_nvidia_without_allow_cpu() -> None:
    result = probe_birth_physics(
        importer=_importer(
            torch=_torch(cuda=False),
            gymnasium=SimpleNamespace(),
            stable_baselines3=_sb3(),
        ),
        has_nvidia=True,
        allow_cpu_ppo=False,
    )
    assert result.ok is False
    assert result.reason == CUDA_REQUIRED
    assert result.retryable is False
    assert INSTALL_HINT in result.human_message


def test_probe_allows_cpu_ppo_only_when_explicit() -> None:
    result = probe_birth_physics(
        importer=_importer(
            torch=_torch(cuda=False),
            gymnasium=SimpleNamespace(),
            stable_baselines3=_sb3(),
        ),
        has_nvidia=True,
        allow_cpu_ppo=True,
    )
    assert result.ok is True
    assert result.cuda_available is False


def test_probe_cpu_machine_without_nvidia_is_ok() -> None:
    result = probe_birth_physics(
        importer=_importer(
            torch=_torch(cuda=False),
            gymnasium=SimpleNamespace(),
            stable_baselines3=_sb3(),
        ),
        has_nvidia=False,
        allow_cpu_ppo=False,
    )
    assert result.ok is True


def test_probe_ready_when_cuda_and_sb3_present() -> None:
    result = probe_birth_physics(
        importer=_importer(
            torch=_torch(cuda=True),
            gymnasium=SimpleNamespace(),
            stable_baselines3=_sb3(),
        ),
        has_nvidia=True,
    )
    assert result.ok is True
    assert result.sb3_ok is True
    assert result.cuda_available is True
    assert result.device_name == "NVIDIA GeForce RTX 5070 Ti"


def test_import_sb3_ppo_raises_operator_message() -> None:
    if importlib.util.find_spec("stable_baselines3") is not None:
        assert import_sb3_ppo() is not None
        return
    with pytest.raises(RuntimeError, match="install_birth_physics_stack"):
        import_sb3_ppo()


def test_trainer_requires_physics_skips_stubs() -> None:
    assert trainer_requires_physics(None) is False
    assert trainer_requires_physics(SimpleNamespace()) is False
    assert trainer_requires_physics(SimpleNamespace(create_fresh_birth_policy=lambda: None)) is False


def test_trainer_requires_physics_detects_live_ppo_trainer() -> None:
    from lumina_core.rl.ppo_trainer import PPOTrainer

    trainer = PPOTrainer(engine=SimpleNamespace(rl_policy_model=None))
    assert trainer_requires_physics(trainer) is True


def test_reject_skips_stub_trainer(tmp_path: Path) -> None:
    host = SimpleNamespace(
        ppo_trainer=SimpleNamespace(create_fresh_birth_policy=lambda **_k: object()),
        workspace_root=tmp_path,
        birth_config=SimpleNamespace(trade_budget_cap=25000),
        birth_start_time=1.0,
    )
    assert reject_birth_if_physics_missing(host, target_trades=25000) is None


def test_reject_blocks_live_trainer_when_sb3_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from lumina_core.rl.ppo_trainer import PPOTrainer

    def _missing(**_kwargs: object) -> BirthPhysicsProbe:
        return BirthPhysicsProbe(
            ok=False,
            reason=PHYSICS_UNAVAILABLE,
            retryable=False,
            torch_ok=False,
            sb3_ok=False,
            gymnasium_ok=True,
            cuda_available=False,
            device_name=None,
            python_exe="python",
            missing=("stable_baselines3",),
            human_message="Leermotor ontbreekt (stable_baselines3).",
            next_action=INSTALL_HINT,
            recommended_actions=("install_birth_physics_stack", "retry_birth"),
        )

    monkeypatch.setattr("lumina_core.birth.physics_preflight.probe_birth_physics", _missing)
    host = SimpleNamespace(
        ppo_trainer=PPOTrainer(engine=SimpleNamespace(rl_policy_model=None)),
        workspace_root=tmp_path,
        birth_config=SimpleNamespace(trade_budget_cap=25000),
        birth_start_time=1.0,
    )
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    blocked = reject_birth_if_physics_missing(host, target_trades=25000)
    assert blocked is not None
    assert blocked["status"] == PHYSICS_UNAVAILABLE
    assert blocked["retryable"] is False


def test_enforce_writes_progress_and_does_not_recommend_wipe(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    svc = SimpleNamespace(workspace_root=tmp_path, _error=None)
    probe = BirthPhysicsProbe(
        ok=False,
        reason=PHYSICS_UNAVAILABLE,
        retryable=False,
        torch_ok=False,
        sb3_ok=False,
        gymnasium_ok=True,
        cuda_available=False,
        device_name=None,
        python_exe="python",
        missing=("stable_baselines3",),
        human_message="Leermotor ontbreekt (stable_baselines3).",
        next_action=INSTALL_HINT,
        recommended_actions=("install_birth_physics_stack", "retry_birth"),
    )
    payload = enforce_birth_physics(
        svc,
        target_trades=25000,
        start_time=1.0,
        training_mode="certified",
        probe=probe,
    )
    assert payload is not None
    assert payload["status"] == PHYSICS_UNAVAILABLE
    assert payload["retryable"] is False
    assert svc._error
    progress = (tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8")
    assert PHYSICS_UNAVAILABLE in progress
    assert "wipe_and_retry" not in progress
    assert "install_birth_physics_stack" in progress


def test_physics_failure_classifier_does_not_wipe() -> None:
    missing = ModuleNotFoundError("No module named 'stable_baselines3'")
    missing.name = "stable_baselines3"
    assert is_physics_failure(missing) is True
    attn = birth_exception_attention(missing)
    assert attn.retryable is False
    assert attn.reason_code == PHYSICS_UNAVAILABLE
    assert "wipe_and_retry" not in attn.actions
    assert "install_birth_physics_stack" in attn.actions
    other = RuntimeError("Fabric host down")
    assert is_physics_failure(other) is False
    default = birth_exception_attention(other)
    assert default.retryable is True
    assert "wipe_and_retry" in default.actions


def test_live_interpreter_probe_is_honest() -> None:
    result = probe_birth_physics()
    sb3 = importlib.util.find_spec("stable_baselines3") is not None
    torch = importlib.util.find_spec("torch") is not None
    gym = importlib.util.find_spec("gymnasium") is not None
    if not sb3 or not torch or not gym:
        assert result.ok is False
        assert result.retryable is False
        assert result.reason == PHYSICS_UNAVAILABLE
        return
    if result.ok:
        assert result.sb3_ok is True
        assert result.torch_ok is True
        return
    assert result.reason == CUDA_REQUIRED
    assert result.retryable is False
