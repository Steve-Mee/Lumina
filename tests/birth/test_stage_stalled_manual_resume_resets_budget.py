"""Manual resume from stage_stalled resets adaptation retry window."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.birth.checkpoint import (
    read_checkpoint_payload,
    reset_adaptation_budget_for_manual_resume,
    save_checkpoint,
)
from lumina_core.birth.progress import read_birth_progress, write_birth_progress


@pytest.mark.unit
def test_reset_adaptation_budget_clears_retries_and_phase(tmp_path: Path) -> None:
    save_checkpoint(
        tmp_path,
        cumulative_trades=400,
        ppo_steps=0,
        training_mode="certified",
        stages_passed=[],
        phase="stage_stalled",
        stage_metrics={
            "retries_this_stage": 3,
            "adaptation_tier": 2,
            "adaptation_history": [{"reason": "stall"}],
        },
    )
    write_birth_progress(
        tmp_path,
        stage="stage_stalled",
        phase="stage_stalled",
        message="winrate 26.9% < 45%",
        progress_pct=42.0,
        cumulative_trades=400,
        target_trades=10000,
        pass_reason="winrate 26.9% < 45%",
        curriculum_stage="stage1_trend",
    )

    assert reset_adaptation_budget_for_manual_resume(tmp_path) is True
    payload = read_checkpoint_payload(tmp_path)
    assert payload is not None
    assert payload.get("phase") == "curriculum_learning"
    metrics = payload.get("stage_metrics") or {}
    assert int(metrics.get("retries_this_stage", -1)) == 0
    assert int(metrics.get("adaptation_tier", -1)) == 2

    progress = read_birth_progress(tmp_path)
    assert progress.get("phase") == "curriculum_learning"
    assert progress.get("stage") == "training_running"
    assert int(progress.get("retries_this_stage", -1)) == 0


@pytest.mark.unit
def test_reset_adaptation_budget_missing_checkpoint(tmp_path: Path) -> None:
    assert reset_adaptation_budget_for_manual_resume(tmp_path) is False
