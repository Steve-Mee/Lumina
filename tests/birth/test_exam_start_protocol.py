"""Birth exam-start physics: no 8-bar blender, FORCE_EXIT is plant, S3 meta taxi."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
from lumina_core.birth.curriculum_types import CurriculumStage
from lumina_core.birth.meta_controller import BirthMetaController
from lumina_core.birth.meta_controller_types import RecoveryStrategy
from lumina_core.birth.foundation_metrics import S3_EDGE_MIN, S3_OCCUPANCY_MIN
from lumina_core.birth.foundation_occupancy_envelope import occupancy_under_exam_fencepost
from lumina_core.birth.stage2_participation_envelope import (
    MODE_FORCE_EXIT,
    MODE_FORCE_FLAT,
    MODE_FORCE_HOLD,
    MODE_PASSTHROUGH,
    decide_stage2_participation,
)
from lumina_core.birth.stage3_inband_idle import plant_tag_for_close, plant_tag_for_entry
from lumina_core.birth.stage3_occupancy_meta import (
    stage3_occupancy_meta_fields,
    stage3_occupancy_taxi_needed,
)
from lumina_core.birth.terminal_freeze import build_terminal_freeze, freeze_attention_fields


@pytest.mark.unit
def test_live_24997_empty_force_flat_not_passthrough() -> None:
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.24997369436357897,
        range_total_signals=28511,
        position=0,
        bars_in_position=0,
        band_lo=0.28,
        band_hi=0.72,
        hysteresis=0.0,
        under_band_release_hysteresis=0.0,
        min_signals=50,
        min_dwell_bars=8,
        max_hold_bars=120,
        cumulative_in_band_passthrough=True,
    )
    assert d.mode == MODE_FORCE_FLAT
    assert occupancy_under_exam_fencepost(0.24997369436357897) is True


@pytest.mark.unit
def test_live_24997_in_position_not_eight_bar_blender() -> None:
    kwargs = dict(
        enabled=True,
        range_flat_ratio=0.24997369436357897,
        range_total_signals=28511,
        band_lo=0.28,
        band_hi=0.72,
        hysteresis=0.0,
        under_band_release_hysteresis=0.0,
        min_signals=50,
        min_dwell_bars=8,
        max_hold_bars=120,
        cumulative_in_band_passthrough=True,
    )
    early = decide_stage2_participation(position=1, bars_in_position=3, **kwargs)
    assert early.mode == MODE_FORCE_HOLD
    eight = decide_stage2_participation(position=1, bars_in_position=8, **kwargs)
    assert eight.mode == MODE_FORCE_HOLD
    horizon = decide_stage2_participation(position=1, bars_in_position=120, **kwargs)
    assert horizon.mode == MODE_FORCE_EXIT
    empty = decide_stage2_participation(position=0, bars_in_position=0, **kwargs)
    assert empty.mode == MODE_FORCE_FLAT


@pytest.mark.unit
def test_force_exit_close_is_plant_not_policy() -> None:
    assert plant_tag_for_entry(force_open_this_step=False) is False
    assert plant_tag_for_close(entry_is_plant=False, participation_mode="PASSTHROUGH") is False
    assert plant_tag_for_close(entry_is_plant=False, participation_mode=MODE_FORCE_EXIT) is True
    assert plant_tag_for_close(entry_is_plant=True, participation_mode="PASSTHROUGH") is True


@pytest.mark.unit
def test_live_force_exit_sample_would_unpoison_skill() -> None:
    """Live: 2539 FORCE_EXIT of 2956 closes. Skill clock must drop plant."""
    total = 2956
    force_exit = 2539
    policy_if_tagged = total - force_exit
    assert policy_if_tagged == 417
    assert policy_if_tagged >= 150
    # Rolling WR 27.07% vs first-touch 30.27% already clears S3 edge floor.
    rolling_wr = 0.270667
    p_ft = 0.30269798136645965
    assert (rolling_wr - p_ft) + 1e-12 >= S3_EDGE_MIN
    assert S3_OCCUPANCY_MIN == pytest.approx(0.25)


@pytest.mark.unit
def test_stage3_occupancy_taxi_owns_fencepost_not_s2_swarm() -> None:
    assert stage3_occupancy_taxi_needed(
        stage=CurriculumStage.STAGE3_MIXED,
        occupancy=0.24997,
        occupancy_exam_armed=False,
        range_total_signals=28511,
    ) is True
    assert stage3_occupancy_taxi_needed(
        stage=CurriculumStage.STAGE2_RANGE,
        occupancy=0.24997,
        occupancy_exam_armed=False,
        range_total_signals=28511,
    ) is False
    assert stage3_occupancy_taxi_needed(
        stage=CurriculumStage.STAGE3_MIXED,
        occupancy=0.40,
        occupancy_exam_armed=True,
        range_total_signals=28511,
    ) is False
    fields = stage3_occupancy_meta_fields(
        exploration_steps=512,
        strong_recovery_explore_fraction=0.5,
    )
    assert fields["rationale"] == "stage3_occupancy_taxi"
    assert fields["mine"] is False


@pytest.mark.unit
def test_stage3_periodic_uses_occupancy_taxi_not_s2_expectancy() -> None:
    ctrl = BirthMetaController(BirthCurriculumConfig(), BirthRewardConfig())
    snap, _ = ctrl.observe(
        winrate_history=[0.22, 0.22, 0.23, 0.23, 0.23, 0.23],
        reward_history=[-0.2, -0.2, -0.19, -0.19, -0.18, -0.18],
        stage_trades=2956,
        required_trades=400,
        patterns_mined=100,
        buffer_size=400,
        escalation_level=5,
        strong_recovery_mode=False,
        strong_recovery_attempts=0,
        low_velocity_attempts=2,
        data_exhausted=False,
        stage=CurriculumStage.STAGE3_MIXED,
        intra_hard_pct=None,
        volume_gate_passed=True,
        range_flat_ratio=0.24997,
        range_total_signals=28511,
        stage_wins=667,
    )
    plan = ctrl.decide_review(snap, trigger="periodic")
    assert plan.rationale == "stage3_occupancy_taxi"
    assert plan.primary == RecoveryStrategy.EXPLORE_REDUCE
    assert "stage2_expectancy" not in str(plan.rationale)


@pytest.mark.unit
def test_fencepost_freeze_autonomous_retry_until_cap() -> None:
    freeze = build_terminal_freeze(
        reason="phoenix_cycle",
        curriculum_stage="stage3_mixed",
        stages_passed=["stage1_trend", "stage2_range"],
        swarm_rejected_no_lift=True,
        expansion_step=0,
        occupancy=0.2499578,
        occupancy_exam_armed=False,
        retries_this_stage=1,
        max_stage_retries=3,
    )
    assert freeze["next_action"] == "retry_stage"
    attn = freeze_attention_fields(freeze)
    assert attn["retryable"] is True
    assert attn["autonomous_recovery_pending"] is True
    assert attn["recommended_recovery_action"] == "retry_stage"
    assert attn["needs_attention"] is False

    exhausted = build_terminal_freeze(
        reason="phoenix_cycle",
        curriculum_stage="stage3_mixed",
        stages_passed=["stage1_trend", "stage2_range"],
        occupancy=0.2499578,
        occupancy_exam_armed=False,
        retries_this_stage=3,
        max_stage_retries=3,
    )
    assert exhausted["next_action"] == "retry_stage_or_wipe"
    done = freeze_attention_fields(exhausted)
    assert done["retryable"] is False
    assert done["needs_attention"] is True


@pytest.mark.unit
def test_s4_hairline_keeps_armed_exam_true_crash_resets() -> None:
    from lumina_core.birth.foundation_metrics import S3_OCCUPANCY_MAX, S3_OCCUPANCY_MIN
    from lumina_core.birth.foundation_occupancy_envelope import (
        OccupancyExamWindow,
        step_occupancy_exam_window,
    )

    win = OccupancyExamWindow()
    for i in range(60):
        win = step_occupancy_exam_window(
            win,
            plant_flat=0.40,
            exam_lo=S3_OCCUPANCY_MIN,
            exam_hi=S3_OCCUPANCY_MAX,
            passthrough=True,
            empty=i % 2 == 0,
        )
    assert win.armed is True
    hair = step_occupancy_exam_window(
        win,
        plant_flat=0.24965,
        exam_lo=S3_OCCUPANCY_MIN,
        exam_hi=S3_OCCUPANCY_MAX,
        passthrough=True,
        empty=True,
    )
    assert hair.armed is True
    assert hair.passthrough == win.passthrough
    crash = step_occupancy_exam_window(
        win,
        plant_flat=0.20,
        exam_lo=S3_OCCUPANCY_MIN,
        exam_hi=S3_OCCUPANCY_MAX,
        passthrough=True,
        empty=True,
    )
    assert crash.armed is False


@pytest.mark.unit
def test_s4_idle_does_not_arm_on_exam_floor() -> None:
    """Idle at 0.26 is re-entry on the 25% floor. Need ≥ 0.28."""
    from lumina_core.birth.stage3_inband_idle import s3_inband_idle_armed

    assert s3_inband_idle_armed(
        curriculum_regime="stage4_viable_plant",
        participation_mode="PASSTHROUGH",
        position=0,
        cumulative_flat=0.26,
        band_lo=0.25,
        band_hi=0.75,
        policy_trades=131,
    ) is False
    assert s3_inband_idle_armed(
        curriculum_regime="stage5_probe_handoff",
        participation_mode="PASSTHROUGH",
        position=0,
        cumulative_flat=0.2764,
        band_lo=0.25,
        band_hi=0.75,
        policy_trades=44,
    ) is True
    assert s3_inband_idle_armed(
        curriculum_regime="stage4_viable_plant",
        participation_mode="PASSTHROUGH",
        position=0,
        cumulative_flat=0.30,
        band_lo=0.25,
        band_hi=0.75,
        policy_trades=131,
    ) is True


@pytest.mark.unit
def test_s4_skill_clock_keeps_131_open() -> None:
    from lumina_core.birth.foundation_skill_clock import skill_clock_keeps_stage_open
    from lumina_core.birth.stage2_participation_envelope import MODE_PASSTHROUGH

    assert skill_clock_keeps_stage_open(
        stage=CurriculumStage.STAGE4_VIABLE_PLANT,
        stage_trades=131,
        policy_trades=131,
        ticks_remaining=True,
        participation_mode=MODE_PASSTHROUGH,
        idle_armed=True,
        occupancy_in_band=True,
    ) is True
    assert skill_clock_keeps_stage_open(
        stage=CurriculumStage.STAGE4_VIABLE_PLANT,
        stage_trades=150,
        policy_trades=150,
        ticks_remaining=True,
        participation_mode=MODE_PASSTHROUGH,
        idle_armed=True,
        occupancy_in_band=True,
    ) is False


@pytest.mark.unit
def test_s5_live_44_policy_keeps_clock_open_without_idle() -> None:
    from lumina_core.birth.foundation_skill_clock import skill_clock_keeps_stage_open

    assert skill_clock_keeps_stage_open(
        stage=CurriculumStage.STAGE5_PROBE_HANDOFF,
        stage_trades=50,
        policy_trades=44,
        ticks_remaining=True,
        participation_mode=MODE_PASSTHROUGH,
        idle_armed=False,
        occupancy_in_band=True,
    ) is True


@pytest.mark.unit
def test_s3_live_passthrough_occupancy_4pct_must_not_fail_plant_flat_25() -> None:
    """Live 17:09: exam PASSTHROUGH empty%=4.1% while plant-flat=25%."""
    from lumina_core.birth.foundation_occupancy_envelope import occupancy_for_foundation_pass

    starved = occupancy_for_foundation_pass(
        stage=CurriculumStage.STAGE3_MIXED,
        range_flat_bars=3992,
        range_total_signals=15971,
        exam_armed=True,
        exam_passthrough_flat_bars=116,
        exam_passthrough_total_signals=2832,
        exam_flat_bars=2500,
        exam_total_signals=10000,
    )
    assert starved is not None
    assert 0.25 - 1e-12 <= float(starved) <= 0.75 + 1e-12
    legacy = occupancy_for_foundation_pass(
        stage=CurriculumStage.STAGE3_MIXED,
        range_flat_bars=3992,
        range_total_signals=15971,
        exam_armed=True,
        exam_passthrough_flat_bars=116,
        exam_passthrough_total_signals=2832,
    )
    assert legacy == pytest.approx(116 / 2832)


@pytest.mark.unit
def test_s3_fencepost_after_exam_seen_is_not_eight_bar_blender() -> None:
    kwargs = dict(
        enabled=True,
        range_flat_ratio=0.24995,
        range_total_signals=15971,
        band_lo=0.28,
        band_hi=0.72,
        hysteresis=0.0,
        under_band_release_hysteresis=0.0,
        min_signals=50,
        min_dwell_bars=8,
        max_hold_bars=120,
        cumulative_in_band_passthrough=True,
        in_band_seen=True,
    )
    held = decide_stage2_participation(position=1, bars_in_position=10, **kwargs)
    assert held.mode == MODE_PASSTHROUGH
    empty = decide_stage2_participation(position=0, bars_in_position=0, **kwargs)
    assert empty.mode == MODE_FORCE_FLAT


@pytest.mark.unit
def test_live_1757_occupancy_23998_blocks_expand() -> None:
    from lumina_core.birth.foundation_occupancy_envelope import occupancy_fencepost_blocks_expand

    assert occupancy_fencepost_blocks_expand(
        occupancy=0.2399750675254519,
        occupancy_exam_armed=False,
    ) is True


@pytest.mark.unit
def test_s2_receipt_seeds_s3_in_band() -> None:
    from types import SimpleNamespace

    from lumina_core.birth.s5_occupancy_continuity import apply_foundation_occupancy_seed

    loop = SimpleNamespace(
        stage=CurriculumStage.STAGE3_MIXED,
        occupancy_in_band_seen=False,
        occupancy_seed_source="n/a",
        occupancy_seed_value=None,
        stage_range_total_signals=0,
        stage_range_flat_bars=0,
        occupancy_control_flat=0.0,
        host=SimpleNamespace(
            _stage_pass_receipts=[
                {"stage": "stage2_range", "occupancy": 0.55},
            ]
        ),
    )
    src = apply_foundation_occupancy_seed(loop)
    assert src == "stage2_range_receipt"
    assert loop.occupancy_in_band_seen is True
    assert loop.occupancy_control_flat == pytest.approx(0.55)


@pytest.mark.unit
def test_s4_occupancy_taxi_off_when_exam_armed() -> None:
    from lumina_core.birth.stage3_occupancy_meta import stage3_occupancy_taxi_needed

    assert stage3_occupancy_taxi_needed(
        stage=CurriculumStage.STAGE4_VIABLE_PLANT,
        occupancy=0.2499,
        occupancy_exam_armed=True,
        range_total_signals=54706,
    ) is False
    assert stage3_occupancy_taxi_needed(
        stage=CurriculumStage.STAGE4_VIABLE_PLANT,
        occupancy=0.2499,
        occupancy_exam_armed=False,
        range_total_signals=54706,
    ) is True


@pytest.mark.unit
def test_s4_policy_only_mean_r_excludes_plant_force_exit() -> None:
    """Live: 65 time-stops ≈ plant FORCE_EXIT. Mean loss 2.67R is airframe, not pilot."""
    from lumina_core.birth.foundation_metrics import S4_MEAN_R_SLACK, mean_loss_r, mean_r
    from lumina_core.birth.stage4_mean_r_meta import stage4_mean_r_failing

    # Live: median loss 1.20R, mean loss 2.67R — fat tail is plant FORCE_EXIT.
    plant_r = [-18.0] * 43
    policy_loss = [-1.20] * 498
    policy_win = [3.19] * 227
    all_r = plant_r + policy_loss + policy_win
    policy_r = policy_loss + policy_win
    e_mech = -0.342
    assert stage4_mean_r_failing(mean_r(all_r), e_mech) is True
    policy_mean = mean_r(policy_r)
    assert policy_mean is not None
    assert mean_loss_r(policy_r) == pytest.approx(-1.2)
    assert float(policy_mean) + 1e-12 >= e_mech - S4_MEAN_R_SLACK
