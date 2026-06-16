from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lumina_launcher.services.birth_service import BirthService


@pytest.mark.unit
def test_sanitize_running_progress_replaces_stale_curriculum_failed(tmp_path: Path) -> None:
    service = BirthService()
    service.configure_workspace(tmp_path)
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "lumina_birth_progress.json").write_text(
        json.dumps(
            {
                "phase": "curriculum_failed",
                "stage": "training_running",
                "message": "Curriculum stage failed: trend winrate=100.00% trades=1",
            }
        ),
        encoding="utf-8",
    )

    alive_thread = MagicMock()
    alive_thread.is_alive.return_value = True
    service._thread = alive_thread
    service._start_time = 1.0

    status = service.get_status()
    progress = status.get("progress") or {}

    assert progress.get("phase") == "curriculum_learning"
    assert progress.get("stage") == "training_running"
