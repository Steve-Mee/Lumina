"""Genesis (first_boot) settings must sync to birth_v2 engine config."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lumina_core.birth.config import load_birth_v2_config, resolve_effective_trade_budget
from lumina_launcher.core.first_boot import FirstBootManager


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
