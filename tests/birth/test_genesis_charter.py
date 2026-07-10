"""Genesis auto-charter tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lumina_core.birth.genesis_charter import (
    compute_genesis_charter,
    load_genesis_charter,
    persist_genesis_charter,
    resolve_genesis_charter,
)


@pytest.mark.unit
def test_compute_genesis_charter(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "hardware_profile": "sweet",
                "birth_v2": {
                    "trade_budget_cap": 50000,
                    "prefer_real_data_only": True,
                    "curriculum": {
                        "stage1_winrate_recommended": 0.45,
                        "stage1_winrate_pass_threshold": 0.45,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    charter = compute_genesis_charter(tmp_path)
    assert charter.training_trades >= 5000
    assert 0.35 <= charter.stage1_winrate_pass_threshold <= 0.55
    assert charter.max_real_days >= 30
    assert charter.prefer_real_data_only is True


@pytest.mark.unit
def test_persist_genesis_charter(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump({"birth_v2": {"trade_budget_cap": 10000}}),
        encoding="utf-8",
    )
    charter = persist_genesis_charter(tmp_path)
    path = tmp_path / "state" / "lumina_genesis_charter.json"
    assert path.is_file()
    assert charter.to_dict()["auto_charter"] is True


@pytest.mark.unit
def test_load_and_resolve_genesis_charter(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump({"birth_v2": {"trade_budget_cap": 8000}}),
        encoding="utf-8",
    )
    persist_genesis_charter(tmp_path)
    loaded = load_genesis_charter(tmp_path)
    assert loaded is not None
    assert loaded.training_trades >= 5000
    resolved = resolve_genesis_charter(tmp_path)
    assert resolved.get("auto_charter") is True