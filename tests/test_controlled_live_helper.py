from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import yaml


def _load_helper_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "controlled_live_helper.py"
    spec = importlib.util.spec_from_file_location("controlled_live_helper", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.safety_gate
def test_inject_config_preserves_sim_first_validation_rails(tmp_path: Path) -> None:
    helper = _load_helper_module()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "mode": "real",
                "broker": {"backend": "live"},
                "risk_controller": {"daily_loss_cap": -9999.0},
                "trading": {},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    exit_code = helper.inject_config(config_path, mode="sim", broker_mode="paper")
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["mode"] == "sim"
    assert payload["broker"]["backend"] == "paper"
    assert payload["risk_controller"]["daily_loss_cap"] == -150.0
    assert payload["risk_controller"]["max_total_open_risk"] == 150.0
    assert payload["risk_controller"]["enforce_session_guard"] is True
    assert payload["trading"]["eod_force_close_minutes_before_session_end"] == 30
    assert payload["trading"]["eod_no_new_trades_minutes_before_session_end"] == 60
    assert payload["trading"]["kelly_fraction_max"] == 0.25


@pytest.mark.safety_gate
def test_contract_check_prefers_latest_summary_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    helper = _load_helper_module()
    state_dir = tmp_path / "state"
    state_dir.mkdir()

    (state_dir / "last_run_summary_live_30m_paper.json").write_text(
        json.dumps(
            {
                "runtime": "headless",
                "broker_status": "live_connected",
                "total_trades": 1,
                "risk_events": 0,
                "var_breach_count": 0,
            }
        ),
        encoding="utf-8",
    )
    (state_dir / "last_run_summary.json").write_text(
        json.dumps(
            {
                "runtime": "headless",
                "broker_status": "paper_ok",
                "total_trades": 12,
                "pnl_realized": 125.0,
                "risk_events": 0,
                "var_breach_count": 0,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    assert helper.contract_check("paper_ok") == 0
