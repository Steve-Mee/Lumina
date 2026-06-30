"""Maturation Telegram bridge tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lumina_core.maturity.milestone_hooks import try_record_milestone
from lumina_core.notifications.maturation_events import maturation_milestone_event
from lumina_core.notifications.milestone_notifier import MilestoneNotifier
from lumina_core.notifications.operator_notifier import notify_maturation


@pytest.mark.unit
def test_maturation_event_builder() -> None:
    event = maturation_milestone_event(
        "sim_real_guard_stable",
        metadata={"consecutive_green_days": 5},
    )
    assert event.milestone_id == "maturation:sim_real_guard_stable"
    assert "READY_FOR_REAL" in event.summary or "GREEN" in event.summary
    assert event.dedupe_key == "maturation:sim_real_guard_stable"


@pytest.mark.unit
def test_maturation_notifier_sends_telegram(tmp_path: Path) -> None:
    telegram = MagicMock()
    telegram.send_milestone_alert.return_value = True
    notifier = MilestoneNotifier(workspace_root=tmp_path, telegram=telegram)
    notifier._enabled = True
    event = maturation_milestone_event("genesis_contract_signed")
    assert notifier.notify(event) is True
    telegram.send_milestone_alert.assert_called_once()


@pytest.mark.unit
def test_try_record_milestone_invokes_notify_maturation(tmp_path: Path) -> None:
    with patch(
        "lumina_core.notifications.operator_notifier.notify_maturation",
        return_value=True,
    ) as notify_mock:
        try_record_milestone(tmp_path, "deck_unlocked")
        try_record_milestone(tmp_path, "deck_unlocked")
    assert notify_mock.call_count == 2
    assert (tmp_path / "state" / "lumina_maturity_progress.json").is_file()


@pytest.mark.unit
def test_notify_maturation_respects_matrix(tmp_path: Path) -> None:
    with patch(
        "lumina_core.notifications.operator_notifier._matrix_enabled",
        return_value=False,
    ):
        sent = notify_maturation("genesis_contract_signed", workspace_root=tmp_path)
    assert sent is False
