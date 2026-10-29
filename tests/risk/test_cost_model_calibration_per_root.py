"""ES and MES rows do not share a rolling mean."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.risk.cost_model_calibrator import run_daily_calibration


@pytest.mark.unit
@pytest.mark.safety_gate
def test_es_and_mes_do_not_share_rolling_mean(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    rows = [
        {
            "event": "reconciled",
            "ts": "2026-05-01T10:00:00+00:00",
            "symbol": "MES JUN26",
            "quantity": 1,
            "slippage_usd": 1.25,
            "commission": 0.94,
            "source": "broker",
        },
        {
            "event": "reconciled",
            "ts": "2026-05-01T11:00:00+00:00",
            "symbol": "ES JUN26",
            "quantity": 1,
            "slippage_usd": 12.50,
            "commission": 2.87,
            "source": "broker",
        },
    ]
    audit.write_text("\n".join(json.dumps(item) for item in rows), encoding="utf-8")
    mes_state = tmp_path / "mes.json"
    es_state = tmp_path / "es.json"
    mes = run_daily_calibration(audit_path=audit, state_path=mes_state, instrument="MES")
    es = run_daily_calibration(audit_path=audit, state_path=es_state, instrument="ES")
    assert mes.sample_count == 1
    assert es.sample_count == 1
    mes_payload = json.loads(mes_state.read_text(encoding="utf-8"))
    es_payload = json.loads(es_state.read_text(encoding="utf-8"))
    assert mes_payload["by_root"]["MES"]["sample_count"] == 1
    assert mes_payload["by_root"]["ES"]["sample_count"] == 1
    assert mes_payload["by_root"]["MES"]["real_fill_cost_usd_avg"] != mes_payload["by_root"]["ES"][
        "real_fill_cost_usd_avg"
    ]
    assert mes_payload["rolling"]["sample_count"] == 1
    assert es_payload["rolling"]["sample_count"] == 1
    assert mes.mean_bias_usd != es.mean_bias_usd
