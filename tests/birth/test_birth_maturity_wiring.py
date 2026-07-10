"""Tests for birth maturity status wiring (Fase 6B)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_launcher.services.birth_maturity_wiring import maturity_status_fields


@pytest.mark.unit
def test_maturity_status_fields_includes_genesis_charter(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir(parents=True)
    (state / "lumina_genesis_charter.json").write_text(
        json.dumps(
            {
                "training_trades": 12000,
                "stage1_winrate_pass_threshold": 0.44,
                "max_real_days": 90,
                "prefer_real_data_only": True,
                "rationale": {},
                "auto_charter": True,
            }
        ),
        encoding="utf-8",
    )
    fields = maturity_status_fields(tmp_path)
    charter = fields.get("genesis_charter")
    assert isinstance(charter, dict)
    assert charter.get("training_trades") == 12000


@pytest.mark.unit
def test_maturity_status_fields_extracts_autonomy_metrics(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir(parents=True)
    (state / "lumina_birth_checkpoint.json").write_text(
        json.dumps(
            {
                "stage_metrics": {
                    "death_spiral_repeat_count": 2,
                    "policy_swarm_active": True,
                    "oos_proxy_winrate": 0.41,
                    "stage_trades": 100,
                }
            }
        ),
        encoding="utf-8",
    )
    fields = maturity_status_fields(tmp_path)
    autonomy = fields.get("autonomy_metrics")
    assert isinstance(autonomy, dict)
    assert autonomy.get("death_spiral_repeat_count") == 2
    assert autonomy.get("policy_swarm_active") is True
    assert autonomy.get("oos_proxy_winrate") == 0.41