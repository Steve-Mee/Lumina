"""One FillEvent fans out to monitor observe and calibrator JSONL (plan §3.3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.research_bridge.fill_translator import observe_metric
from lumina_core.risk.cost_model_calibrator import load_reconciled_rows
from tests.research_bridge.s2_helpers import broker_fill, make_translator


@pytest.mark.unit
@pytest.mark.safety_gate
def test_fill_event_fans_out_to_observe_and_calibrator(tmp_path: Path) -> None:
    translator, observe, _index, _bus = make_translator(tmp_path)
    fill = broker_fill(price=5000.25, commission=0.0)
    result = translator.ingest(fill, client_order_id="cid-1", reference_price=5000.0)
    assert result.observed is True
    assert result.calibrated is True
    assert result.published is True
    ssot = result.fill.ssot_payload()
    assert ssot["fill_price"] == pytest.approx(5000.25)
    assert ssot["qty"] == 1
    assert ssot["commission"] == pytest.approx(0.94)
    assert ssot["source"] == "broker"
    assert observe.calls == [("hyp-s2", observe_metric(result.fill))]
    rows = translator.calibrator_rows()
    assert len(rows) == 1
    assert rows[0]["fill_price"] == pytest.approx(ssot["fill_price"])
    assert rows[0]["qty"] == ssot["qty"]
    assert rows[0]["commission"] == pytest.approx(ssot["commission"])
    assert rows[0]["slippage_ticks"] == pytest.approx(ssot["slippage_ticks"])
    loaded = load_reconciled_rows(tmp_path / "live_calibrator.jsonl")
    assert len(loaded) == 1
    assert loaded[0]["commission"] == pytest.approx(0.94)
    assert loaded[0]["source"] == "broker"


@pytest.mark.unit
def test_jsonl_without_translator_does_not_observe(tmp_path: Path) -> None:
    translator, observe, _index, _bus = make_translator(tmp_path)
    path = tmp_path / "live_calibrator.jsonl"
    path.write_text(
        json.dumps(
            {
                "event": "reconciled",
                "ts": "2026-10-29T12:00:00+00:00",
                "symbol": "MES",
                "quantity": 1,
                "commission": 0.94,
                "source": "broker",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    loaded = load_reconciled_rows(path)
    assert len(loaded) == 1
    assert observe.calls == []
    assert translator.observed_metrics() == ()
