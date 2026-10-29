"""TelegramAlertSink journals research/alarm rejects without a network send."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.research_bridge.alerts import TelegramAlertSink, telegram_credentials_present


@pytest.mark.unit
@pytest.mark.safety_gate
def test_telegram_sink_journals_no_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert telegram_credentials_present() is False
    journal = tmp_path / "tg.jsonl"
    sink = TelegramAlertSink(kind="ops", path=journal)
    sink.alert(code="research_sim_gated", message="gated", details={"hypothesis_id": "hyp-a"})
    text = journal.read_text(encoding="utf-8")
    assert "research_sim_gated" in text
    assert "no_credentials" in text
    assert "hyp-a" in text


@pytest.mark.unit
def test_telegram_sink_evolution_kind(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    journal = tmp_path / "tg.jsonl"
    sink = TelegramAlertSink(kind="evolution", path=journal, source="alarm_executor")
    sink.alert(code="alarm_executor.gated", message="gated", details={"strategy_id": "hyp-b"})
    text = journal.read_text(encoding="utf-8")
    assert '"kind": "evolution"' in text or "evolution" in text
