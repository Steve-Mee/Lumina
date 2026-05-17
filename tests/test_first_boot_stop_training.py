"""Regression: Stop training must stop BirthService, not only lumina_runtime."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lumina_launcher.core.first_boot import FirstBootManager
from lumina_launcher.services.birth_service import BirthService
from lumina_launcher.ui.tabs import first_boot as fb


@pytest.mark.unit
def test_stop_birth_training_calls_birth_service(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(fb.st, "session_state", {})
    manager = FirstBootManager(tmp_path)
    birth_service = MagicMock(spec=BirthService)
    birth_service.is_running.return_value = True
    birth_service.is_stopping.return_value = False
    birth_service.stop_birth.return_value = {"status": "stopped", "message": "Birth gestopt."}
    process_manager = MagicMock()
    process_manager.stop_bot.return_value = (True, "Bot stopped")

    ok, msg = fb._stop_birth_training(
        first_boot_manager=manager,
        birth_service=birth_service,
        backend_client=None,
        process_manager=process_manager,
        progress={"stage": "training_running"},
        stage="training_running",
    )

    assert ok is True
    birth_service.stop_birth.assert_called_once()
    process_manager.stop_bot.assert_called_once()
    assert manager.pause_flag_path.exists()


@pytest.mark.unit
def test_first_boot_tab_has_unified_stop_button() -> None:
    source = Path(fb.__file__).read_text(encoding="utf-8")
    assert "first_boot_stop_training" in source
    assert "_stop_birth_training" in source
    assert "on_click=_on_stop_training_click" in source
    assert "Stop training" in source
