"""source=hypothetical_adr0055 never writes live calibrator state."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.risk.cost_model_calibrator import load_reconciled_rows, run_daily_calibration
from tests.research_bridge.s2_helpers import broker_fill, make_translator


@pytest.mark.unit
@pytest.mark.safety_gate
def test_hypothetical_ingest_does_not_write_live_calibrator(tmp_path: Path) -> None:
    translator, _observe, _index, _bus = make_translator(tmp_path)
    fill = broker_fill(source="hypothetical_adr0055", fill_id="shadow-1")
    result = translator.ingest(fill, client_order_id="cid-1")
    assert result.calibrated is False
    assert translator.calibrator_rows() == ()
    jsonl = tmp_path / "live_calibrator.jsonl"
    if jsonl.exists():
        assert "hypothetical_adr0055" not in jsonl.read_text(encoding="utf-8")
    state = tmp_path / "cost_model_calibration.json"
    run_daily_calibration(audit_path=jsonl if jsonl.exists() else tmp_path / "empty.jsonl", state_path=state)
    if jsonl.exists():
        assert load_reconciled_rows(jsonl) == []


@pytest.mark.unit
def test_hypothetical_row_in_audit_is_skipped(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    rows = [
        {
            "event": "reconciled",
            "ts": "2026-05-01T10:00:00+00:00",
            "symbol": "MES",
            "quantity": 1,
            "commission": 0.94,
            "slippage_usd": 1.25,
            "source": "hypothetical_adr0055",
        },
        {
            "event": "reconciled",
            "ts": "2026-05-01T11:00:00+00:00",
            "symbol": "MES",
            "quantity": 1,
            "commission": 0.94,
            "slippage_usd": 1.25,
            "source": "broker",
        },
    ]
    audit.write_text("\n".join(json.dumps(item) for item in rows), encoding="utf-8")
    loaded = load_reconciled_rows(audit)
    assert len(loaded) == 1
    assert loaded[0]["source"] == "broker"
    state = tmp_path / "cost_model_calibration.json"
    result = run_daily_calibration(audit_path=audit, state_path=state, instrument="MES")
    assert result.sample_count == 1
    assert "hypothetical_adr0055" not in state.read_text(encoding="utf-8")


@pytest.mark.unit
@pytest.mark.safety_gate
def test_unknown_source_is_not_live_calibrated(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    rows = [
        {
            "event": "reconciled",
            "ts": "2026-05-01T10:00:00+00:00",
            "symbol": "MES",
            "quantity": 1,
            "commission": 0.01,
            "slippage_usd": 0.0,
            "source": "research_four_leg",
        }
    ]
    audit.write_text("\n".join(json.dumps(item) for item in rows) + "\n", encoding="utf-8")
    assert load_reconciled_rows(audit) == []
    state = tmp_path / "cost_model_calibration.json"
    result = run_daily_calibration(audit_path=audit, state_path=state, instrument="MES")
    assert result.sample_count == 0
