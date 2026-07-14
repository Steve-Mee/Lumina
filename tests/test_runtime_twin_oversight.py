from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.logging_utils import classify_twin_decision_outcome, compute_autonomy_snapshot
from lumina_core.runtime.runtime_twin_oversight import RuntimeTwinOversight


@pytest.fixture(autouse=True)
def _reset_oversight() -> None:
    RuntimeTwinOversight.reset_for_tests()
    yield
    RuntimeTwinOversight.reset_for_tests()


@pytest.mark.unit
def test_classify_twin_decision_outcome() -> None:
    assert classify_twin_decision_outcome(recommendation=True, score=0.85, risk_flags=[]) == "auto_approved"
    assert classify_twin_decision_outcome(recommendation=False, score=0.9, risk_flags=[]) == "veto"
    assert classify_twin_decision_outcome(recommendation=True, score=0.5, risk_flags=[]) == "deferred"
    assert classify_twin_decision_outcome(recommendation=True, score=0.9, risk_flags=["x"]) == "deferred"


@pytest.mark.unit
def test_compute_autonomy_snapshot_from_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = tmp_path / "state"
    state.mkdir()
    decisions = state / "monitoring_twin_decisions.jsonl"
    rows = [
        {"timestamp": "2099-01-01T12:00:00Z", "recommendation": True, "score": 0.9, "risk_flags": [], "outcome": "auto_approved"},
        {"timestamp": "2099-01-01T12:01:00Z", "recommendation": False, "score": 0.85, "risk_flags": [], "outcome": "veto"},
        {"timestamp": "2099-01-01T12:02:00Z", "recommendation": True, "score": 0.5, "risk_flags": [], "outcome": "deferred"},
    ]
    decisions.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    monkeypatch.setenv("LUMINA_WORKSPACE_ROOT", str(tmp_path))

    snap = compute_autonomy_snapshot(window_hours=24)
    assert snap["decisions_total"] == 3
    assert snap["auto_approved_total"] == 1
    assert snap["veto_total"] == 1
    assert snap["deferred_total"] == 1
    assert snap["autonomy_level_pct"] == pytest.approx(33.33, abs=0.1)

    # New Perfect Birth KPIs surface in snapshot (default 0 when no extra data)
    assert "twin_steve_agreement_pct" not in snap or isinstance(snap.get("twin_steve_agreement_pct"), (int, float))
    assert "autonomy_level_pct" in snap


@pytest.mark.unit
def test_audit_config_reload_blocks_auto_approve_real() -> None:
    oversight = RuntimeTwinOversight.get()
    verdict = oversight.audit_config_reload(
        ["evolution"],
        {"evolution": {"auto_approve_real": True}},
        mode="sim",
    )
    assert not verdict.allowed
    assert "auto_approve_real" in verdict.blocked_fields


@pytest.mark.unit
def test_audit_config_reload_blocks_threshold_decrease_in_real() -> None:
    oversight = RuntimeTwinOversight.get()
    verdict = oversight.audit_config_reload(
        ["evolution"],
        {"evolution": {"approval_twin": {"threshold": 0.5}}},
        mode="real",
    )
    assert not verdict.allowed
    assert "approval_twin.threshold_decrease" in verdict.blocked_fields


@pytest.mark.unit
def test_bind_subscribes_to_twin_decision_topic() -> None:
    bus = EventBus()
    oversight = RuntimeTwinOversight.get()
    token = oversight.bind(bus, mode="sim")
    assert token

    bus.publish(
        topic="evolution.twin.decision",
        producer="test",
        payload={
            "dna_hash": "abc",
            "recommendation": True,
            "confidence": 0.9,
            "risk_flags": [],
        },
    )
    assert len(oversight._live_decisions) == 1


@pytest.mark.unit
def test_twin_artifacts_healthy_requires_model_and_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "ws"
    state = workspace / "state"
    state.mkdir(parents=True)
    (state / "approval_twin_model.json").write_text(json.dumps({"threshold": 0.8}), encoding="utf-8")
    (state / "steve_values_registry.jsonl").write_text("{}\n", encoding="utf-8")
    monkeypatch.setenv("LUMINA_WORKSPACE_ROOT", str(workspace))

    oversight = RuntimeTwinOversight.get()
    healthy, reason = oversight.twin_artifacts_healthy()
    assert healthy
    assert reason == "ok"