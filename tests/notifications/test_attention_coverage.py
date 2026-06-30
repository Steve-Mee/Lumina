"""Attention notification wiring coverage tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lumina_core.notifications.attention_events import (
    birth_error_event,
    birth_interrupted_event,
    constitution_violation_event,
    evolution_proof_failed_attention_event,
    real_safe_mode_event,
    real_trading_blocked_event,
)
from lumina_core.notifications.attention_notifier import AttentionNotifier
from lumina_core.notifications.operator_notifier import notify_problem


@pytest.mark.unit
@pytest.mark.parametrize(
    "event_factory",
    [
        lambda: birth_interrupted_event(detail="stopped"),
        lambda: birth_error_event(detail="engine crash"),
        lambda: evolution_proof_failed_attention_event(reasons=["oos_low"]),
        lambda: real_safe_mode_event(detail="ws down"),
        lambda: real_trading_blocked_event(blockers=["Evolution Proof passed"], source="test"),
        lambda: constitution_violation_event(detail="principle_x"),
    ],
)
def test_attention_notifier_sends_telegram(event_factory, tmp_path: Path) -> None:
    telegram = MagicMock()
    telegram.send_attention_alert.return_value = True
    scheduler = MagicMock()

    def _schedule(callback, **_: object) -> dict[str, bool]:
        callback()
        return {"sent_now": True, "accepted": True}

    scheduler.schedule_notification.side_effect = _schedule
    notifier = AttentionNotifier(workspace_root=tmp_path, telegram=telegram, scheduler=scheduler)
    notifier._enabled = True
    notifier._dedupe_sec = 0

    assert notifier.notify(event_factory()) is True
    telegram.send_attention_alert.assert_called_once()


@pytest.mark.unit
def test_notify_problem_delegates_to_attention(tmp_path: Path) -> None:
    with patch(
        "lumina_core.notifications.operator_notifier.notify_attention",
        return_value=True,
    ) as notify_mock:
        sent = notify_problem(
            real_trading_blocked_event(blockers=["x"], source="test"),
            workspace_root=tmp_path,
        )
    assert sent is True
    notify_mock.assert_called_once()


@pytest.mark.unit
def test_real_trading_blocked_dedupe_key() -> None:
    event = real_trading_blocked_event(blockers=["a", "b"], source="command_deck")
    assert event.dedupe_key == "real:blocked:command_deck"
    assert event.severity.value == "high"
