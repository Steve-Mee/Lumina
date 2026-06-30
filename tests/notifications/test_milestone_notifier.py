"""Milestone notifier tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.stage_pass_receipt import StagePassReceipt
from lumina_core.notifications.milestone_events import (
    MilestoneCategory,
    MilestoneEvent,
    birth_started_event,
    curriculum_stage_passed_event,
)
from lumina_core.notifications.milestone_notifier import MilestoneNotifier


@pytest.mark.unit
def test_milestone_dedupe_blocks_repeat(tmp_path: Path) -> None:
    telegram = MagicMock()
    telegram.send_milestone_alert.return_value = True
    notifier = MilestoneNotifier(workspace_root=tmp_path, telegram=telegram)
    notifier._enabled = True
    event = MilestoneEvent(
        milestone_id="birth_started",
        category=MilestoneCategory.BIRTH,
        title="Birth gestart",
        summary="Test",
    )
    assert notifier.notify(event) is True
    assert telegram.send_milestone_alert.call_count == 1
    assert notifier.notify(event) is False
    assert telegram.send_milestone_alert.call_count == 1


@pytest.mark.unit
def test_milestone_missing_credentials_fail_closed(tmp_path: Path) -> None:
    telegram = MagicMock()
    telegram.send_milestone_alert.return_value = False
    notifier = MilestoneNotifier(workspace_root=tmp_path, telegram=telegram)
    notifier._enabled = True
    event = birth_started_event(training_mode="certified", trade_budget=100_000)
    assert notifier.notify(event) is False


@pytest.mark.unit
def test_milestone_seed_prevents_resend(tmp_path: Path) -> None:
    telegram = MagicMock()
    telegram.send_milestone_alert.return_value = True
    notifier = MilestoneNotifier(workspace_root=tmp_path, telegram=telegram)
    notifier._enabled = True
    notifier.seed_from_birth_state(
        stages_passed=["stage1_trend", "stage2_range"],
        phase="curriculum_stage",
        training_mode="certified",
    )
    event = curriculum_stage_passed_event(
        CurriculumStage.STAGE1_TREND,
        StagePassReceipt(
            stage="stage1_trend",
            trades=120,
            wins=70,
            winrate=0.583,
            required_trades=100,
            pass_criteria_id="stage1",
            provisional=False,
            passed_at="2026-01-01T00:00:00+00:00",
            engine_version="test",
        ),
    )
    assert notifier.notify(event) is False
    assert telegram.send_milestone_alert.call_count == 0


@pytest.mark.unit
def test_milestone_reset_allows_fresh_run(tmp_path: Path) -> None:
    telegram = MagicMock()
    telegram.send_milestone_alert.return_value = True
    notifier = MilestoneNotifier(workspace_root=tmp_path, telegram=telegram)
    notifier._enabled = True
    event = birth_started_event(training_mode="certified", trade_budget=50_000)
    assert notifier.notify(event) is True
    assert notifier.notify(event) is False
    notifier.reset_notified()
    assert notifier.notify(event) is True
    assert telegram.send_milestone_alert.call_count == 2


@pytest.mark.unit
def test_curriculum_stage_event_summary() -> None:
    event = curriculum_stage_passed_event(
        CurriculumStage.STAGE2_RANGE,
        StagePassReceipt(
            stage="stage2_range",
            trades=150,
            wins=90,
            winrate=0.60,
            required_trades=100,
            pass_criteria_id="stage2",
            provisional=False,
            passed_at="2026-01-01T00:00:00+00:00",
            engine_version="test",
        ),
    )
    assert "Stage 2" in event.title
    assert "150/100" in event.summary
    assert "60.0%" in event.telegram_body()
