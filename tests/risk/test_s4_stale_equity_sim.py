"""Stale equity blocks new orders in mode sim (ADR-0064 follow-up Accepted)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from lumina_core.order_gatekeeper import enforce_pre_trade_gate
from lumina_core.order_gatekeeper.engine_helpers import MODES_REQUIRING_EQUITY_SNAPSHOT
from lumina_core.research_bridge.alerts import RecordingAlertSink
from lumina_core.risk.equity_snapshot import EquitySnapshot
from tests.test_order_gatekeeper_contracts import _RiskController, _make_engine


def _stale_snapshot() -> EquitySnapshot:
    return EquitySnapshot(
        equity_usd=50_000.0,
        available_margin_usd=40_000.0,
        used_margin_usd=10_000.0,
        as_of_utc=datetime(2020, 1, 1, tzinfo=timezone.utc),
        source="test",
        ok=True,
        reason_code="ok_live",
        ttl_seconds=30.0,
    )


@pytest.mark.unit
@pytest.mark.safety_gate
def test_sim_in_equity_snapshot_modes() -> None:
    assert "sim" in MODES_REQUIRING_EQUITY_SNAPSHOT


@pytest.mark.unit
@pytest.mark.safety_gate
def test_stale_equity_blocks_sim_and_alerts(monkeypatch: pytest.MonkeyPatch) -> None:
    sink = RecordingAlertSink()
    engine = _make_engine(
        trade_mode="sim",
        risk_controller=_RiskController(),
        equity_snapshot_provider=SimpleNamespace(get_snapshot=_stale_snapshot),
        alert_sink=sink,
    )
    monkeypatch.setattr("lumina_core.order_gatekeeper.is_stale_contract_symbol", lambda *_a, **_k: False)
    monkeypatch.setenv("LUMINA_ALLOW_STALE_CONTRACTS", "false")
    allowed, reason = enforce_pre_trade_gate(
        engine,
        symbol="MES JUN26",
        regime="NEUTRAL",
        proposed_risk=50.0,
        order_side="BUY",
    )
    assert allowed is False
    assert "equity snapshot" in reason.lower() or "stale" in reason.lower()
    assert any(item["code"] == "equity_snapshot_stale" for item in sink.records)
