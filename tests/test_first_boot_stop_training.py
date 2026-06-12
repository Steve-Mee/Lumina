"""Regression: Stop training must stop BirthService, not only lumina_runtime."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lumina_launcher.core.birth_actions import stop_birth_training
from lumina_launcher.core.first_boot import FirstBootManager
from lumina_launcher.services.birth_service import BirthService


@pytest.mark.unit
def test_stop_birth_training_calls_birth_service(tmp_path: Path) -> None:
    manager = FirstBootManager(tmp_path)
    birth_service = MagicMock(spec=BirthService)
    birth_service.is_running.return_value = True
    birth_service.is_stopping.return_value = False
    birth_service.stop_birth.return_value = {"status": "stopped", "message": "Birth gestopt."}
    process_manager = MagicMock()
    process_manager.stop_bot.return_value = (True, "Bot stopped")

    ok, msg = stop_birth_training(
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
def test_tauri_training_control_has_stop() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "tauri-app" / "src" / "components" / "birth" / "TrainingControlBar.tsx").read_text(
        encoding="utf-8"
    )
    assert "stopBirth" in source or "Stop" in source
