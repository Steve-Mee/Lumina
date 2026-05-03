from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.fault import FaultDomain, FaultPolicy, LuminaFault


@pytest.mark.unit
def test_fault_policy_sim_logs_structured_without_raising(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    try:
        raise ValueError("simulated-sim-fault")
    except ValueError as exc:
        FaultPolicy.handle(
            domain=FaultDomain.AUDIT_LOG_SERVICE,
            operation="sim_observability_check",
            exc=exc,
            is_real_mode=False,
            message="SIM fault policy should remain observable",
            context={"stream": "trade_decision"},
        )

    structured = tmp_path / "logs" / "structured_errors.jsonl"
    assert structured.exists()
    lines = [json.loads(line) for line in structured.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= 1
    latest = lines[-1]
    assert latest["context"]["domain"] == FaultDomain.AUDIT_LOG_SERVICE.value
    assert latest["context"]["operation"] == "sim_observability_check"
    assert latest["context"]["fault_id"]


@pytest.mark.unit
def test_fault_policy_real_raises_typed_fault_and_logs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(LuminaFault) as exc_info:
        try:
            raise RuntimeError("simulated-real-fault")
        except RuntimeError as exc:
            FaultPolicy.handle(
                domain=FaultDomain.AGENT_DECISION_LOG,
                operation="real_fail_closed_check",
                exc=exc,
                is_real_mode=True,
                message="REAL mode must fail closed",
            )

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    structured = tmp_path / "logs" / "structured_errors.jsonl"
    assert structured.exists()
    payload = json.loads(structured.read_text(encoding="utf-8").splitlines()[-1])
    assert payload["context"]["is_real_mode"] is True
    assert payload["context"]["fault_id"] == exc_info.value.fault_id
