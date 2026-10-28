"""Regression: demote fixed UnboundLocal birth residual without wiping data."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.birth.physics_preflight import (
    INSTALL_HINT,
    PHYSICS_UNAVAILABLE,
    BirthPhysicsProbe,
)
from lumina_launcher.services.birth_residual_cleanup import (
    demote_fixed_birth_residuals,
    is_fixed_physics_logger_residual,
    is_fixed_write_birth_progress_residual,
)


def test_detects_unboundlocal_residual() -> None:
    assert is_fixed_write_birth_progress_residual(
        {
            "stage": "error",
            "phase": "error",
            "message": (
                "UnboundLocalError: cannot access local variable "
                "'write_birth_progress' where it is not associated with a value"
            ),
        }
    )
    assert not is_fixed_write_birth_progress_residual(
        {"stage": "error", "phase": "error", "message": "history_unavailable"}
    )
    assert not is_fixed_write_birth_progress_residual(
        {"stage": "training_running", "phase": "curriculum_learning", "message": "ok"}
    )


def test_demote_preserves_manifest(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    progress = {
        "stage": "error",
        "phase": "error",
        "message": (
            "UnboundLocalError: cannot access local variable "
            "'write_birth_progress' where it is not associated with a value"
        ),
        "last_error": (
            "UnboundLocalError: cannot access local variable "
            "'write_birth_progress' where it is not associated with a value"
        ),
        "progress_pct": 26.0,
        "target_trades": 25000,
        "cumulative_trades": 0,
        "ppo_steps": 0,
        "data_manifest": {
            "days_loaded": 57,
            "tick_count": 212248,
            "real_data_pct": 100.0,
        },
        "curriculum_stage": "pipeline_boot",
        "needs_attention": True,
    }
    (state / "lumina_birth_progress.json").write_text(
        json.dumps(progress), encoding="utf-8"
    )
    result = demote_fixed_birth_residuals(tmp_path)
    assert result["changed"] is True
    assert result["has_manifest"] is True
    out = json.loads((state / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert out["stage"] == "paused"
    assert out["phase"] == "residual_cleared_ready"
    assert out.get("data_manifest", {}).get("days_loaded") == 57
    assert out.get("retryable") is True
    assert "UnboundLocalError" not in str(out.get("message") or "")


def test_demote_noop_for_other_errors(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    (state / "lumina_birth_progress.json").write_text(
        json.dumps(
            {
                "stage": "error",
                "phase": "error",
                "message": "history_unavailable",
            }
        ),
        encoding="utf-8",
    )
    result = demote_fixed_birth_residuals(tmp_path)
    assert result["changed"] is False
    out = json.loads((state / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert out["message"] == "history_unavailable"


def test_detects_ppo_evolution_logger_residual() -> None:
    assert is_fixed_physics_logger_residual(
        {
            "stage": "error",
            "phase": "error",
            "message": (
                "RuntimeError: stable-baselines3 is required for PPOEvolutionLogger. "
                "Install with: pip install stable-baselines3"
            ),
        }
    )
    assert not is_fixed_physics_logger_residual(
        {"stage": "error", "phase": "error", "message": "history_unavailable"}
    )


def test_demote_physics_residual_when_probe_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    (state / "lumina_birth_progress.json").write_text(
        json.dumps(
            {
                "stage": "error",
                "phase": "error",
                "message": (
                    "RuntimeError: stable-baselines3 is required for PPOEvolutionLogger. "
                    "Install with: pip install stable-baselines3"
                ),
                "last_error": (
                    "RuntimeError: stable-baselines3 is required for PPOEvolutionLogger. "
                    "Install with: pip install stable-baselines3"
                ),
                "progress_pct": 27.0,
                "target_trades": 25000,
                "data_manifest": {"days_loaded": 91, "tick_count": 334560},
                "needs_attention": True,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "lumina_core.birth.physics_preflight.probe_birth_physics",
        lambda **_k: BirthPhysicsProbe(
            ok=True,
            reason="physics_ready",
            retryable=True,
            torch_ok=True,
            sb3_ok=True,
            gymnasium_ok=True,
            cuda_available=True,
            device_name="NVIDIA GeForce RTX 5070 Ti",
            python_exe="venv-python",
            missing=(),
            human_message="Leermotor klaar.",
            next_action=None,
            recommended_actions=(),
        ),
    )
    result = demote_fixed_birth_residuals(tmp_path)
    assert result["changed"] is True
    assert result["reason"] == "demoted_physics_logger_residual"
    out = json.loads((state / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert out["stage"] == "not_started"
    assert out["phase"] == "residual_cleared_ready"
    assert out.get("needs_attention") is False
    assert "PPOEvolutionLogger" not in str(out.get("message") or "")
    assert "pip install stable-baselines3" not in str(out.get("last_error") or "")
    assert out.get("data_manifest", {}).get("days_loaded") == 91
    assert "WIPE_FULL" in str(out.get("message") or "")


def test_physics_residual_stays_when_probe_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    original = (
        "RuntimeError: stable-baselines3 is required for PPOEvolutionLogger. "
        "Install with: pip install stable-baselines3"
    )
    (state / "lumina_birth_progress.json").write_text(
        json.dumps({"stage": "error", "phase": "error", "message": original}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "lumina_core.birth.physics_preflight.probe_birth_physics",
        lambda **_k: BirthPhysicsProbe(
            ok=False,
            reason=PHYSICS_UNAVAILABLE,
            retryable=False,
            torch_ok=False,
            sb3_ok=False,
            gymnasium_ok=False,
            cuda_available=False,
            device_name=None,
            python_exe="system-python",
            missing=("stable_baselines3",),
            human_message="Leermotor ontbreekt (stable_baselines3).",
            next_action=INSTALL_HINT,
            recommended_actions=("install_birth_physics_stack", "retry_birth"),
        ),
    )
    result = demote_fixed_birth_residuals(tmp_path)
    assert result["changed"] is False
    assert result["reason"] == "physics_still_unavailable"
    out = json.loads((state / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert out["message"] == original
