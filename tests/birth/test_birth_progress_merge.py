"""Tests for birth progress extra merge (PEP 448 duplicate kwargs guard)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.birth.progress import merge_birth_progress_extra, write_birth_progress


@pytest.mark.unit
def test_merge_birth_progress_extra_last_wins() -> None:
    scorecard = {"constitution_violations": 2, "stage_wins": 10}
    constitution_fields = {
        "constitution_violations": 5,
        "constitution_violations_session": 2,
        "constitution_violations_cumulative": 5,
    }
    merged = merge_birth_progress_extra(scorecard, constitution_fields)
    assert merged["constitution_violations"] == 5
    assert merged["constitution_violations_session"] == 2
    assert merged["constitution_violations_cumulative"] == 5
    assert merged["stage_wins"] == 10


@pytest.mark.unit
def test_write_birth_progress_accepts_merged_scorecard_and_constitution(
    tmp_path: Path,
) -> None:
    """Regression: dual ** unpack of constitution_violations raised TypeError (PEP 448)."""
    scorecard = {"constitution_violations": 0, "stage_wins": 0, "stage_winrate": 0.0}
    constitution_fields = {
        "constitution_violations": 0,
        "constitution_violations_session": 0,
        "constitution_violations_cumulative": 0,
    }
    merged = merge_birth_progress_extra(scorecard, constitution_fields)
    write_birth_progress(
        tmp_path,
        stage="training_running",
        phase="curriculum_learning",
        message="Curriculum stage1_trend: 10 / 500 trades",
        progress_pct=30.0,
        cumulative_trades=10,
        target_trades=5000,
        **merged,
    )
    progress_path = tmp_path / "state" / "lumina_birth_progress.json"
    assert progress_path.is_file()
    text = progress_path.read_text(encoding="utf-8")
    assert "constitution_violations" in text
    assert "constitution_violations_session" in text
    assert "constitution_violations_cumulative" in text


@pytest.mark.unit
def test_dual_star_unpack_raises_without_merge(tmp_path: Path) -> None:
    scorecard = {"constitution_violations": 0}
    constitution_fields = {"constitution_violations": 0, "constitution_violations_session": 0}
    with pytest.raises(TypeError, match="multiple values for keyword argument"):
        write_birth_progress(
            tmp_path,
            stage="training_running",
            phase="curriculum_learning",
            message="test",
            progress_pct=1.0,
            **scorecard,
            **constitution_fields,
        )


@pytest.mark.unit
def test_write_birth_progress_clears_stale_blockers_on_stage_change(tmp_path: Path) -> None:
    write_birth_progress(
        tmp_path,
        stage="training_running",
        phase="curriculum_learning",
        message="stage2 stalled",
        progress_pct=50.0,
        curriculum_stage="stage2_range",
        stage_blocker_metric="position_flat",
        stage_blocker_value=0.7071,
        pass_reason="position_flat 70.7% outside 30–70%",
    )
    write_birth_progress(
        tmp_path,
        stage="training_running",
        phase="ppo_training",
        message="stage3 rolling",
        progress_pct=60.0,
        curriculum_stage="stage3_mixed",
        stage_trades=50,
        stage_blocker_metric=None,
        stage_blocker_value=None,
        pass_reason=None,
    )
    progress_path = tmp_path / "state" / "lumina_birth_progress.json"
    loaded = json.loads(progress_path.read_text(encoding="utf-8"))
    assert loaded["curriculum_stage"] == "stage3_mixed"
    assert loaded.get("stage_blocker_metric") is None
    assert loaded.get("pass_reason") is None
