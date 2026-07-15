"""Unit tests for TwinTrainingService (local audit + light RLHF)."""

from __future__ import annotations

import json
from pathlib import Path

from lumina_core.evolution.approval_twin_agent import ApprovalTwinAgent
from lumina_core.evolution.steve_values_registry import SteveValuesRegistry
from lumina_core.evolution.twin_training_service import (
    TwinTrainingService,
    decision_to_answer,
    default_confidence,
)


def _svc(tmp_path: Path) -> TwinTrainingService:
    decisions = tmp_path / "monitoring_twin_decisions.jsonl"
    training = tmp_path / "monitoring_twin_training.jsonl"
    model = tmp_path / "approval_twin_model.json"
    registry = SteveValuesRegistry(
        sqlite_path=tmp_path / "steve.sqlite3",
        jsonl_path=tmp_path / "steve.jsonl",
    )
    twin = ApprovalTwinAgent(registry=registry, model_path=model)
    return TwinTrainingService(
        registry=registry,
        twin=twin,
        model_path=model,
        decisions_path=decisions,
        training_path=training,
    )


def test_decision_to_answer_mapping() -> None:
    assert decision_to_answer("approve") == "APPROVE"
    assert decision_to_answer("reject", "too hot") == "VETO: too hot"
    assert decision_to_answer("modify", "cut size") == "MODIFY: cut size"
    assert default_confidence("approve") == 0.85
    assert default_confidence("reject") == 0.25
    assert default_confidence("modify") == 0.45


def test_record_decision_persists_and_trains(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    out = svc.record_decision(
        decision="approve",
        dna_hash="abc123",
        twin_score=0.9,
        twin_recommendation=True,
        explanation="low risk guard",
        risk_flags=[],
        train_now=True,
    )
    assert out["recorded"] is True
    assert out["label"] == "APPROVE"
    assert out["rlhf"] is not None
    assert out["rlhf"]["updated"] is True
    labels = svc.list_labels(limit=10)
    assert len(labels) == 1
    assert labels[0]["context_dna_hash"] == "abc123"
    assert svc.model_path.exists()


def test_modify_label_soft_reject(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    out = svc.record_decision(
        decision="modify",
        dna_hash="mod1",
        notes="approve only with half size",
        train_now=True,
    )
    assert out["label"].startswith("MODIFY")
    assert ApprovalTwinAgent._label_from_answer(out["label"]) == 0.35


def test_list_review_queue_high_stakes_first(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    lines = [
        json.dumps({"dna_hash": "routine_old", "score": 0.92, "recommendation": True, "risk_flags": []}),
        json.dumps({"dna_hash": "high_new", "score": 0.55, "recommendation": False, "risk_flags": []}),
        json.dumps(
            {
                "dna_hash": "risk_flag",
                "score": 0.95,
                "recommendation": True,
                "risk_flags": ["drawdown"],
            }
        ),
    ]
    svc.decisions_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    queue = svc.list_review_queue(limit=5)
    assert all("stakes" in row for row in queue)
    assert queue[0]["stakes"] == "high"
    # High-stakes (risk or low score) before pure routine high-conf
    high_hashes = {r["dna_hash"] for r in queue if r["stakes"] == "high"}
    assert "high_new" in high_hashes
    assert "risk_flag" in high_hashes
    routine = [r for r in queue if r["stakes"] == "routine"]
    assert all(r["dna_hash"] == "routine_old" for r in routine)


def test_list_review_queue_excludes_labeled(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    lines = [
        json.dumps({"dna_hash": "labeled1", "score": 0.4, "recommendation": False}),
        json.dumps({"dna_hash": "open1", "score": 0.5, "recommendation": False}),
    ]
    svc.decisions_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    svc.record_decision(decision="approve", dna_hash="labeled1", train_now=False)
    hidden = svc.list_review_queue(limit=10, include_labeled=False)
    assert all(r["dna_hash"] != "labeled1" for r in hidden)
    assert any(r["dna_hash"] == "open1" for r in hidden)
    shown = svc.list_review_queue(limit=10, include_labeled=True)
    labeled_row = next(r for r in shown if r["dna_hash"] == "labeled1")
    assert labeled_row["already_labeled"] is True


def test_metrics_local_only(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    m = svc.metrics()
    assert m["local_only"] is True
    assert "threshold" in m


def test_record_requires_dna(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    try:
        svc.record_decision(decision="approve", dna_hash="  ")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_start_gym_session_synthetic(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    session = svc.start_gym_session(count=3, prefer_historical=False, rng_seed=42)
    assert session["practice_only"] is True
    assert session["promotes_dna"] is False
    assert session["count"] == 3
    assert len(session["proposals"]) == 3
    assert all(p["source"] == "synthetic" for p in session["proposals"])
    assert session["session_id"]


def test_record_gym_answer_and_complete(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    session = svc.start_gym_session(count=3, prefer_historical=False, rng_seed=7)
    first = session["proposals"][0]
    one = svc.record_gym_answer(
        decision="reject",
        dna_hash=first["dna_hash"],
        summary=first["summary"],
        estimated_confidence=first["estimated_confidence"],
        session_id=session["session_id"],
        train_now=False,
    )
    assert one["recorded"] is True
    assert one["practice_only"] is True
    assert one["label"] == "VETO"

    answers = [
        {
            "decision": "approve",
            "dna_hash": session["proposals"][1]["dna_hash"],
            "summary": session["proposals"][1]["summary"],
            "estimated_confidence": session["proposals"][1]["estimated_confidence"],
        },
        {
            "decision": "modify",
            "dna_hash": session["proposals"][2]["dna_hash"],
            "summary": session["proposals"][2]["summary"],
            "notes": "half size",
        },
    ]
    batch = svc.complete_gym_session(
        answers=answers,
        train_now=True,
        session_id=session["session_id"],
    )
    assert batch["recorded_count"] == 2
    assert batch["rlhf"] is not None
    assert batch["promotes_dna"] is False
    labels = svc.list_labels(limit=20)
    assert len(labels) >= 3
