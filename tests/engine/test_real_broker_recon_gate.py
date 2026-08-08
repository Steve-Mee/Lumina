"""T4: REAL broker recon config fail-closed gate."""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from lumina_core.engine.trade_reconciler.real_recon_gate import (
    evaluate_real_broker_recon_gate,
    recon_required_for_mode,
)
from lumina_core.engine.trade_reconciler.reconciler import TradeReconciler


@pytest.mark.unit
def test_recon_required_for_capital_risk_modes() -> None:
    assert recon_required_for_mode("real") is True
    assert recon_required_for_mode("sim_real_guard") is True
    assert recon_required_for_mode("paper") is False
    assert recon_required_for_mode("sim") is False


@pytest.mark.unit
def test_real_without_reconcile_fails_gate() -> None:
    gate = evaluate_real_broker_recon_gate(
        trade_mode="real",
        reconcile_fills=False,
        reconciliation_method="websocket",
        reconciliation_timeout_seconds=15.0,
    )
    assert gate["ok"] is False
    assert "reconcile_fills_disabled_in_capital_risk_mode" in gate["failures"]


@pytest.mark.unit
def test_real_with_recon_passes_gate() -> None:
    gate = evaluate_real_broker_recon_gate(
        trade_mode="real",
        reconcile_fills=True,
        reconciliation_method="websocket",
        reconciliation_timeout_seconds=15.0,
    )
    assert gate["ok"] is True
    assert gate["failures"] == []


@pytest.mark.unit
def test_timeout_too_low_fails() -> None:
    gate = evaluate_real_broker_recon_gate(
        trade_mode="real",
        reconcile_fills=True,
        reconciliation_method="websocket",
        reconciliation_timeout_seconds=1.0,
    )
    assert gate["ok"] is False
    assert any("timeout" in f for f in gate["failures"])


@pytest.mark.unit
def test_start_fail_closed_when_real_recon_disabled(tmp_path: Path) -> None:
    """Capital-risk mode + reconcile_fills=false → fail_closed status (not silent disable)."""
    status_holder: dict[str, Any] = {}

    class _Engine:
        def __init__(self) -> None:
            self.config = SimpleNamespace(
                trade_mode="real",
                reconcile_fills=False,
                reconciliation_method="websocket",
                reconciliation_timeout_seconds=15.0,
                trade_reconciler_status_file=tmp_path / "status.json",
                trade_reconciler_audit_log=tmp_path / "audit.jsonl",
            )
            self.app = SimpleNamespace(logger=logging.getLogger("recon-gate-test"))
            self.pending_trade_reconciliations: list = []
            self.trade_reconciler_status = status_holder

    engine = _Engine()
    rec = TradeReconciler(engine=engine)  # type: ignore[arg-type]
    rec.start()
    status = getattr(engine, "trade_reconciler_status", {}) or {}
    # _update_status may write to engine attribute via mixin
    if not status:
        status = status_holder
    # Prefer reading from reconciler path if mixin sets on engine
    assert (
        status.get("status") == "fail_closed_recon_required"
        or getattr(engine, "trade_reconciler_status", {}).get("status")
        == "fail_closed_recon_required"
    )
