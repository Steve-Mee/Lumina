"""Base training session + birth readiness flag."""

from __future__ import annotations

from pathlib import Path

from lumina_core.evolution.approval_twin_agent import ApprovalTwinAgent
from lumina_core.evolution.steve_values_registry import SteveValuesRegistry
from lumina_core.evolution.twin_base_curriculum import build_base_curriculum
from lumina_core.evolution.twin_base_training import is_twin_birth_ready
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


def test_base_training_full_flow(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    assert is_twin_birth_ready(tmp_path / "readiness.json") is False
    start = svc.start_base_training()
    assert start["started"] is True
    # UI relies on active=True (same shape as base_training_status)
    assert start.get("active") is True
    assert start.get("status") == "in_progress"
    assert start["telegram_disabled"] is True
    assert start["question"] is not None

    qs = build_base_curriculum()
    for q in qs:
        status = svc.next_base_question()
        assert status["question"] is not None
        qid = status["question"]["question_id"]
        assert qid == q.question_id
        choice = status["question"]["choices"][0]["id"]
        out = svc.submit_base_answer(question_id=qid, choice_id=choice, train_now=True)
        assert out["recorded"] is True

    done = svc.complete_base_training()
    assert done["completed"] is True
    assert done["birth_ready"] is True
    assert is_twin_birth_ready(tmp_path / "readiness.json") is True
    ready = svc.readiness()
    assert ready["birth_ready"] is True
    assert ready["base_training_completion_pct"] >= 100.0 or ready["base_trained"] is True
    labels = svc.list_labels(limit=50)
    assert len(labels) >= len(qs)


def test_incomplete_complete_raises(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    svc.start_base_training()
    q = svc.next_base_question()["question"]
    svc.submit_base_answer(question_id=q["question_id"], choice_id="A")
    try:
        svc.complete_base_training()
        raise AssertionError("expected incomplete error")
    except ValueError as exc:
        assert "incomplete" in str(exc)


def test_stale_curriculum_version_not_birth_ready(tmp_path: Path) -> None:
    """Older curriculum versions are not valid for current base_v4 REAL-conscience seed."""
    from lumina_core.evolution.twin_base_training import write_birth_readiness
    from lumina_core.evolution.twin_curriculum_types import CURRICULUM_VERSION

    path = tmp_path / "readiness.json"
    write_birth_readiness(
        path,
        base_trained=True,
        question_count=20,
        curriculum_version="base_v1",
    )
    assert is_twin_birth_ready(path) is False
    write_birth_readiness(
        path,
        base_trained=True,
        question_count=20,
        curriculum_version="base_v2",
    )
    assert is_twin_birth_ready(path) is False
    write_birth_readiness(
        path,
        base_trained=True,
        question_count=20,
        curriculum_version="base_v3",
    )
    assert is_twin_birth_ready(path) is False
    write_birth_readiness(
        path,
        base_trained=True,
        question_count=20,
        curriculum_version=CURRICULUM_VERSION,
    )
    assert is_twin_birth_ready(path) is True
