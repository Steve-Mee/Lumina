from __future__ import annotations

from pathlib import Path


def test_setup_persist_module_contains_required_helpers() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "lumina_launcher" / "services" / "setup_persist.py").read_text(encoding="utf-8")
    assert "persist_setup_configuration" in source
    assert "resolve_mode_matrix" in source
    assert "SmartSetupService" not in source


def test_onboarding_endpoints_expose_app_surface() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "lumina_os" / "backend" / "setup_endpoints.py").read_text(encoding="utf-8")
    assert "resolve_app_surface" in source
    assert "app_surface" in source


def test_tauri_onboarding_wizard_steps() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "tauri-app" / "src" / "lib" / "onboardingSteps.ts").read_text(encoding="utf-8")
    assert "welcome" in source
    assert "birth" in source
