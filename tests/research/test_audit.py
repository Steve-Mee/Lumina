"""Append-only JSONL: trials, gate decisions, rejects. Writing cannot be skipped."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from lumina_research.validation import audit as audit_mod
from lumina_research.validation.audit import AuditLog
from lumina_research.validation.gate import passes_validation_gate
from lumina_research.validation.trial_registry import TrialRegistry
from lumina_research.validation.types import (
    DSRSnapshot,
    GateReport,
    OOSDistribution,
    PBOSnapshot,
    RegimeSnapshot,
    ValidationResults,
    WFESnapshot,
)


def _empty_results(path: Path) -> ValidationResults:
    return ValidationResults(
        agent_id="agent-x",
        audit_path=path,
        oos_distribution=OOSDistribution.missing(),
        dsr=DSRSnapshot.missing(),
        pbo=PBOSnapshot.missing(),
        wfe=WFESnapshot.missing(),
        cost_provenance=None,
        median_oos_after_costs=float("nan"),
        n_oos_windows=0,
        regimes=RegimeSnapshot.missing(),
        n_trials_registry=0,
    )


@pytest.mark.unit
def test_gate_always_writes_gate_and_reject(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    passed, report = passes_validation_gate(_empty_results(path))
    assert passed is False
    assert isinstance(report, GateReport)
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    events = [json.loads(line)["event"] for line in lines]
    assert "gate" in events
    assert "reject" in events
    for line in lines:
        payload = json.loads(line)
        assert "timestamp" in payload
        assert payload["agent_id"] == "agent-x"
        metrics = payload["metrics"]
        assert "oos_distribution" in metrics
        assert "dsr" in metrics
        assert "pbo" in metrics
        assert "wfe" in metrics
        assert "reject_reasons" in metrics


@pytest.mark.unit
def test_trial_record_always_writes(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    registry = TrialRegistry(path)
    n = registry.record(config_id="c1", agent_id="agent-y", metrics={"sharpe": 1.2})
    assert n == 1
    payload = json.loads(path.read_text(encoding="utf-8").strip())
    assert payload["event"] == "trial"
    assert payload["agent_id"] == "agent-y"
    assert payload["metrics"]["n_trials"] == 1


@pytest.mark.unit
def test_skip_flags_are_rejected(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "a.jsonl")
    with pytest.raises(TypeError):
        log.append(
            audit_mod.AuditRecord(timestamp="t", agent_id="a", event="gate", metrics={}),
            skip_audit=True,
        )
    registry = TrialRegistry(tmp_path / "b.jsonl")
    with pytest.raises(TypeError):
        registry.record(config_id="c", agent_id="a", metrics={}, skip_audit=True)


@pytest.mark.unit
def test_audit_log_cannot_be_subclassed_to_skip_writes() -> None:
    with pytest.raises(TypeError, match="subclassed"):

        class Silent(AuditLog):  # type: ignore[misc]
            def append(self, record: object, **kwargs: object) -> None:
                return None


@pytest.mark.unit
def test_gate_source_writes_in_finally() -> None:
    source = inspect.getsource(passes_validation_gate)
    assert "finally:" in source
    assert "_audit_decision" in source
    assert "write_event" in inspect.getsource(audit_mod)
