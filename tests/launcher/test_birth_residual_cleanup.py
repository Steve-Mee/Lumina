"""Regression: demote fixed UnboundLocal birth residual without wiping data."""

from __future__ import annotations

import json
from pathlib import Path

from lumina_launcher.services.birth_residual_cleanup import (
    demote_fixed_birth_residuals,
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
