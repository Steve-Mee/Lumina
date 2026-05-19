from __future__ import annotations

from pathlib import Path


def test_smart_setup_wizard_module_contains_required_screens() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "lumina_launcher" / "ui" / "smart_setup_wizard.py").read_text(encoding="utf-8")
    assert "render_smart_setup_wizard" in source
    assert "lumina_smart_setup_step" in source
    assert "welcome" in source
    assert "configure" in source
    assert "running" in source
    assert "success" in source
    assert "🚀 Alles Automatisch Instellen" in source
    assert "Ga door naar configuratie" in source
    assert "Hardware scannen" in source
    assert "SmartSetupService" in source
    assert "mark_complete=False" in source


def test_streamlit_main_two_phase_setup_gate() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "lumina_launcher" / "streamlit_main.py").read_text(encoding="utf-8")
    assert "smart_setup_service" in source
    assert "resolve_launcher_setup_state" in source
    assert "render_smart_setup_wizard" in source
    assert "render_setup_wizard" in source
    assert "Setup — Intelligence" in source or "Setup — {phase_label}" in source
