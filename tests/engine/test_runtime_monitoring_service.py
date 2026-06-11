"""Tests for RuntimeMonitoringService (D2 sub-slice 15)."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from lumina_core.engine.runtime_monitoring_service import RuntimeMonitoringService

_RUNTIME_WORKERS = Path(__file__).resolve().parents[2] / "lumina_core" / "runtime_workers.py"


@pytest.mark.unit
def test_compute_session_kpis_winrate_and_drawdown():
    app = SimpleNamespace(
        np=np,
        pnl_history=[10.0, -5.0, 8.0],
        equity_curve=[100.0, 110.0, 95.0, 105.0],
    )
    kpis = RuntimeMonitoringService(app=app).compute_session_kpis()
    assert kpis["winrate"] == round(2 / 3, 6)
    assert kpis["realized_pnl_session"] == 13.0
    assert kpis["max_drawdown_usd"] > 0
    assert "sharpe_annualized" in kpis


@pytest.mark.unit
def test_publish_snapshot_writes_payload(monkeypatch):
    captured: list[dict] = []

    def fake_write(payload: dict) -> None:
        captured.append(payload)

    monkeypatch.setattr(
        "lumina_core.engine.runtime_monitoring_service.write_runtime_monitoring_snapshot",
        fake_write,
    )
    rc_state = SimpleNamespace(mc_drawdown_worst_pct=2.5)
    risk_controller = SimpleNamespace(consecutive_losses=1, state=rc_state)
    engine = SimpleNamespace(
        risk_controller=risk_controller,
        live_position_qty=2,
        config=SimpleNamespace(trade_mode="paper", drawdown_kill_percent=8.0),
    )
    app = SimpleNamespace(
        np=np,
        engine=engine,
        pnl_history=[1.0],
        equity_curve=[100.0, 101.0],
        account_balance=1000.0,
        account_equity=950.0,
        realized_pnl_today=5.0,
        open_pnl=1.0,
        pending_trade_reconciliations=[],
        trade_log=[],
    )
    RuntimeMonitoringService(app=app).publish_snapshot()
    assert len(captured) == 1
    payload = captured[0]
    assert payload["mode"] == "paper"
    assert payload["live_position_qty"] == 2
    assert payload["session_kpis"]["realized_pnl_session"] == 1.0
    assert payload["drawdown_pct"] == 5.0
    print("MANUAL_SMOKE_SUB15_MONITORING_SUCCESS")


@pytest.mark.unit
def test_runtime_workers_monitoring_is_thin_delegate_only():
    text = _RUNTIME_WORKERS.read_text(encoding="utf-8")
    assert "np.maximum.accumulate" not in text
    assert "write_runtime_monitoring_snapshot" not in text
    kpi_block = re.search(
        r"def _compute_session_kpis.*?^def ",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert kpi_block is not None
    body = kpi_block.group(0)
    assert "RuntimeMonitoringService" in body
    assert "winrate =" not in body
