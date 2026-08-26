"""Escalation create/resolve + dual-channel consistency."""

from __future__ import annotations

from pathlib import Path

from lumina_core.evolution.approval_twin_agent import ApprovalTwinAgent
from lumina_core.evolution.steve_values_registry import SteveValuesRegistry
from lumina_core.evolution.twin_escalation import detect_doubt
from lumina_core.evolution.twin_training_service import TwinTrainingService


def _svc(tmp_path: Path) -> TwinTrainingService:
    registry = SteveValuesRegistry(
        sqlite_path=tmp_path / "steve.sqlite3",
        jsonl_path=tmp_path / "steve.jsonl",
    )
    model = tmp_path / "model.json"
    twin = ApprovalTwinAgent(registry=registry, model_path=model)
    return TwinTrainingService(
        registry=registry,
        twin=twin,
        model_path=model,
        decisions_path=tmp_path / "dec.jsonl",
        training_path=tmp_path / "train.jsonl",
        pending_path=tmp_path / "pending.json",
        base_session_path=tmp_path / "base_session.json",
        birth_readiness_path=tmp_path / "readiness.json",
        escalation_log_path=tmp_path / "esc.jsonl",
    )


def test_detect_doubt_low_conf() -> None:
    reasons = detect_doubt(confidence=0.5, risk_flags=[], dna_hash="abc")
    assert "low_conf" in reasons
    assert detect_doubt(confidence=0.95, risk_flags=[]) == []


def test_create_and_resolve_escalation(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    created = svc.create_escalation(
        dna_hash="dna_esc_1",
        confidence=0.62,
        risk_flags=["correlated_instruments"],
        twin_recommendation=True,
        notify_telegram=False,
    )
    assert created["created"] is True
    eid = created["escalation_id"]
    pending = svc.list_pending_escalations()
    assert any(p.get("escalation_id") == eid or p.get("pending_id") == eid for p in pending)

    r1 = svc.resolve_escalation(eid, choice_id="B", resolved_by="deck", train_now=True)
    assert r1["resolved"] is True
    assert r1["already_resolved"] is False
    assert r1["decision_unblocked"] is True

    # Dual-channel race: second resolve is idempotent
    r2 = svc.resolve_escalation(eid, choice_id="A", resolved_by="telegram", train_now=True)
    assert r2["resolved"] is True
    assert r2["already_resolved"] is True
    assert r2["resolved_by"] == "deck"

    pending2 = svc.list_pending_escalations()
    assert not any(p.get("escalation_id") == eid or p.get("pending_id") == eid for p in pending2)
    labels = svc.list_labels(limit=5)
    assert len(labels) >= 1


def test_metrics_include_escalation(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    svc.create_escalation(
        dna_hash="x", confidence=0.4, notify_telegram=False
    )
    m = svc.metrics()
    assert "escalation_rate" in m
    assert m.get("base_trained") is False
    assert "birth_ready" in m


def test_escalation_dedup_same_dna(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    first = svc.create_escalation(
        dna_hash="dna_same",
        confidence=0.4,
        notify_telegram=False,
    )
    second = svc.create_escalation(
        dna_hash="dna_same",
        confidence=0.41,
        notify_telegram=False,
    )
    assert first["created"] is True
    assert second.get("deduped") is True
    assert second["escalation_id"] == first["escalation_id"]
    pending = svc.list_pending_escalations()
    assert len(pending) == 1
