"""Checkpoint resumable SSOT (UI resume button visibility)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from lumina_core.birth.checkpoint import is_checkpoint_resumable
from lumina_launcher.services.birth_service import BirthService


@pytest.fixture(autouse=True)
def _reset_birth_service_singleton() -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    yield
    BirthService._instance = None  # type: ignore[attr-defined]


def _write_checkpoint(workspace: Path, *, policy_name: str = "lumina_ppo_policy.zip") -> None:
    policy_path = workspace / "lumina_agents" / "ppo" / policy_name
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text("zip", encoding="utf-8")
    payload = {
        "version": 3,
        "cumulative_trades": 500,
        "ppo_steps": 12000,
        "training_mode": "certified",
        "curriculum_stage": "stage1_trend",
        "policy_path": str(policy_path),
        "stage_metrics": {"stage_trades": 140},
    }
    ckpt = workspace / "state" / "lumina_birth_checkpoint.json"
    ckpt.parent.mkdir(parents=True, exist_ok=True)
    ckpt.write_text(json.dumps(payload), encoding="utf-8")


def test_is_checkpoint_resumable_true_with_valid_checkpoint(tmp_path: Path) -> None:
    _write_checkpoint(tmp_path)
    assert is_checkpoint_resumable(tmp_path) is True


def test_is_checkpoint_resumable_false_without_checkpoint_file(tmp_path: Path) -> None:
    assert is_checkpoint_resumable(tmp_path) is False


def test_is_checkpoint_resumable_false_when_policy_missing(tmp_path: Path) -> None:
    _write_checkpoint(tmp_path)
    (tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip").unlink()
    assert is_checkpoint_resumable(tmp_path) is False


def test_is_checkpoint_resumable_false_for_interrupted_progress_only(tmp_path: Path) -> None:
    progress = tmp_path / "state" / "lumina_birth_progress.json"
    progress.parent.mkdir(parents=True, exist_ok=True)
    progress.write_text(
        json.dumps(
            {
                "stage": "interrupted",
                "cumulative_trades": 6377,
                "ppo_steps": 900000,
            }
        ),
        encoding="utf-8",
    )
    assert is_checkpoint_resumable(tmp_path) is False


def test_wipe_all_sets_checkpoint_resumable_false(tmp_path: Path) -> None:
    _write_checkpoint(tmp_path)
    progress = tmp_path / "state" / "lumina_birth_progress.json"
    progress.write_text('{"stage":"interrupted","cumulative_trades":42}', encoding="utf-8")

    svc = BirthService()
    svc.configure_workspace(tmp_path)
    assert svc.checkpoint_resumable() is True

    result = svc.wipe_all_birth_data()
    assert result["status"] == "wiped"
    assert result["checkpoint_resumable"] is False
    assert svc.checkpoint_resumable() is False


def test_birth_status_enrich_includes_checkpoint_resumable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lumina_os.backend.birth_endpoints import _enrich_status_full

    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    birth_module = sys.modules["lumina_launcher.services.birth_service"]
    monkeypatch.setattr(birth_module, "birth_service", svc)
    monkeypatch.setattr("lumina_os.backend.birth_endpoints.birth_service", svc)

    _write_checkpoint(tmp_path)

    payload = _enrich_status_full(
        {
            "status": "interrupted",
            "progress": {
                "stage": "interrupted",
                "cumulative_trades": 6377,
                "ppo_steps": 900000,
            },
        }
    )
    assert payload["checkpoint_resumable"] is True
    assert payload["checkpoint_ppo_steps"] == 12000
    assert payload["curriculum_stage"] == "stage1_trend"
