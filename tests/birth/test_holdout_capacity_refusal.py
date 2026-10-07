"""Thin holdout is a refusal, not an orphan crash, and not a frozen plant."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.birth.holdout_capacity_refusal import (
    CAPACITY_REFUSAL_STAGE,
    persist_holdout_capacity_refusal,
    void_receipts_for_grown_tape,
)
from lumina_launcher.services.birth_runner_lock import reconcile_orphaned_birth_progress
from lumina_launcher.services.birth_service import BirthService
from lumina_launcher.services.birth_status_mapper import resolve_terminal_birth_status


@pytest.mark.unit
def test_persist_refusal_is_visible_and_not_an_orphan(tmp_path: Path) -> None:
    persist_holdout_capacity_refusal(
        tmp_path,
        reason="holdout_capacity_below_n_b_min slots=160 need=500",
        cumulative_trades=1145,
        target_trades=25000,
        ppo_steps=47000,
        birth_start_time=0.0,
    )
    progress = json.loads(
        (tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8")
    )
    assert progress["stage"] == CAPACITY_REFUSAL_STAGE
    assert progress["user_initiated_stop"] is False
    assert "cannot host Awakening" in progress["message"]
    assert "slots=160" in progress["message"]
    status, message = resolve_terminal_birth_status(progress) or ("", "")
    assert status == "paused"
    assert "Awakening" in message

    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    assert reconcile_orphaned_birth_progress(svc) is False
    kept = json.loads(
        (tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8")
    )
    assert kept["stage"] == CAPACITY_REFUSAL_STAGE
    assert "without a user stop" not in kept["message"]
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_void_receipts_when_tape_grows_past_the_exam() -> None:
    host = SimpleNamespace(
        _data_manifest={"actual_calendar_days": 347},
        _stage_pass_receipts=[SimpleNamespace(unique_calendar_days=89, stage="stage5_probe_handoff")],
        _stages_passed=["stage1_trend", "stage5_probe_handoff"],
        _pending_stage_pass_receipt=object(),
    )
    assert void_receipts_for_grown_tape(host) is True
    assert host._stages_passed == []
    assert host._stage_pass_receipts == []
    assert host._pending_stage_pass_receipt is None


@pytest.mark.unit
def test_same_tape_resume_keeps_receipts() -> None:
    host = SimpleNamespace(
        _data_manifest={"actual_calendar_days": 90},
        _stage_pass_receipts=[SimpleNamespace(unique_calendar_days=89, stage="stage1_trend")],
        _stages_passed=["stage1_trend"],
        _pending_stage_pass_receipt=None,
    )
    assert void_receipts_for_grown_tape(host) is False
    assert host._stages_passed == ["stage1_trend"]
