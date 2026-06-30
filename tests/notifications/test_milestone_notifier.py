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
    birth_gate_warning_event,
    birth_started_event,
    curriculum_stage_passed_event,
    evolution_proof_passed_event,
    hold_trap_detected_event,
    learning_breakthrough_event,
    plateau_entered_event,
    plateau_evolution_forced_advance_event,
    stall_remediation_cycle_event,
    trade_budget_milestone_event,
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


@pytest.mark.unit
def test_plateau_milestone_event_bodies() -> None:
    entered = plateau_entered_event(stage_trades=5000, winrate=0.27, pass_target=0.45)
    assert "plateau_entered" == entered.milestone_id
    assert "5,000" in entered.telegram_body()

    forced = plateau_evolution_forced_advance_event(
        step=2, max_steps=8, action="POLICY_ROLLBACK", winrate=0.268
    )
    assert "Forced evolution" in forced.title
    assert "26.8%" in forced.telegram_body()


@pytest.mark.unit
def test_breakthrough_and_budget_milestones() -> None:
    breakthrough = learning_breakthrough_event(
        winrate=0.30, prior_mean=0.27, delta=0.03
    )
    assert breakthrough.milestone_id == "learning_breakthrough"
    assert "30.0%" in breakthrough.telegram_body()

    budget = trade_budget_milestone_event(pct=75, cumulative_trades=75_000, cap=100_000)
    assert budget.milestone_id == "trade_budget_75"
    assert "75%" in budget.summary


@pytest.mark.unit
def test_seed_plateau_milestones_on_resume(tmp_path: Path) -> None:
    telegram = MagicMock()
    telegram.send_milestone_alert.return_value = True
    notifier = MilestoneNotifier(workspace_root=tmp_path, telegram=telegram)
    notifier._enabled = True
    notifier.seed_from_birth_state(
        stages_passed=["stage1_trend"],
        phase="curriculum_learning",
        training_mode="certified",
        plateau_active=True,
        evolution_step=2,
        hold_trap_detected=True,
    )
    assert notifier.notify(
        plateau_entered_event(stage_trades=100, winrate=0.25, pass_target=0.45)
    ) is False
    assert notifier.notify(hold_trap_detected_event(hold_ratio=0.6, winrate=0.25)) is False
    assert telegram.send_milestone_alert.call_count == 0


@pytest.mark.unit
def test_evolution_proof_and_gate_warning_events() -> None:
    passed = evolution_proof_passed_event(oos_winrate=0.50, lift=0.08)
    assert passed.milestone_id == "evolution_proof_passed"
    assert "50.0%" in passed.telegram_body()

    warning = birth_gate_warning_event(threshold=0.36, recommended=0.45)
    assert warning.milestone_id == "birth_gate_warning"
    assert "36%" in warning.telegram_body() or "36" in warning.telegram_body()


@pytest.mark.unit
def test_stall_remediation_cycle_event_format() -> None:
    event = stall_remediation_cycle_event(cycle=2, max_cycles=3)
    assert event.milestone_id == "stall_remediation_cycle_2"
    assert "2 of 3" in event.summary
