from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from lumina_core.audit.audit_log_service import AuditLogService
from lumina_core.engine.trade_reconciler import TradeReconciler


def test_reconciler_mirrors_events_to_trade_decision_audit(tmp_path: Path) -> None:
    fill_audit = tmp_path / "trade_fill_audit.jsonl"
    status_path = tmp_path / "trade_reconciler_status.json"
    decision_audit = tmp_path / "trade_decision_audit.jsonl"

    engine = SimpleNamespace(
        config=SimpleNamespace(
            trade_mode="sim_real_guard",
            trade_reconciler_audit_log=str(fill_audit),
            trade_reconciler_status_file=str(status_path),
            reconciliation_method="websocket",
            instrument="MES JUN26",
        ),
        pending_trade_reconciliations=[],
        trade_reconciler_status={},
        audit_log_service=AuditLogService(path=decision_audit, enabled=True, fail_closed_real=True),
        app=SimpleNamespace(logger=SimpleNamespace(info=lambda *_a, **_k: None, error=lambda *_a, **_k: None)),
    )

    reconciler = TradeReconciler(engine=cast(Any, engine))
    reconciler._append_audit_event(
        {
            "event": "reconciled",
            "symbol": "MES JUN26",
            "status": "reconciled_fill",
            "pnl": 25.0,
        }
    )

    fill_lines = [json.loads(line) for line in fill_audit.read_text(encoding="utf-8").splitlines() if line.strip()]
    decision_lines = [
        json.loads(line) for line in decision_audit.read_text(encoding="utf-8").splitlines() if line.strip()
    ]

    assert len(fill_lines) == 1
    assert fill_lines[0]["event"] == "reconciled"
    assert len(decision_lines) == 1
    assert decision_lines[0]["stage"] == "reconciliation"
    assert decision_lines[0]["final_decision"] == "reconciled"
