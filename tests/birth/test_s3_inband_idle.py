"""S3 in-band idle IMU: HOLD tax + HOLD-mask explore, policy-tagged, SSOT restore."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from lumina_core.birth.birth_constitution_guard import (
    BIRTH_MAX_RISK_STOP_PCT,
    BIRTH_MIN_STOP_PCT,
)
from lumina_core.birth.birth_trade_geometry import BirthTradeGeometry
from lumina_core.birth.config import BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage, evaluate_stage_pass
from lumina_core.birth.foundation_metrics import (
    POLICY_EDGE_MIN_TRADES,
    S2_OCCUPANCY_MAX,
    S2_OCCUPANCY_MIN,
    S3_EDGE_MIN,
    S3_MIN_TRADES,
    S3_OCCUPANCY_MAX,
    S3_OCCUPANCY_MIN,
)
from lumina_core.birth.stage2_participation_envelope import (
    MODE_FORCE_HOLD,
    MODE_FORCE_OPEN,
    MODE_PASSTHROUGH,
    occupancy_control_over,
)
from lumina_core.birth.stage3_inband_idle import (
    S3_INBAND_HOLD_MASK_REASON,
    S3InbandIdleState,
    apply_passthrough_hold_mask,
    plant_tag_for_entry,
    reset_skill_settlement_if_fresh_stage,
    restore_skill_settlement_from_metrics,
    s3_inband_hold_mask,
    s3_inband_hold_tax,
    s3_inband_idle_armed,
    simulate_passthrough_hold_mask_bars,
    snapshot_from_checkpoint_metrics,
)
from lumina_core.rl.reward_shaper import range_patience_step_reward
from tests.birth.honest_settlement import foundation_eval_kwargs, honest_closes


def _armed_kwargs(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "curriculum_regime": "mixed",
        "participation_mode": MODE_PASSTHROUGH,
        "position": 0,
        "cumulative_flat": 0.58,
        "band_lo": 0.25,
        "band_hi": 0.75,
        "policy_trades": 0,
        "policy_edge_min_trades": POLICY_EDGE_MIN_TRADES,
    }
    payload.update(overrides)
    return payload


def test_a_predicate_mixed_passthrough_in_band_thin_policy_armed() -> None:
    assert s3_inband_idle_armed(**_armed_kwargs()) is True  # type: ignore[arg-type]


def test_a_predicate_policy_150_disarmed() -> None:
    assert s3_inband_idle_armed(**_armed_kwargs(policy_trades=150)) is False  # type: ignore[arg-type]


def test_a_predicate_force_open_disarmed() -> None:
    assert (
        s3_inband_idle_armed(**_armed_kwargs(participation_mode=MODE_FORCE_OPEN)) is False  # type: ignore[arg-type]
    )


def test_a_predicate_in_position_disarmed() -> None:
    assert s3_inband_idle_armed(**_armed_kwargs(position=1)) is False  # type: ignore[arg-type]


def test_a_predicate_over_band_disarmed() -> None:
    assert s3_inband_idle_armed(**_armed_kwargs(cumulative_flat=0.90)) is False  # type: ignore[arg-type]


def test_a_predicate_s2_range_disarmed() -> None:
    assert (
        s3_inband_idle_armed(**_armed_kwargs(curriculum_regime="stage2_range")) is False  # type: ignore[arg-type]
    )


def test_b_idle_tax_armed_hold_negative() -> None:
    tax = s3_inband_hold_tax(**_armed_kwargs(action_side=0, tax=0.01))  # type: ignore[arg-type]
    assert tax < 0.0
    assert tax == pytest.approx(-0.01)


def test_b_idle_tax_dominates_inband_flat_bonus() -> None:
    cfg = BirthRewardConfig(enabled=True, range_flat_bonus_coeff=0.003, s3_inband_hold_tax=0.01)
    net = range_patience_step_reward(
        regime="NEUTRAL",
        position_flat=True,
        trade_closed=False,
        cfg=cfg,
        stage_flat_ratio=0.58,
        curriculum_regime="mixed",
        participation_mode=MODE_PASSTHROUGH,
        position=0,
        policy_trades=0,
        band_lo=0.25,
        band_hi=0.75,
        action_side=0,
        cumulative_flat=0.58,
    )
    bonus_only = 0.003 * 0.25
    assert bonus_only > 0.0
    assert net < 0.0
    assert net == pytest.approx(bonus_only - 0.01)


def test_b_idle_tax_dominates_quality_mode_flat_bonus() -> None:
    cfg = BirthRewardConfig(enabled=True, range_flat_bonus_coeff=0.003, s3_inband_hold_tax=0.01)
    net = range_patience_step_reward(
        regime="NEUTRAL",
        position_flat=True,
        trade_closed=False,
        cfg=cfg,
        stage_flat_ratio=0.58,
        expectancy_gap=0.10,
        curriculum_regime="stage3_mixed",
        participation_mode=MODE_PASSTHROUGH,
        position=0,
        policy_trades=0,
        band_lo=0.25,
        band_hi=0.75,
        action_side=0,
        cumulative_flat=0.58,
    )
    assert net < 0.0
    assert net == pytest.approx(0.003 * 0.05 - 0.01)


def test_b_force_hold_tax_zero() -> None:
    tax = s3_inband_hold_tax(
        **_armed_kwargs(participation_mode=MODE_FORCE_HOLD, action_side=0, tax=0.01)  # type: ignore[arg-type]
    )
    assert tax == 0.0


def test_b_s2_inband_flat_bonus_unchanged() -> None:
    cfg = BirthRewardConfig(enabled=True, range_flat_bonus_coeff=0.003, s3_inband_hold_tax=0.01)
    bonus = range_patience_step_reward(
        regime="RANGING",
        position_flat=True,
        trade_closed=False,
        cfg=cfg,
        stage_flat_ratio=0.50,
        curriculum_regime="stage2_range",
        participation_mode=MODE_PASSTHROUGH,
        position=0,
        policy_trades=0,
        band_lo=0.30,
        band_hi=0.70,
        action_side=0,
        cumulative_flat=0.50,
    )
    assert bonus == pytest.approx(0.003 * 0.25)
    assert bonus > 0.0


def test_c_hold_mask_not_yet_at_31() -> None:
    geo = BirthTradeGeometry(stop_pct=0.0012, target_pct=0.0020, source="test")
    action = s3_inband_hold_mask(
        **_armed_kwargs(  # type: ignore[arg-type]
            idle_hold_bars=31,
            min_idle_hold_bars=32,
            action_side=0,
            geometry=geo,
        )
    )
    assert action is None


def test_c_hold_mask_fires_at_32_constitution_stop() -> None:
    geo = BirthTradeGeometry(stop_pct=0.0012, target_pct=0.0020, source="test")
    action = s3_inband_hold_mask(
        **_armed_kwargs(  # type: ignore[arg-type]
            idle_hold_bars=32,
            min_idle_hold_bars=32,
            action_side=0,
            geometry=geo,
            explore_step=0,
        )
    )
    assert action is not None
    side = int(np.clip(np.round(float(action[0])), 0, 2))
    assert side in {1, 2}
    stop = float(action[2])
    assert BIRTH_MIN_STOP_PCT - 1e-12 <= stop <= BIRTH_MAX_RISK_STOP_PCT + 1e-12
    assert stop <= 0.01 + 1e-12


def test_c_hold_mask_off_at_policy_150() -> None:
    geo = BirthTradeGeometry(stop_pct=0.0012, target_pct=0.0020, source="test")
    action = s3_inband_hold_mask(
        **_armed_kwargs(  # type: ignore[arg-type]
            policy_trades=150,
            idle_hold_bars=1000,
            min_idle_hold_bars=32,
            action_side=0,
            geometry=geo,
        )
    )
    assert action is None


def test_c_hold_mask_off_under_force_open() -> None:
    geo = BirthTradeGeometry(stop_pct=0.0012, target_pct=0.0020, source="test")
    action = s3_inband_hold_mask(
        **_armed_kwargs(  # type: ignore[arg-type]
            participation_mode=MODE_FORCE_OPEN,
            idle_hold_bars=32,
            min_idle_hold_bars=32,
            action_side=0,
            geometry=geo,
        )
    )
    assert action is None


def test_d_cloud_failure_replica_mask_replaces_hold_by_bar_32() -> None:
    rows = simulate_passthrough_hold_mask_bars(
        n_bars=40,
        min_idle_hold_bars=32,
        cumulative_flat=0.58,
        policy_trades=0,
        participation_mode=MODE_PASSTHROUGH,
        position=0,
    )
    assert len(rows) == 40
    first_entry = next((i for i, (side, _plant, _r) in enumerate(rows) if side in {1, 2}), None)
    assert first_entry is not None
    assert first_entry == 31  # 0-based bar 32
    side, is_plant, reason = rows[31]
    assert side in {1, 2}
    assert is_plant is False
    assert reason == S3_INBAND_HOLD_MASK_REASON
    assert all(s == 0 for s, _p, _r in rows[:31])


def test_e_plant_tag_force_open_true_mask_false() -> None:
    assert plant_tag_for_entry(force_open_this_step=True) is True
    assert plant_tag_for_entry(force_open_this_step=False) is False
    state = S3InbandIdleState()
    geo = BirthTradeGeometry(stop_pct=0.0012, target_pct=0.0020, source="test")
    hold = np.array([0.0, 0.5, 0.0012, 0.0020], dtype=np.float32)
    for _ in range(32):
        hold = apply_passthrough_hold_mask(
            state=state,
            action=np.array([0.0, 0.5, 0.0012, 0.0020], dtype=np.float32),
            participation_mode=MODE_PASSTHROUGH,
            action_override=None,
            curriculum_regime="mixed",
            position=0,
            cumulative_flat=0.58,
            band_lo=0.25,
            band_hi=0.75,
            policy_trades=0,
            min_idle_hold_bars=32,
            geometry=geo,
        )
    side = int(np.clip(np.round(float(hold[0])), 0, 2))
    assert side in {1, 2}
    assert plant_tag_for_entry(force_open_this_step=False) is False
    assert state.explore_count == 1


def test_f_s2_envelope_over_imu_and_cumulative_passthrough_untouched() -> None:
    from lumina_core.birth.stage2_participation_envelope import decide_stage2_participation

    assert occupancy_control_over(cumulative_flat=0.90, rolling_flat=0.50) == pytest.approx(0.90)
    s3 = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.577,
        rolling_flat_ratio=0.278,
        range_total_signals=8000,
        position=0,
        bars_in_position=0,
        band_lo=0.28,
        band_hi=0.72,
        hysteresis=0.0,
        under_band_release_hysteresis=0.0,
        min_signals=50,
        cumulative_in_band_passthrough=True,
    )
    assert s3.mode == MODE_PASSTHROUGH
    assert s3.reason == "exam_cumulative_in_band"
    s2 = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.903,
        rolling_flat_ratio=0.50,
        range_total_signals=8000,
        position=0,
        bars_in_position=0,
        band_lo=0.30,
        band_hi=0.70,
        min_signals=50,
        cumulative_in_band_passthrough=False,
    )
    assert s2.mode == MODE_FORCE_OPEN


def test_floors_unchanged() -> None:
    assert S3_MIN_TRADES == 400
    assert S3_EDGE_MIN == pytest.approx(-0.05)
    assert S3_OCCUPANCY_MIN == pytest.approx(0.25)
    assert S3_OCCUPANCY_MAX == pytest.approx(0.75)
    assert POLICY_EDGE_MIN_TRADES == 150
    assert S2_OCCUPANCY_MIN == pytest.approx(0.30)
    assert S2_OCCUPANCY_MAX == pytest.approx(0.70)


def _s3_eval(*, policy: int, plant: int, trades: int, closes: dict[str, int], **extra: object):
    payload = {
        "hold_signals": 100,
        "total_signals": 1000,
        "range_hold_signals": 100,
        "range_total_signals": 1000,
        "range_flat_bars": 580,
        "range_round_trips": 80,
        "constitution_violations": 0,
        "target_trades": 400,
        "policy_entropy": 0.5,
        "ppo_steps": 1000,
        "occupancy": 0.58,
        "unique_calendar_days": 88,
        "median_loss_r": 1.05,
        "mean_r": -0.1,
        "first_touch_hit_rate": 0.338,
        "geometry_net_rr": 1.2,
        "trades": trades,
        "wins": 200,
        "policy_trades": policy,
        "policy_wins": 0,
        "plant_trades": plant,
        "plant_wins": 200,
        **closes,
        **foundation_eval_kwargs(unique_calendar_days=88, occupancy=0.58),
    }
    payload.update(extra)
    return evaluate_stage_pass(CurriculumStage.STAGE3_MIXED, **payload)  # type: ignore[arg-type]


def test_g_resume_ssot_does_not_emit_settlement_share_zero() -> None:
    closes = honest_closes(524, flatten_share=0.0)
    metrics = {
        "stage_trades": 524,
        "stage_policy_trades": 0,
        "stage_plant_trades": 524,
        "stage_closes_stop_cum": closes["closes_stop"],
        "stage_closes_target_cum": closes["closes_target"],
        "stage_closes_flatten_cum": closes["closes_flatten"],
        "stage_closes_time_stop_cum": closes["closes_time_stop"],
        "stage_closes_unknown_cum": closes["closes_unknown"],
    }
    snap = snapshot_from_checkpoint_metrics(metrics, stage_trades=524)
    assert snap.policy_trades + snap.plant_trades == 524
    assert snap.policy_trades == 0
    assert snap.plant_trades == 524
    assert snap.settlement_ssot_pending is False
    loop = SimpleNamespace(stage_trades=524, metrics_match_stage=True)
    restore_skill_settlement_from_metrics(loop, metrics)
    assert int(loop.stage_policy_trades) + int(loop.stage_plant_trades) == 524
    result = _s3_eval(
        policy=int(loop.stage_policy_trades),
        plant=int(loop.stage_plant_trades),
        trades=524,
        closes={
            "closes_stop": int(loop.stage_closes_stop_cum),
            "closes_target": int(loop.stage_closes_target_cum),
            "closes_flatten": int(loop.stage_closes_flatten_cum),
            "closes_time_stop": int(loop.stage_closes_time_stop_cum),
            "closes_unknown": int(loop.stage_closes_unknown_cum),
        },
    )
    assert "settlement_share=0.00" not in result.message
    assert "policy_sample" in result.message
    assert "150" in result.message
    share = float(result.settlement_share)
    assert share >= 0.70


def test_g_zeroed_resume_skips_settlement_zero_blocker() -> None:
    metrics = {
        "stage_trades": 524,
        "stage_policy_trades": 0,
        "stage_plant_trades": 524,
        "stage_closes_stop_cum": 0,
        "stage_closes_target_cum": 0,
        "stage_closes_flatten_cum": 0,
        "stage_closes_time_stop_cum": 0,
        "stage_closes_unknown_cum": 0,
    }
    loop = SimpleNamespace(stage_trades=524, metrics_match_stage=True)
    restore_skill_settlement_from_metrics(loop, metrics)
    assert bool(loop._settlement_ssot_pending) is True
    result = evaluate_stage_pass(
        CurriculumStage.STAGE3_MIXED,
        trades=524,
        wins=479,
        hold_signals=100,
        total_signals=1000,
        range_flat_bars=580,
        range_total_signals=1000,
        constitution_violations=0,
        target_trades=400,
        policy_entropy=0.5,
        ppo_steps=1000,
        occupancy=0.58,
        unique_calendar_days=88,
        median_loss_r=1.05,
        mean_r=-0.1,
        first_touch_hit_rate=0.338,
        geometry_net_rr=1.2,
        policy_trades=0,
        policy_wins=0,
        plant_trades=524,
        plant_wins=479,
        closes_stop=0,
        closes_target=0,
        closes_flatten=0,
        closes_time_stop=0,
        closes_unknown=0,
        settlement_ssot_pending=True,
        **foundation_eval_kwargs(unique_calendar_days=88, occupancy=0.58),
    )
    assert "settlement_share=0.00" not in result.message
    assert "policy_sample 0 < 150" in result.message


def test_g_fresh_stage_still_zeros_skill_clocks() -> None:
    loop = SimpleNamespace(
        metrics_match_stage=False,
        stage_trades=0,
        stage_policy_trades=9,
        stage_plant_trades=9,
        stage_closes_stop_cum=9,
    )
    reset_skill_settlement_if_fresh_stage(loop)
    assert int(loop.stage_policy_trades) == 0
    assert int(loop.stage_plant_trades) == 0
    assert int(loop.stage_closes_stop_cum) == 0


def test_g_resume_does_not_zero_restored_counters() -> None:
    loop = SimpleNamespace(
        metrics_match_stage=True,
        stage_trades=524,
        stage_policy_trades=0,
        stage_plant_trades=524,
        stage_closes_stop_cum=200,
        stage_closes_target_cum=324,
        stage_policy_wins=0,
        stage_plant_wins=479,
        stage_closes_flatten_cum=0,
        stage_closes_time_stop_cum=0,
        stage_closes_unknown_cum=0,
    )
    reset_skill_settlement_if_fresh_stage(loop)
    assert int(loop.stage_plant_trades) == 524
    assert int(loop.stage_closes_stop_cum) == 200
    assert int(loop.stage_closes_target_cum) == 324
