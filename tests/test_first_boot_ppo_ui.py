from __future__ import annotations

from pathlib import Path


def test_first_boot_ui_uses_phase_specific_ppo_status() -> None:
    root = Path(__file__).resolve().parents[1]
    first_boot_src = (root / "lumina_launcher" / "ui" / "tabs" / "first_boot.py").read_text(encoding="utf-8")
    dashboard_src = (root / "lumina_launcher" / "ui" / "tabs" / "training_dashboard.py").read_text(encoding="utf-8")

    assert "_render_birth_phase_status_banner" in first_boot_src
    assert "_render_ppo_progress_bars" in first_boot_src
    assert "Totaal PPO:" in first_boot_src
    assert "Huidige PPO-batch:" in first_boot_src
    assert "SIM-training is voltooid" not in first_boot_src
    assert "PPO policy-training loopt nog" not in first_boot_src
    assert "SIM-deel is voltooid" not in dashboard_src
    assert "_render_ppo_progress_bars" in dashboard_src
