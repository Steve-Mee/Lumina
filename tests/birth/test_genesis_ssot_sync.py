"""Genesis (first_boot) settings must sync to birth_v2 engine config."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from lumina_core.birth.config import load_birth_v2_config, resolve_effective_trade_budget
from lumina_launcher.core.first_boot import FirstBootManager
from lumina_launcher.services.setup_persist import persist_tauri_quick_config


@pytest.mark.unit
def test_save_full_settings_syncs_birth_v2_trade_budget_cap(tmp_path: Path) -> None:
    mgr = FirstBootManager(tmp_path)
    mgr.save_full_settings(
        training_trades=30_000,
        prefer_real_data_only=True,
        max_real_days=120,
        allow_minimal_synthetic_fallback=True,
        mark_user_configured=True,
    )
    raw = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8")) or {}
    assert raw["first_boot"]["training_trades"] == 30_000
    assert raw["birth_v2"]["trade_budget_cap"] == 30_000
    assert raw["birth_v2"]["max_real_days"] == 120
    assert raw["birth_v2"]["prefer_real_data_only"] is True

    cfg = load_birth_v2_config(tmp_path)
    assert cfg.trade_budget_cap == 30_000
    assert cfg.max_real_days == 120
    assert cfg.prefer_real_data_only is True


@pytest.mark.unit
def test_save_full_settings_syncs_stage1_winrate_gate(tmp_path: Path) -> None:
    mgr = FirstBootManager(tmp_path)
    mgr.save_full_settings(
        training_trades=25_000,
        prefer_real_data_only=True,
        max_real_days=90,
        allow_minimal_synthetic_fallback=False,
        stage1_winrate_pass_threshold=0.38,
        mark_user_configured=True,
    )
    raw = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8")) or {}
    assert raw["birth_v2"]["curriculum"]["stage1_winrate_pass_threshold"] == 0.38
    settings = mgr.read_settings()
    assert settings["stage1_winrate_pass_threshold"] == 0.38


@pytest.mark.unit
def test_persist_tauri_quick_config_syncs_winrate_gate(tmp_path: Path) -> None:
    mgr = FirstBootManager(tmp_path)
    snapshot = MagicMock()
    snapshot.ram_gb = 32
    snapshot.gpu_vram_gb = 8
    snapshot.vllm_supported = False
    snapshot.profile_tier = "high"

    setup_service = MagicMock()
    setup_service.apply_recommended_config.return_value = MagicMock(
        to_dict=lambda: {"name": "model", "success": True}
    )
    model_service = MagicMock()
    model_service.get_recommended.return_value = MagicMock(key="test-model")
    model_service.get_model.return_value = MagicMock(key="test-model")
    config_manager = MagicMock()
    config_manager.load_yaml_config.return_value = {"sim": {}, "real": {}, "evolution": {}, "broker": {}}
    config_manager.parse_env_file.return_value = {}

    persist_tauri_quick_config(
        workspace_root=tmp_path,
        setup_service=setup_service,
        config_manager=config_manager,
        first_boot_manager=mgr,
        model_service=model_service,
        snapshot=snapshot,
        mode_selection="sim",
        credentials={
            "LUMINA_JWT_SECRET_KEY": "x",
            "CROSSTRADE_TOKEN": "x",
            "CROSSTRADE_ACCOUNT": "x",
        },
        risk={"kelly_fraction": 1.0, "max_total_open_risk": 3000, "real_capital_safety_threshold_usd": 1000},
        evolution={"approval_required": False, "aggressive_evolution": True, "max_mutation_depth": "radical"},
        training={
            "training_trades": 20_000,
            "prefer_real_data_only": True,
            "max_real_days": 60,
            "allow_minimal_synthetic_fallback": False,
            "require_real_simulator_data": True,
            "stage1_winrate_pass_threshold": 0.40,
        },
    )
    raw = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8")) or {}
    assert raw["birth_v2"]["curriculum"]["stage1_winrate_pass_threshold"] == 0.40


@pytest.mark.unit
def test_resolve_effective_trade_budget_prefers_start_arg() -> None:
    raw = {
        "birth_v2": {"trade_budget_cap": 10_000},
        "first_boot": {"training_trades": 25_000},
    }
    cap, source = resolve_effective_trade_budget(raw, target_trades=15_000)
    assert cap == 15_000
    assert source == "start_arg.target_trades"


@pytest.mark.unit
def test_resolve_effective_trade_budget_falls_back_to_birth_v2() -> None:
    raw = {
        "birth_v2": {"trade_budget_cap": 20_000},
        "first_boot": {"training_trades": 25_000},
    }
    cap, source = resolve_effective_trade_budget(raw, target_trades=None)
    assert cap == 20_000
    assert source == "birth_v2.trade_budget_cap"
