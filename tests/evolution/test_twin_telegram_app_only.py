"""Base curriculum must never ship over Telegram."""

from __future__ import annotations

from lumina_core.notifications.telegram_notifier import TelegramNotifier


def test_send_twin_mc_refuses_app_only_policy() -> None:
    n = TelegramNotifier(api_token="", chat_id="")
    ok = n.send_twin_mc_question(
        pending_id="test1",
        question={
            "channel_policy": "app_only",
            "scenario": "base Q",
            "choices": [{"id": "A", "label": "x"}],
        },
        resolve_token="tok",
        kind="escalation",
    )
    assert ok is False


def test_send_twin_mc_refuses_base_kind() -> None:
    n = TelegramNotifier(api_token="fake", chat_id="1")
    ok = n.send_twin_mc_question(
        pending_id="test2",
        question={
            "channel_policy": "dual",
            "scenario": "should still refuse because kind=base",
            "choices": [{"id": "A", "label": "x"}],
        },
        resolve_token="tok",
        kind="base",
    )
    assert ok is False
