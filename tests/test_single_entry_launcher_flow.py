"""Launcher entry and Command Deck lifecycle tests (post-Streamlit)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_launcher.core.birth_actions import persist_first_boot_settings, start_birth_training
from lumina_launcher.core.onboarding import resolve_app_surface


def test_main_module_prints_usage_without_streamlit(capsys: pytest.CaptureFixture[str]) -> None:
    from lumina_launcher.__main__ import main

    code = main()
    captured = capsys.readouterr()
    assert code == 0
    assert "Command Deck" in captured.out
    assert "streamlit" not in captured.out.lower()


def test_resolve_app_surface_returns_known_values() -> None:
    surface, reason = resolve_app_surface(
        setup_complete=False,
        birth_status="idle",
        artifacts_ok=False,
        backend_reachable=True,
        required_steps=["welcome"],
    )
    assert surface in {"setup", "birth", "deck"}
    assert isinstance(reason, str)


def test_process_manager_stops_birth_service() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "lumina_launcher" / "core" / "process_manager.py").read_text(encoding="utf-8")
    assert "birth_service.stop_birth" in source


def test_bootstrap_script_does_not_reference_streamlit() -> None:
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "bootstrap_lumina.py").read_text(encoding="utf-8")
    assert "streamlit" not in script.lower()
    assert "run_backend.ps1" in script or "Command Deck" in script


def test_start_script_uses_backend_not_streamlit() -> None:
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "start_lumina_with_training_dashboard.ps1").read_text(encoding="utf-8")
    assert "streamlit" not in script.lower() or "removed" in script.lower()
    assert "8000" in script or "run_backend" in script


def test_tauri_onboarding_gate_uses_app_surface() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "tauri-app" / "src" / "lib" / "onboardingPhase.ts").read_text(encoding="utf-8")
    assert "app_surface" in source
    assert "mapAppPhase" in source


def test_birth_actions_save_does_not_start_training(tmp_path: Path) -> None:
    from unittest.mock import MagicMock

    from lumina_launcher.core.first_boot import FirstBootManager
    from lumina_launcher.services.birth_service import BirthService

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


def test_birth_actions_requires_explicit_start(tmp_path: Path) -> None:
    from unittest.mock import MagicMock

    from lumina_launcher.services.birth_service import BirthService

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
