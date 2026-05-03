from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from lumina_core.engine.audit_log_service import AuditLogService


def test_audit_log_service_writes_hash_chain(tmp_path: Path) -> None:
    log_path = tmp_path / "trade_decision_audit.jsonl"
    service = AuditLogService(path=log_path, enabled=True, fail_closed_real=True)

    payload_1 = {
        "stage": "risk_gate",
        "final_decision": "allow",
        "reason": "ok",
        "mode": "sim",
        "symbol": "MES",
    }
    payload_2 = {
        "stage": "risk_gate",
        "final_decision": "block",
        "reason": "threshold",
        "mode": "real",
        "symbol": "MES",
    }

    assert service.log_decision(payload_1, is_real_mode=False) is True
    assert service.log_decision(payload_2, is_real_mode=True) is True

    lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 2
    assert lines[0]["prev_hash"] == "GENESIS"
    assert lines[0]["hash"]
    assert lines[1]["prev_hash"] == lines[0]["hash"]
    assert lines[1]["hash"]


def test_audit_log_service_logs_stacktrace_on_validation_error(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = AuditLogService(path=tmp_path / "trade_decision_audit.jsonl", enabled=True, fail_closed_real=True)
    invalid_payload = {"mode": "real"}

    with caplog.at_level(logging.ERROR):
        ok = service.log_decision(invalid_payload, is_real_mode=True)

    assert ok is False
    assert "failed to append decision event" in caplog.text
