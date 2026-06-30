"""Attention notifier tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lumina_core.notifications.attention_events import (
    AttentionCategory,
    AttentionEvent,
    AttentionSeverity,
    birth_stage_stalled_event,
)
from lumina_core.notifications.attention_notifier import AttentionNotifier


@pytest.mark.unit
def test_attention_dedupe_blocks_repeat(tmp_path: Path) -> None:
    telegram = MagicMock()
    telegram.send_attention_alert.return_value = True
    notifier = AttentionNotifier(workspace_root=tmp_path, telegram=telegram, scheduler=MagicMock())
    notifier._enabled = True
    notifier._dedupe_sec = 3600
    event = AttentionEvent(
        category=AttentionCategory.REAL,
        severity=AttentionSeverity.CRITICAL,
        reason_code="test",
        title="Test",
        summary="Test summary",
        dedupe_key="test:dedupe",
    )
    assert notifier.notify(event) is True
    assert telegram.send_attention_alert.call_count == 1
    assert notifier.notify(event) is False
    assert telegram.send_attention_alert.call_count == 1


@pytest.mark.unit
def test_attention_missing_credentials_fail_closed(tmp_path: Path) -> None:
    telegram = MagicMock()
    telegram.send_attention_alert.return_value = False
    notifier = AttentionNotifier(workspace_root=tmp_path, telegram=telegram, scheduler=MagicMock())
    notifier._enabled = True
    event = AttentionEvent(
        category=AttentionCategory.REAL,
        severity=AttentionSeverity.CRITICAL,
        reason_code="test_fail",
        title="Fail",
        summary="No creds",
        dedupe_key="test:fail",
    )
    assert notifier.notify(event) is False


@pytest.mark.unit
def test_birth_stage_stalled_event_includes_actions() -> None:
    event = birth_stage_stalled_event(
        curriculum_stage="stage1_trend",
        stall_reason="plateau_evolution_exhausted",
        blocker_detail="winrate 33%",
        winrate=0.335,
        retryable=False,
    )
    body = event.telegram_body()
    assert "genesis settings" in body.lower()
    assert "forensics" in body.lower()
