from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lumina_launcher.services.birth_service import BirthService
from lumina_launcher.services.birth_status_mapper_get import sanitize_running_progress


@pytest.fixture(autouse=True)
def _reset_birth_service_singleton() -> None:
    """Coverage suite shares one process; BirthService is a singleton."""
    inst = getattr(BirthService, "_instance", None)
    if inst is not None and getattr(inst, "_stop_requested", None) is not None:
        inst._stop_requested.clear()
    BirthService._instance = None
    yield
    inst = getattr(BirthService, "_instance", None)
    if inst is not None and getattr(inst, "_stop_requested", None) is not None:
        inst._stop_requested.clear()
    BirthService._instance = None


def _isolated_running_service(tmp_path: Path) -> BirthService:
    """Fresh singleton with a live worker and no stop/recovery side effects."""
    service = BirthService()
    # No-op before workspace bind: configure_workspace itself calls recovery.
    service._maybe_execute_autonomous_recovery = lambda: None  # type: ignore[method-assign]
    service._maybe_auto_resume_stalled_birth = lambda: None  # type: ignore[method-assign]
    service.configure_workspace(tmp_path)
    if getattr(service, "_stop_requested", None) is not None:
        service._stop_requested.clear()
    service._error = None
    service._result = None
    service._stalled_auto_resume_attempted = True
    alive_thread = MagicMock()
    alive_thread.is_alive.return_value = True
    service._thread = alive_thread
    service._start_time = 1.0
    # Coverage suite can leave is_stopping() true on the singleton Event.
    # Pin the two predicates the mapper uses so sanitize is actually exercised.
    service.is_running = lambda: True  # type: ignore[method-assign]
    service.is_stopping = lambda: False  # type: ignore[method-assign]
    return service


@pytest.mark.unit
def test_sanitize_running_progress_replaces_stale_curriculum_failed_direct() -> None:
    sanitized = sanitize_running_progress(
        {
            "phase": "curriculum_failed",
            "stage": "training_running",
            "message": "Curriculum stage failed: trend winrate=100.00% trades=1",
        }
    )
    assert sanitized.get("phase") == "curriculum_learning"
    assert sanitized.get("stage") == "training_running"


@pytest.mark.unit
def test_sanitize_running_progress_replaces_stale_stage_stalled_direct() -> None:
    sanitized = sanitize_running_progress(
        {
            "phase": "stage_stalled",
            "stage": "stage_stalled",
            "terminal_stall_reason": "plateau_evolution_exhausted",
            "needs_attention": True,
        }
    )
    assert sanitized.get("phase") == "loading_history"
    assert sanitized.get("stage") == "loading_data"
    assert sanitized.get("needs_attention") is False
    assert "terminal_stall_reason" not in sanitized


@pytest.mark.unit
def test_sanitize_running_progress_replaces_stale_curriculum_failed(tmp_path: Path) -> None:
    service = _isolated_running_service(tmp_path)
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

    status = service.get_status()
    progress = status.get("progress") or {}

    assert status.get("status") == "running"
    assert progress.get("phase") == "curriculum_learning"
    assert progress.get("stage") == "training_running"


@pytest.mark.unit
def test_sanitize_running_progress_replaces_stale_stage_stalled(tmp_path: Path) -> None:
    service = _isolated_running_service(tmp_path)
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "lumina_birth_progress.json").write_text(
        json.dumps(
            {
                "phase": "stage_stalled",
                "stage": "stage_stalled",
                "terminal_stall_reason": "plateau_evolution_exhausted",
                "needs_attention": True,
            }
        ),
        encoding="utf-8",
    )

    status = service.get_status()
    progress = status.get("progress") or {}

    assert status.get("status") == "running"
    assert progress.get("phase") == "loading_history"
    assert progress.get("stage") == "loading_data"
    assert progress.get("needs_attention") is False
