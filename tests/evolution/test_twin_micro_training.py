"""Micro training session dual-channel close."""

from __future__ import annotations

from pathlib import Path

from lumina_core.evolution.approval_twin_agent import ApprovalTwinAgent
from lumina_core.evolution.steve_values_registry import SteveValuesRegistry
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


def test_micro_session_and_answer(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    session = svc.start_micro_session(count=2, notify_telegram=False, dual_channel=True)
    assert session["count"] >= 1
    item = session["items"][0]
    q = item.get("question") or {}
    scenario = str(q.get("scenario") or "")
    assert "Oefenvraag" in scenario
    assert "Live data:" in scenario
    assert "Termen:" in scenario
    labels = [c.get("label", "") for c in (q.get("choices") or [])]
    assert any("doorzetten" in str(x) for x in labels)
    assert any("\n+ " in str(x) for x in labels)
    pid = item["pending_id"]
    out = svc.submit_micro(pending_id=pid, choice_id="A", resolved_by="deck")
    assert out["recorded"] is True
    again = svc.submit_micro(pending_id=pid, choice_id="B", resolved_by="telegram")
    assert again.get("already_resolved") is True
