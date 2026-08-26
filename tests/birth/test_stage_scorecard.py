"""Tests for birth stage scorecard helpers."""

from __future__ import annotations

import pytest

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.stage_scorecard import (
    CURRICULUM_STAGE_COUNT,
    build_scorecard_payload,
    calculate_simple_slope,
    compute_advancing,
    curriculum_index_for_stage,
    enrich_adaptation_payload,
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
    assert curriculum_index_for_stage(CurriculumStage.STAGE4_VIABLE_PLANT) == 4
    assert curriculum_index_for_stage(CurriculumStage.STAGE5_PROBE_HANDOFF) == 5
    assert curriculum_index_for_stage(CurriculumStage.STAGE4_POLISH) == 0


@pytest.mark.unit
def test_stage_display_name() -> None:
    assert stage_display_name(CurriculumStage.STAGE1_TREND) == "Closed loop"
    assert stage_display_name(CurriculumStage.STAGE2_RANGE) == "Selectivity"


@pytest.mark.unit
def test_pass_criteria_stage1_trend() -> None:
    criteria = pass_criteria_for_stage(CurriculumStage.STAGE1_TREND, target_trades=2000)
    assert criteria.id == "closed_loop"
    assert criteria.target_trades == 100
    assert criteria.training_budget_trades == 2000
    assert criteria.metric_max == 1.5
    assert "pass gate" in criteria.label
    assert "2000 budget" in criteria.label
    assert "median loss" in criteria.label.lower()


@pytest.mark.unit
def test_pass_criteria_stage1_trend_with_cfg() -> None:
    from lumina_core.birth.config import BirthCurriculumConfig

    cfg = BirthCurriculumConfig(stage1_trend_trades=2000, stage1_edgescore_enabled=True)
    criteria = pass_criteria_for_stage(CurriculumStage.STAGE1_TREND, cfg=cfg)
    assert criteria.id == "closed_loop"
    assert criteria.target_trades == 150
    assert criteria.training_budget_trades == 2000
    assert ">=150 pass gate (2000 budget)" in criteria.label
    assert "median loss" in criteria.label.lower()


@pytest.mark.unit
def test_pass_criteria_stage2_range() -> None:
    criteria = pass_criteria_for_stage(CurriculumStage.STAGE2_RANGE, target_trades=3000)
    assert criteria.id == "selectivity"
    assert criteria.metric_min == 0.30
    assert criteria.metric_max == 0.70


@pytest.mark.unit
def test_pass_criteria_stage3_mixed() -> None:
    criteria = pass_criteria_for_stage(CurriculumStage.STAGE3_MIXED, target_trades=5000)
    assert criteria.id == "mixed_regimes"
    assert criteria.metric_min == pytest.approx(-0.05)
    assert criteria.metric_max is None


@pytest.mark.unit
def test_human_sub_phase_mapping() -> None:
    assert human_sub_phase("curriculum_research") == "Oracle research"
    assert human_sub_phase("ppo_polish") == "Post-Birth PPO polish"


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
        is False
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
    assert enriched["pass_criteria_id"] == "closed_loop"
    assert enriched["pass_metric_label"] == "Median loss R"
    assert enriched["stage_winrate"] == pytest.approx(0.4, rel=1e-2)


@pytest.mark.unit
def test_enrich_progress_scorecard_adds_budget_fields() -> None:
    enriched = enrich_progress_scorecard(
        {
            "curriculum_stage": "stage1_trend",
            "cumulative_trades": 11_074,
            "target_trades": 25_000,
            "trade_budget_source": "birth_v2.trade_budget_cap",
            "terminal_stall_reason": "winrate 23.6% < 45%",
        }
    )
    assert enriched["trade_budget_cap"] == 25_000
    assert enriched["trade_budget_remaining"] == 13_926
    assert enriched["trade_budget_source"] == "birth_v2.trade_budget_cap"
    assert enriched["terminal_stall_reason"] == "winrate 23.6% < 45%"


@pytest.mark.unit
def test_build_scorecard_payload_stage1_with_cfg_uses_stage_pass_trades() -> None:
    from lumina_core.birth.config import BirthCurriculumConfig

    cfg = BirthCurriculumConfig(stage1_trend_trades=2000)
    payload = build_scorecard_payload(
        stage=CurriculumStage.STAGE1_TREND,
        curriculum_index=1,
        stages_passed=[],
        stage_trades=210,
        stage_wins=80,
        stage_hold_signals=0,
        stage_total_signals=210,
        constitution_violations=0,
        target_trades=2000,
        phase="curriculum_learning",
        patterns_mined=100,
        learning_attempt=3,
        cfg=cfg,
    )
    assert payload["stage_target_trades"] == 150
    assert payload["stage_training_budget_trades"] == 2000
    assert ">=150 pass gate (2000 budget)" in payload["pass_criteria_label"]


@pytest.mark.unit
def test_build_scorecard_missing_process_r_is_foundation_blocker() -> None:
    from lumina_core.birth.config import BirthCurriculumConfig

    cfg = BirthCurriculumConfig(
        stage1_trend_trades=2000,
        stage1_edgescore_enabled=True,
    )
    payload = build_scorecard_payload(
        stage=CurriculumStage.STAGE1_TREND,
        curriculum_index=1,
        stages_passed=[],
        stage_trades=6214,
        stage_wins=1543,
        stage_hold_signals=0,
        stage_total_signals=6214,
        constitution_violations=0,
        target_trades=2000,
        phase="curriculum_learning",
        patterns_mined=100,
        learning_attempt=3,
        cfg=cfg,
        unique_calendar_days=50,
        closes_stop=3000,
        closes_target=2000,
        policy_entropy=5.6,
        ppo_steps=2000,
        geometry_net_rr=1.4,
    )
    assert payload["stage_pass_now"] is False
    assert payload["median_loss_r"] is None
    assert payload["stage_blocker_metric"] == "median_loss_r"
    assert "median_loss_r" in str(payload["pass_reason"])


@pytest.mark.unit
def test_build_scorecard_payload_stage1_emits_process_r_and_net_rr() -> None:
    from lumina_core.birth.config import BirthCurriculumConfig

    cfg = BirthCurriculumConfig(stage1_trend_trades=2000)
    losses = [-20.2] * 70
    wins = [28.2] * 80
    payload = build_scorecard_payload(
        stage=CurriculumStage.STAGE1_TREND,
        curriculum_index=1,
        stages_passed=[],
        stage_trades=150,
        stage_wins=80,
        stage_hold_signals=100,
        stage_total_signals=400,
        constitution_violations=0,
        target_trades=2000,
        phase="curriculum_learning",
        patterns_mined=100,
        learning_attempt=1,
        cfg=cfg,
        pnl_series=wins + losses,
        stop_pct=0.000537,
        ref_price=7521.25,
        geometry_net_rr=1.3975,
        unique_calendar_days=40,
        closes_stop=70,
        closes_target=80,
        policy_entropy=5.6,
        ppo_steps=2000,
    )
    assert payload["median_loss_r"] is not None
    assert float(payload["median_loss_r"]) <= 1.5 + 1e-9
    assert payload["geometry_net_rr"] == pytest.approx(1.3975)
    assert payload["geometry_net_rr_after_cost"] == pytest.approx(1.3975)
    assert payload["occupancy"] is None
    assert payload["stage_pass_now"] is True
    assert payload["stage_blocker_metric"] is None
    assert payload["pass_reason"] is None


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
    assert payload["pass_criteria_id"] == "closed_loop"
    assert payload["sub_phase"] == "curriculum_research"
    assert payload["sub_phase_label"] == "Oracle research"
    assert payload["is_advancing"] is True


@pytest.mark.unit
def test_calculate_simple_slope_negative() -> None:
    slope = calculate_simple_slope([0.35, 0.34, 0.33, 0.32, 0.30])
    assert slope < 0


@pytest.mark.unit
def test_calculate_simple_slope_short_history_returns_zero() -> None:
    assert calculate_simple_slope([0.30, 0.29]) == 0.0


@pytest.mark.unit
def test_enrich_adaptation_payload_volume_gate_and_retry_fields() -> None:
    payload = enrich_adaptation_payload(
        stage_trades=120,
        required=100,
        winrate_history=[0.35, 0.34, 0.33, 0.32, 0.30],
        retries_this_stage=1,
        adaptation_history=[{"reason": "metrics_not_improving_within_wall", "chunk_target": 8}],
        adaptation_enabled=True,
        wall_behavior="adaptive",
    )
    assert payload["volume_gate_status"] == "PASSED"
    assert payload["retries_this_stage"] == 1
    assert payload["last_adaptation"]["reason"] == "metrics_not_improving_within_wall"
    assert payload["winrate_trend_slope"] < 0
    assert payload["adaptation_enabled"] is True
    assert payload["wall_behavior"] == "adaptive"


@pytest.mark.unit
def test_learning_metric_target_stage3_uses_recommended_winrate() -> None:
    from lumina_core.birth.config import BirthCurriculumConfig
    from lumina_core.birth.stage_scorecard import learning_metric_target

    cfg = BirthCurriculumConfig(stage1_winrate_recommended=0.45, stage3_edgescore_enabled=False)
    criteria = pass_criteria_for_stage(CurriculumStage.STAGE3_MIXED, cfg=cfg)
    assert criteria.id == "mixed_regimes"
    assert criteria.metric_target is None
    assert criteria.metric_min == pytest.approx(-0.05)
    # Hold-trap / plateau recovery still uses recommended WR; it is not a pass gate.
    assert learning_metric_target(
        CurriculumStage.STAGE3_MIXED,
        cfg=cfg,
        pass_criteria=criteria,
    ) == pytest.approx(0.45)


@pytest.mark.unit
def test_build_scorecard_payload_clears_blockers_below_volume_gate() -> None:
    from lumina_core.birth.config import BirthCurriculumConfig

    cfg = BirthCurriculumConfig()
    payload = build_scorecard_payload(
        stage=CurriculumStage.STAGE3_MIXED,
        curriculum_index=3,
        stages_passed=["stage1_trend", "stage2_range"],
        stage_trades=200,
        stage_wins=70,
        stage_hold_signals=100,
        stage_total_signals=500,
        constitution_violations=0,
        target_trades=5000,
        phase="ppo_training",
        patterns_mined=0,
        learning_attempt=10,
        cfg=cfg,
    )
    assert payload["stage_blocker_metric"] is None
    assert payload["stage_blocker_value"] is None
    assert payload["pass_reason"] is None


@pytest.mark.unit
def test_enrich_progress_scorecard_stage3_uses_session_violations_for_gate() -> None:
    enriched = enrich_progress_scorecard(
        {
            "curriculum_stage": "stage3_mixed",
            "constitution_violations": 11_080,
            "constitution_violations_session": 0,
            "constitution_violations_cumulative": 11_080,
        }
    )
    assert enriched["constitution_violations"] == 0
    assert enriched["constitution_violations_cumulative"] == 11_080

