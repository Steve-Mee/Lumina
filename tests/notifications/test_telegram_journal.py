"""Telegram I/O journal: outbound, inbound, Q+A threads."""

from __future__ import annotations

from pathlib import Path

from lumina_core.notifications.telegram_journal import (
    THREAD_RESOLVED_KIND,
    list_records,
    list_threads,
    record_inbound,
    record_outbound,
    record_reply,
)


def test_journal_out_in_and_thread_resolved(tmp_path: Path) -> None:
    path = tmp_path / "tg.jsonl"
    record_outbound(
        text="Twin is onzeker — kies A of B",
        kind="twin_escalation",
        correlation_id="esc-1",
        expects_reply=True,
        source="test",
        path=path,
    )
    record_inbound(text="B", kind="operator", source="telegram_poll", path=path)
    out = record_reply(
        correlation_id="esc-1",
        reply_text="B",
        resolved_by="telegram",
        kind="twin_escalation",
        source="test",
        question_text="Twin is onzeker — kies A of B",
        path=path,
    )
    assert out["resolved"]["kind"] == THREAD_RESOLVED_KIND
    assert "Q:" in str(out["resolved"]["text"])
    assert "A: B" in str(out["resolved"]["text"])

    rows = list_records(limit=50, path=path)
    assert any(r.get("direction") == "out" for r in rows)
    assert any(r.get("kind") == THREAD_RESOLVED_KIND for r in rows)

    threads = list_threads(limit=50, path=path)
    questions = [t for t in threads if t.get("expects_reply")]
    assert len(questions) == 1
    assert questions[0]["reply"] is not None
    assert questions[0]["reply"]["text"] == "B"
    assert questions[0]["reply"]["resolved_by"] == "telegram"
    assert questions[0]["ts"]
    assert "Twin is onzeker" in str(questions[0]["text"])


def test_deck_reply_attaches_to_telegram_question(tmp_path: Path) -> None:
    path = tmp_path / "tg.jsonl"
    record_outbound(
        text="Situatie: DNA promoten?",
        kind="twin_decision",
        correlation_id="dec-9",
        expects_reply=True,
        source="twin_decision_notify",
        delivered=False,
        drop_reason="policy_shadow_diary",
        path=path,
    )
    record_reply(
        correlation_id="dec-9",
        reply_text="V",
        resolved_by="deck",
        kind="twin_decision",
        source="twin_decision_notify.apply_feedback",
        path=path,
    )
    threads = list_threads(limit=20, path=path)
    q = next(t for t in threads if t.get("correlation_id") == "dec-9")
    assert q["delivered"] is False
    assert q["drop_reason"] == "policy_shadow_diary"
    assert q["reply"] is not None
    assert q["reply"]["text"] == "V"
    assert q["reply"]["resolved_by"] == "deck"
