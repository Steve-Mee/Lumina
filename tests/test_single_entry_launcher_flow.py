"""Launcher entry and Command Deck lifecycle tests (post-Streamlit)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_launcher.core.onboarding import resolve_app_surface


def test_main_module_prints_usage_without_streamlit(capsys: pytest.CaptureFixture[str]) -> None:
    from lumina_launcher.cli.dispatch import main

    code = main([])
    captured = capsys.readouterr()
    assert code == 0
    assert "Command Deck" in captured.out
    assert "Autonomous SIM/Paper loop" in captured.out


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


def test_process_manager_stop_all_activities_stops_the_bot() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "lumina_launcher" / "core" / "process_manager.py").read_text(encoding="utf-8")
    assert "def stop_all_activities" in source
    assert "self.stop_bot()" in source
    assert "lumina_launcher.services.birth_service" not in source


def test_run_backend_uses_venv_python_not_system_python() -> None:
    root = Path(__file__).resolve().parents[1]
    script = (root / "lumina_os" / "run_backend.ps1").read_text(encoding="utf-8")
    assert ".venv\\Scripts\\python.exe" in script
    assert "System Python is forbidden for Birth" in script
    assert "Resolve-LuminaPython" in script


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


