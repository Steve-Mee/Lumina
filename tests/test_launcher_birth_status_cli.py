"""Birth status CLI tests."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from lumina_launcher.birth.status_cli import run_birth_status


@pytest.mark.unit
def test_birth_status_json_shape(capsys: pytest.CaptureFixture[str]) -> None:
    payload = {
        "status": "running",
        "progress": {
            "stage": "ppo_training",
            "phase": "curriculum_learning",
            "message": "Training",
            "progress_pct": 42.0,
            "trades_done": 1000,
            "target_trades": 25000,
            "stage_index": 3,
            "auto_recovery_active": False,
        },
        "runner": "thread",
    }
    with patch("lumina_launcher.birth.status_cli.birth_service.get_status", return_value=payload):
        code = run_birth_status(as_json=True)
    captured = capsys.readouterr()
    assert code == 0
    summary = json.loads(captured.out)
    assert summary["status"] == "running"
    assert summary["stage"] == "ppo_training"
    assert summary["phase"] == "curriculum_learning"
    assert summary["progress_pct"] == 42.0
    assert summary["runner"] == "thread"


@pytest.mark.unit
def test_birth_status_text_output(capsys: pytest.CaptureFixture[str]) -> None:
    with patch(
        "lumina_launcher.birth.status_cli.birth_service.get_status",
        return_value={"status": "idle", "progress": {}},
    ):
        code = run_birth_status(as_json=False)
    captured = capsys.readouterr()
    assert code == 0
    assert "status=idle" in captured.out
