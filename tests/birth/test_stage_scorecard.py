"""Tests for birth stage scorecard helpers."""

from __future__ import annotations

import pytest

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.stage_scorecard import (
    CURRICULUM_STAGE_COUNT,
    build_scorecard_payload,
    compute_advancing,
    curriculum_index_for_stage,
    enrich_progress_scorecard,
    human_sub_phase,
    pass_criteria_for_stage,
    stage_display_name,
)


@pytest.mark.unit
def test_curriculum_index_for_stage() -> None:
    assert curriculum_index_for_stage(CurriculumStage.STAGE1_TREND) == 1
    assert curriculum_index_for_stage(CurriculumStage.STAGE2_RANGE) == 2
    assert curriculum_index_for_stage(CurriculumStage.STAGE3_MIXED) == 3
    assert curriculum_index_for_stage(CurriculumStage.STAGE4_POLISH) == 4


@pytest.mark.unit
def test_stage_display_name() -> None:
    assert stage_display_name(CurriculumStage.STAGE1_TREND) == "Trend"
    assert stage_display_name(CurriculumStage.STAGE2_RANGE) == "Range patience"


@pytest.mark.unit
def test_pass_criteria_stage1_trend() -> None:
    criteria = pass_criteria_for_stage(CurriculumStage.STAGE1_TREND, target_trades=2000)
    assert criteria.id == "trend_winrate"
    assert criteria.target_trades == 100
    assert criteria.metric_target == 0.45
    assert "45%" in criteria.label


@pytest.mark.unit
def test_pass_criteria_stage2_range() -> None:
    criteria = pass_criteria_for_stage(CurriculumStage.STAGE2_RANGE, target_trades=3000)
    assert criteria.id == "range_roundtrip"
    assert criteria.metric_min == 0.30
    assert criteria.metric_max == 0.70


@pytest.mark.unit
def test_pass_criteria_stage3_mixed() -> None:
    criteria = pass_criteria_for_stage(CurriculumStage.STAGE3_MIXED, target_trades=5000)
    assert criteria.id == "mixed_constitution"
    assert criteria.metric_target == 0.0


@pytest.mark.unit
def test_human_sub_phase_mapping() -> None:
    assert human_sub_phase("curriculum_research") == "Oracle research"
    assert human_sub_phase("ppo_polish") == "Final PPO polish"


@pytest.mark.unit
def test_compute_advancing_with_delta() -> None:
    assert (
        compute_advancing(
            stage_trades=50,
            patterns_mined=10,
            prev_stage_trades=40,
            prev_patterns_mined=10,
            elapsed_since_snapshot_sec=300.0,
        )
        is True
    )


@pytest.mark.unit
def test_compute_advancing_recent_without_delta() -> None:
    assert (
        compute_advancing(
            stage_trades=50,
            patterns_mined=10,
            prev_stage_trades=50,
            prev_patterns_mined=10,
            elapsed_since_snapshot_sec=30.0,
        )
        is True
    )


@pytest.mark.unit
def test_compute_advancing_stale_without_delta() -> None:
    assert (
        compute_advancing(
            stage_trades=50,
            patterns_mined=10,
            prev_stage_trades=50,
            prev_patterns_mined=10,
            elapsed_since_snapshot_sec=200.0,
        )
        is False
    )


@pytest.mark.unit
def test_enrich_progress_scorecard_infers_pass_criteria() -> None:
    enriched = enrich_progress_scorecard(
        {
            "curriculum_stage": "stage1_trend",
            "stage_trades": 190,
            "stage_wins": 76,
            "phase": "ppo_training",
        }
    )
    assert enriched["pass_criteria_id"] == "trend_winrate"
    assert enriched["pass_metric_label"] == "Winrate"
    assert enriched["stage_winrate"] == pytest.approx(0.4, rel=1e-2)


@pytest.mark.unit
def test_build_scorecard_payload_stage1() -> None:
    payload = build_scorecard_payload(
        stage=CurriculumStage.STAGE1_TREND,
        curriculum_index=1,
        stages_passed=[],
        stage_trades=62,
        stage_wins=25,
        stage_hold_signals=0,
        stage_total_signals=62,
        constitution_violations=0,
        target_trades=2000,
        phase="curriculum_research",
        patterns_mined=1240,
        learning_attempt=12,
    )
    assert payload["curriculum_index"] == 1
    assert payload["curriculum_total"] == CURRICULUM_STAGE_COUNT
    assert payload["stage_wins"] == 25
    assert payload["stage_winrate"] == pytest.approx(0.4032, rel=1e-3)
    assert payload["pass_criteria_id"] == "trend_winrate"
    assert payload["sub_phase"] == "curriculum_research"
    assert payload["sub_phase_label"] == "Oracle research"
    assert payload["is_advancing"] is True
