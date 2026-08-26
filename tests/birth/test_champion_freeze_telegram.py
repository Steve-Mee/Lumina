"""Champion freeze Telegram bridge — parse, notify pending, echo."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lumina_core.birth.champion_freeze_telegram import (
    CMD_ACCEPT,
    CMD_ACCEPT_NO_START,
    CMD_WIPE,
    apply_freeze_command,
    clear_pending,
    echo_operator_decision,
    format_freeze_telegram_body,
    load_pending,
    notify_champion_freeze_decision,
    parse_freeze_telegram_command,
    try_handle_telegram_freeze_text,
    write_pending,
)
from lumina_core.birth.champion_freeze_ops import build_champion_freeze_decision_card
from lumina_core.notifications.attention_events import birth_champion_freeze_event


@pytest.mark.unit
def test_parse_freeze_commands() -> None:
    assert parse_freeze_telegram_command("ACCEPT") == CMD_ACCEPT
    assert parse_freeze_telegram_command("accept please") == CMD_ACCEPT
    assert parse_freeze_telegram_command("ACCEPT_NO_START") == CMD_ACCEPT_NO_START
    assert parse_freeze_telegram_command("WIPE") == CMD_WIPE
    assert parse_freeze_telegram_command("WIPE_FULL") == "WIPE_FULL"
    assert parse_freeze_telegram_command("wipe_and_retry") == CMD_WIPE
    assert parse_freeze_telegram_command("YES token123") is None
    assert parse_freeze_telegram_command("APPROVE dna") is None


@pytest.mark.unit
def test_format_body_includes_commands() -> None:
    card = build_champion_freeze_decision_card(
        progress={
            "swarm_rejected_no_lift": True,
            "phase": "swarm_reject_hard_stop",
            "stage_blocker_metric": "position_flat",
            "stage_blocker_value": 0.956,
            "pass_reason": "flat high",
        }
    )
    body = format_freeze_telegram_body(card)
    assert "ACCEPT" in body
    assert "WIPE_FULL" in body
    assert "checklist" in body.lower() or "Checklist" in body


@pytest.mark.unit
def test_birth_champion_freeze_event_actions() -> None:
    ev = birth_champion_freeze_event(summary="frozen", stage_trades=100)
    assert ev.severity.value == "critical"
    assert "accept_champion" in ev.recommended_actions
    assert any("Telegram" in a for a in ev.recommended_actions)


@pytest.mark.unit
def test_notify_writes_pending(tmp_path: Path) -> None:
    progress = {
        "swarm_rejected_no_lift": True,
        "phase": "swarm_reject_hard_stop",
        "needs_attention": True,
        "cumulative_trades": 100,
    }
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "lumina_birth_progress.json").write_text(
        json.dumps(progress), encoding="utf-8"
    )
    with patch(
        "lumina_core.notifications.attention_notifier.notify_attention", return_value=True
    ), patch(
        "lumina_core.notifications.telegram_notifier.TelegramNotifier"
    ) as tg_cls:
        tg = MagicMock()
        tg.send_attention_alert.return_value = True
        tg_cls.return_value = tg
        out = notify_champion_freeze_decision(tmp_path, progress=progress, force=True)
    assert out.get("ok") is True
    pending = load_pending(tmp_path)
    assert pending is not None
    assert pending.get("status") == "pending"
    # second call without force skips spam
    out2 = notify_champion_freeze_decision(tmp_path, progress=progress, force=False)
    assert out2.get("skipped") == "already_pending"


@pytest.mark.unit
def test_freeze_does_not_send_twin_mc_telegram(tmp_path: Path) -> None:
    progress = {
        "swarm_rejected_no_lift": True,
        "phase": "swarm_reject_hard_stop",
        "needs_attention": True,
        "cumulative_trades": 100,
    }
    (tmp_path / "state").mkdir()
    captured: dict[str, object] = {}

    class _Svc:
        def create_escalation(self, **kwargs: object) -> dict[str, object]:
            captured.update(kwargs)
            return {"escalation_id": "esc-freeze", "created": True}

    with patch(
        "lumina_core.notifications.attention_notifier.notify_attention", return_value=True
    ), patch(
        "lumina_core.notifications.telegram_notifier.TelegramNotifier"
    ) as tg_cls, patch(
        "lumina_core.evolution.twin_base_training.is_twin_birth_ready", return_value=True
    ), patch(
        "lumina_core.evolution.twin_training_service.TwinTrainingService",
        return_value=_Svc(),
    ):
        tg = MagicMock()
        tg.send_attention_alert.return_value = True
        tg_cls.return_value = tg
        notify_champion_freeze_decision(tmp_path, progress=progress, force=True)
    assert captured.get("notify_telegram") is False
    tg.send_twin_mc_question.assert_not_called()


@pytest.mark.unit
def test_try_handle_status_without_freeze(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "lumina_birth_progress.json").write_text(
        json.dumps({"phase": "curriculum_learning"}), encoding="utf-8"
    )
    with patch(
        "lumina_core.birth.champion_freeze_telegram._send_plain", return_value=True
    ) as send:
        result = try_handle_telegram_freeze_text(tmp_path, "STATUS", apply=True)
    assert result is not None
    assert result.get("action") == "status"
    send.assert_called()


@pytest.mark.unit
def test_try_handle_accept_requires_freeze(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "lumina_birth_progress.json").write_text(
        json.dumps({"phase": "curriculum_learning"}), encoding="utf-8"
    )
    with patch(
        "lumina_core.birth.champion_freeze_telegram._send_plain", return_value=True
    ):
        result = try_handle_telegram_freeze_text(tmp_path, "ACCEPT", apply=True)
    assert result is not None
    assert result.get("ok") is False
    assert result.get("error") == "no_freeze"


@pytest.mark.unit
def test_echo_operator_decision_sends(tmp_path: Path) -> None:
    with patch(
        "lumina_core.birth.champion_freeze_telegram._send_plain", return_value=True
    ) as send:
        ok = echo_operator_decision(
            tmp_path,
            action="ACCEPT",
            source="app",
            detail="champion accepted",
            started=True,
        )
    assert ok is True
    send.assert_called_once()
    text = send.call_args[0][1]
    assert "ACCEPT" in text
    assert "source: app" in text


@pytest.mark.unit
def test_apply_accept_no_start_mocked(tmp_path: Path) -> None:
    write_pending(tmp_path, {"status": "pending"})
    mock_svc = MagicMock()
    mock_svc.accept_champion_birth.return_value = {
        "status": "champion_accepted",
        "started": False,
    }
    with patch(
        "lumina_launcher.services.birth_service.BirthService", return_value=mock_svc
    ), patch(
        "lumina_core.birth.champion_freeze_telegram._send_plain", return_value=True
    ):
        out = apply_freeze_command(tmp_path, CMD_ACCEPT_NO_START, source="telegram")
    assert out.get("ok") is True
    mock_svc.accept_champion_birth.assert_called_once()
    kwargs = mock_svc.accept_champion_birth.call_args.kwargs
    assert kwargs.get("start") is False
    assert kwargs.get("source") == "telegram"
    assert load_pending(tmp_path) is None
    clear_pending(tmp_path)
