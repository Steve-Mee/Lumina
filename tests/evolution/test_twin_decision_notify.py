"""Twin decision Telegram feed + operator feedback → RLHF."""

from __future__ import annotations

import json
from pathlib import Path

from lumina_core.evolution.twin_decision_notify import (
    TwinDecisionNotifyStore,
    apply_decision_feedback,
    build_lumina_question,
    format_decision_telegram_message,
    format_twin_answer,
    notify_twin_decision,
    parse_decision_feedback_text,
)


def test_message_contains_operator_clarity() -> None:
    payload = {
        "decision_id": "abc123xyz",
        "dna_hash": "deadbeefcafebabe0123456789",
        "call": "evaluate_dna_promotion",
        "recommendation": True,
        "confidence": 0.90,
        "explanation": "Twin score=90%, threshold=60%, backend=local, fitness=0.5",
        "executable": True,
        "authority": "execute_judgment",
    }
    msg = format_decision_telegram_message(payload)
    low = msg.lower()
    assert "situatie" in low
    assert "twin" in low
    assert "termen" in low
    assert "ok abc123" in low or "ok abc123xyz" in low
    assert "a abc123" in low  # base_v4 approve correction
    assert "evaluate_dna" not in low
    assert "backend=" not in low
    # Post-hoc — not pre-approval gate panic
    assert "natraining" in low or "keek mee" in low or "nátijden" in low or "natijden" in low
    assert "wacht op jouw goedkeuring" not in low


def test_format_answer_and_question() -> None:
    assert "APPROVE" in format_twin_answer(recommendation=True, confidence=0.87)
    assert "VETO" in format_twin_answer(recommendation=False, confidence=0.2)
    q = build_lumina_question(
        dna_hash="hash1234567890",
        call="evaluate_dna_promotion",
        explanation="Twin score=50%, threshold=60%, backend=local",
        risk_flags=["overnight"],
    )
    assert "evaluate_dna" not in q.lower()
    assert "handelsregels" in q.lower() or "dna" in q.lower()
    assert "backend" not in q.lower()


def test_parse_feedback_commands() -> None:
    assert parse_decision_feedback_text("OK dec1") == {
        "action": "OK",
        "decision_id": "dec1",
        "notes": "",
    }
    p = parse_decision_feedback_text("FIX V dec99 too hot")
    assert p is not None
    assert p["action"] == "FIX_V"
    assert p["decision_id"] == "dec99"
    assert "too hot" in p["notes"]
    # base_v4 short aliases
    assert parse_decision_feedback_text("A dec1")["action"] == "FIX_A"
    assert parse_decision_feedback_text("B dec1")["action"] == "FIX_V"
    assert parse_decision_feedback_text("C dec1 note")["notes"] == "note"


def test_notify_and_feedback_trains(tmp_path: Path, monkeypatch) -> None:
    store = TwinDecisionNotifyStore(path=tmp_path / "pending.json")
    monkeypatch.setattr(
        "lumina_core.evolution.twin_decision_notify.get_decision_notify_store",
        lambda: store,
    )
    # No real telegram
    monkeypatch.setattr(
        "lumina_core.evolution.twin_decision_notify.should_send_now",
        lambda **k: True,
    )

    class _FakeTg:
        def send_message(self, _m: str) -> bool:
            return False

        _lock = __import__("threading").RLock()
        _pending_twin_questions: dict = {}

    monkeypatch.setattr(
        "lumina_core.notifications.telegram_notifier.TelegramNotifier",
        _FakeTg,
    )

    out = notify_twin_decision(
        dna_hash="dna_fb_1",
        recommendation=True,
        confidence=0.91,
        explanation="high conf clean",
        call="evaluate_dna_promotion",
        mode="shadow",
        notify_telegram=True,
    )
    assert out.get("decision_id")
    did = str(out["decision_id"])

    # Point training service at tmp paths
    from lumina_core.evolution.approval_twin_agent import ApprovalTwinAgent
    from lumina_core.evolution.steve_values_registry import SteveValuesRegistry
    from lumina_core.evolution.twin_training_service import TwinTrainingService

    registry = SteveValuesRegistry(
        sqlite_path=tmp_path / "s.sqlite3",
        jsonl_path=tmp_path / "s.jsonl",
    )
    model = tmp_path / "m.json"
    twin = ApprovalTwinAgent(registry=registry, model_path=model)
    svc = TwinTrainingService(
        registry=registry,
        twin=twin,
        model_path=model,
        decisions_path=tmp_path / "d.jsonl",
        training_path=tmp_path / "t.jsonl",
        pending_path=tmp_path / "p.json",
        base_session_path=tmp_path / "b.json",
        birth_readiness_path=tmp_path / "r.json",
        escalation_log_path=tmp_path / "e.jsonl",
    )
    monkeypatch.setattr(
        "lumina_core.evolution.twin_training_service.TwinTrainingService",
        lambda **k: svc,
    )

    fb = apply_decision_feedback(did, action="V", notes="should veto", resolved_by="deck")
    assert fb.get("ok") is True
    assert fb.get("trained") is True
    labels = svc.list_labels(limit=5)
    assert len(labels) >= 1
    assert "VETO" in labels[0]["steve_antwoord"].upper() or "veto" in labels[0]["steve_antwoord"].lower()


def test_notify_telegram_false_journals_without_send(tmp_path: Path, monkeypatch) -> None:
    store = TwinDecisionNotifyStore(path=tmp_path / "pending.json")
    monkeypatch.setattr(
        "lumina_core.evolution.twin_decision_notify.get_decision_notify_store",
        lambda: store,
    )
    monkeypatch.setattr(
        "lumina_core.evolution.twin_decision_notify._cfg",
        lambda: {"enabled": True, "telegram": False},
    )
    sent_calls: list[str] = []

    class _BoomTg:
        def send_message(self, *_a, **_k) -> bool:
            sent_calls.append("sent")
            return True

    monkeypatch.setattr(
        "lumina_core.notifications.telegram_notifier.TelegramNotifier",
        _BoomTg,
    )
    journal_path = tmp_path / "tg.jsonl"
    monkeypatch.setattr(
        "lumina_core.notifications.telegram_journal.resolve_journal_path",
        lambda workspace_root=None: journal_path,
    )
    out = notify_twin_decision(
        dna_hash="dna_no_tg",
        recommendation=True,
        confidence=0.4,
        risk_flags=["low_conf"],
        notify_telegram=True,
    )
    assert out.get("decision_id")
    assert out.get("sent") is False
    assert sent_calls == []
    rows = journal_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1
    rec = json.loads(rows[0])
    assert rec["kind"] == "twin_decision"
    assert rec["delivered"] is False
    assert rec["drop_reason"] == "policy_shadow_diary"
    assert rec["expects_reply"] is True
