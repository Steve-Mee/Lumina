from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core import logging_utils


@pytest.mark.unit
def test_monitoring_telemetry_writers_create_expected_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # gegeven
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LUMINA_WORKSPACE_ROOT", str(tmp_path))

    # wanneer
    logging_utils.record_twin_decision_monitoring(
        dna_hash="abc123",
        score=0.91,
        recommendation=True,
        risk_flags=["none"],
        explanation="ok",
    )
    logging_utils.record_gate_rejection_monitoring(
        gate_name="risk_var_es",
        reason="var breach",
        mode="real",
        symbol="MES",
        side="BUY",
        decision_context_id="ctx-1",
    )
    logging_utils.record_model_load_time_monitoring(
        model_type="ppo",
        model_path="lumina_agents/ppo/lumina_ppo_policy.zip",
        load_time_sec=1.23,
        status="loaded",
    )
    logging_utils.write_ppo_policy_metadata(
        policy_path="lumina_agents/ppo/lumina_ppo_policy.zip",
        policy_version="ppo-1",
        total_training_steps=1000,
        training_time_sec=4.2,
    )
    logging_utils.write_runtime_monitoring_snapshot(
        {
            "mode": "real",
            "live_position_qty": 2,
            "daily_pnl": 123.45,
            "consecutive_losses": 1,
            "last_trades": [{"signal": "BUY", "pnl": 12.0}],
        }
    )

    # dan
    twin_path = tmp_path / "state/monitoring_twin_decisions.jsonl"
    gate_path = tmp_path / "state/monitoring_gate_rejections.jsonl"
    load_path = tmp_path / "state/monitoring_model_load_times.jsonl"
    ppo_meta_path = tmp_path / "state/ppo_policy_metadata.json"
    runtime_path = tmp_path / "state/monitoring_runtime_metrics.json"

    assert twin_path.exists()
    assert gate_path.exists()
    assert load_path.exists()
    assert ppo_meta_path.exists()
    assert runtime_path.exists()

    twin_row = json.loads(twin_path.read_text(encoding="utf-8").splitlines()[-1])
    gate_row = json.loads(gate_path.read_text(encoding="utf-8").splitlines()[-1])
    load_row = json.loads(load_path.read_text(encoding="utf-8").splitlines()[-1])
    ppo_meta = json.loads(ppo_meta_path.read_text(encoding="utf-8"))
    runtime_meta = json.loads(runtime_path.read_text(encoding="utf-8"))

    assert twin_row["dna_hash"] == "abc123"
    assert gate_row["gate_name"] == "risk_var_es"
    assert load_row["status"] == "loaded"
    assert ppo_meta["total_training_steps"] == 1000
    assert runtime_meta["live_position_qty"] == 2

    pnl_hist = tmp_path / "state/monitoring_daily_pnl.jsonl"
    assert pnl_hist.exists()
    pnl_row = json.loads(pnl_hist.read_text(encoding="utf-8").splitlines()[-1])
    assert pnl_row["daily_pnl"] == 123.45
