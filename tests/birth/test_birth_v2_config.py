"""Birth v2 config loading — trade budget SSOT."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.birth.config import load_birth_v2_config, resolve_effective_trade_budget, resolve_trade_budget_cap


@pytest.mark.unit
def test_resolve_trade_budget_cap_from_birth_v2() -> None:
    raw = {
        "birth_v2": {"trade_budget_cap": 25000},
        "first_boot": {"training_trades": 10000},
    }
    cap, source = resolve_trade_budget_cap(raw)
    assert cap == 25000
    assert source == "birth_v2.trade_budget_cap"


@pytest.mark.unit
def test_resolve_trade_budget_cap_falls_back_to_first_boot() -> None:
    raw = {
        "birth_v2": {"max_real_days": 90},
        "first_boot": {"training_trades": 25000},
    }
    cap, source = resolve_trade_budget_cap(raw)
    assert cap == 25000
    assert source == "first_boot.training_trades"


@pytest.mark.unit
def test_load_birth_v2_config_uses_first_boot_when_cap_missing(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(
        "birth_v2:\n  max_real_days: 90\nfirst_boot:\n  training_trades: 25000\n",
        encoding="utf-8",
    )
    cfg = load_birth_v2_config(tmp_path)
    assert cfg.trade_budget_cap == 25000


@pytest.mark.unit
def test_resolve_effective_trade_budget_without_start_arg() -> None:
    raw = {"birth_v2": {"trade_budget_cap": 18000}, "first_boot": {"training_trades": 25000}}
    cap, source = resolve_effective_trade_budget(raw)
    assert cap == 18000
    assert source == "birth_v2.trade_budget_cap"
