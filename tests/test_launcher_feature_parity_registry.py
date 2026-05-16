from __future__ import annotations

from pathlib import Path


def test_launcher_feature_parity_registry_exists_and_has_core_entries() -> None:
    root = Path(__file__).resolve().parents[1]
    registry = root / "docs" / "launcher_feature_parity_registry.md"
    assert registry.exists()
    text = registry.read_text(encoding="utf-8")
    for required_key in (
        "save_config_and_start_bot",
        "first_boot_training_trades",
        "first_boot_require_real_simulator_data",
        "sim_evolution_dashboard",
        "real_operations_dashboard",
        "single_active_tab_render",
    ):
        assert required_key in text
