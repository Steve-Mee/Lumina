"""Regression: Save Settings must not start Birth Phase; start requires explicit gate."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lumina_launcher.core.birth_actions import persist_first_boot_settings, start_birth_training
from lumina_launcher.core.first_boot import FirstBootManager
from lumina_launcher.services.birth_service import BirthService


@pytest.mark.unit
def test_save_settings_never_calls_start_birth(tmp_path: Path) -> None:
    manager = FirstBootManager(tmp_path)
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    birth_service = MagicMock(spec=BirthService)
    birth_service.is_running.return_value = False

    persist_first_boot_settings(
        manager,
        training_trades=25_000,
        prefer_real_data_only=True,
        max_real_days=365,
        allow_minimal_synthetic_fallback=False,
        require_real_simulator_data=True,
    )

    birth_service.start_birth.assert_not_called()


@pytest.mark.unit
def test_start_birth_requires_explicit_flag(tmp_path: Path) -> None:
    birth_service = MagicMock(spec=BirthService)
    birth_service.is_running.return_value = False

    ok, msg = start_birth_training(
        birth_service=birth_service,
        backend_client=None,
        workspace_root=tmp_path,
        target_trades=25_000,
        explicit_user_start=False,
    )

    assert ok is False
    assert "expliciete" in msg.lower()
    birth_service.start_birth.assert_not_called()


@pytest.mark.unit
def test_start_birth_with_explicit_flag_calls_service(tmp_path: Path) -> None:
    birth_service = MagicMock(spec=BirthService)
    birth_service.start_birth.return_value = {"status": "started", "message": "ok"}

    ok, msg = start_birth_training(
        birth_service=birth_service,
        backend_client=None,
        workspace_root=tmp_path,
        target_trades=25_000,
        explicit_user_start=True,
    )

    assert ok is True
    birth_service.start_birth.assert_called_once()
    call_kwargs = birth_service.start_birth.call_args.kwargs
    assert call_kwargs.get("explicit_user_start") is True


@pytest.mark.unit
def test_birth_service_rejects_without_explicit_user_start(tmp_path: Path) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)

    result = svc.start_birth(target_trades=5000, explicit_user_start=False)

    assert result["status"] == "rejected"
    assert svc._thread is None  # type: ignore[attr-defined]
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_tauri_birth_settings_panel_has_save_and_start() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "tauri-app" / "src" / "components" / "birth" / "BirthSettingsPanel.tsx").read_text(
        encoding="utf-8"
    )
    assert "saveBirthSettings" in source or "saveSettings" in source
    assert "saveBirthSettings" in source
