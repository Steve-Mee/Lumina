"""Append-only JSONL: trials, gate decisions, rejects. Writing cannot be skipped."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from lumina_research.validation import audit as audit_mod
from lumina_research.validation.audit import AuditLog, utc_now_iso
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
            audit_mod.AuditRecord(timestamp=utc_now_iso(), agent_id="a", event="gate", metrics={}),
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


@pytest.mark.unit
def test_concurrent_appends_are_valid_jsonl(tmp_path: Path) -> None:
    import threading

    path = tmp_path / "conc.jsonl"
    log = AuditLog(path)
    errors: list[BaseException] = []

    def writer(agent: str) -> None:
        try:
            for index in range(20):
                log.append(
                    audit_mod.AuditRecord(
                        timestamp=utc_now_iso(),
                        agent_id=agent,
                        event="trial",
                        metrics={"i": index},
                    )
                )
        except BaseException as exc:  # noqa: BLE001 — collect worker failures
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(f"a{n}",)) for n in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 80
    for line in lines:
        payload = json.loads(line)
        assert payload["event"] == "trial"
        assert "timestamp" in payload
        assert payload["agent_id"].startswith("a")


@pytest.mark.unit
def test_forged_timestamp_is_rejected(tmp_path: Path) -> None:
    from lumina_research.validation.audit import write_event

    with pytest.raises(TypeError, match="UTC"):
        write_event(path=tmp_path / "t.jsonl", agent_id="a", event="gate", metrics={}, timestamp="now")


@pytest.mark.unit
def test_trial_count_uses_audit_high_water(tmp_path: Path) -> None:
    path = tmp_path / "hw.jsonl"
    registry = TrialRegistry(path)
    registry.record(config_id="a", agent_id="x", metrics={})
    registry.record(config_id="b", agent_id="x", metrics={})
    object.__setattr__(registry, "_records", ())
    assert registry.n_trials == 2
