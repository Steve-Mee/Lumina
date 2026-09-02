"""S3 exam clocks: volume = total stage closes, edge = policy-only (BIRTH-CLOUD-003).

Cloud-failure replica numbers are the S2-rerun freeze. Thin pilot ≠ edge=-p_ft.
"""

from __future__ import annotations

import pytest

from lumina_core.birth.curriculum import CurriculumStage, evaluate_stage_pass
from lumina_core.birth.foundation_metrics import (
    POLICY_EDGE_MIN_TRADES,
    S2_MIN_TRADES,
    S2_OCCUPANCY_MAX,
    S2_OCCUPANCY_MIN,
    S3_EDGE_MIN,
    S3_MIN_TRADES,
    S3_OCCUPANCY_MAX,
    S3_OCCUPANCY_MIN,
    S4_EDGE_MIN,
    S5_EDGE_MIN,
    build_foundation_snapshot,
)
from lumina_core.birth.stage2_participation_envelope import occupancy_control_over
from lumina_core.birth.stage_blocker_foundation import (
    _metric_from_blocker,
    compute_foundation_hud_blocker,
)
from tests.birth.honest_settlement import honest_closes


def test_floors_unchanged() -> None:
    assert S3_MIN_TRADES == 400
    assert S3_EDGE_MIN == pytest.approx(-0.05)
    assert S3_OCCUPANCY_MIN == pytest.approx(0.25)
    assert S3_OCCUPANCY_MAX == pytest.approx(0.75)
    assert S2_OCCUPANCY_MIN == pytest.approx(0.30)
    assert S2_OCCUPANCY_MAX == pytest.approx(0.70)
    assert S4_EDGE_MIN == pytest.approx(0.0)
    assert S5_EDGE_MIN == pytest.approx(-0.03)
    assert POLICY_EDGE_MIN_TRADES == 150
    assert S2_MIN_TRADES == 250


def _physics(**overrides: object) -> dict[str, object]:
    trades = int(overrides.get("trades", 729))  # type: ignore[arg-type]
    payload: dict[str, object] = {
        "hold_signals": 100,
        "total_signals": 1000,
        "range_hold_signals": 100,
        "range_total_signals": 1000,
        "range_flat_bars": 576,
        "range_round_trips": 80,
        "constitution_violations": 0,
        "target_trades": 400,
        "policy_entropy": 0.5,
        "ppo_steps": 1000,
        "occupancy": 0.576,
        "unique_calendar_days": 88,
        "median_loss_r": 1.05,
        "mean_r": -0.1,
        "first_touch_hit_rate": 0.338,
        "geometry_net_rr": 1.2,
        "trades": trades,
        "wins": 200,
        **honest_closes(trades),
    }
    payload.update(overrides)
    return payload


def _s3(**overrides: object):
    return evaluate_stage_pass(CurriculumStage.STAGE3_MIXED, **_physics(**overrides))  # type: ignore[arg-type]


def test_a_cloud_replica_volume_clock_not_zeroed_policy() -> None:
    result = _s3(trades=729, wins=200, policy_trades=0, policy_wins=0)
    assert result.passed is False
    assert result.trades == 729
    assert result.progress_fields["foundation_skill_trades"] == 0
    assert result.progress_fields["foundation_skill_wins"] == 0
    assert result.edge is None
    msg = result.message
    assert "trades 0 < 400" not in msg
    assert "edge=-0.338" not in msg
    assert "edge=None" not in msg
    assert "policy_sample" in msg
    assert "150" in msg
    assert f"trades {729} < {S3_MIN_TRADES}" not in msg


def test_b_honest_edge_fail_when_policy_sample_adequate() -> None:
    result = _s3(
        trades=729,
        wins=200,
        policy_trades=200,
        policy_wins=40,
    )
    assert result.passed is False
    msg = result.message
    assert "policy_sample" not in msg
    assert "trades 0 < 400" not in msg
    assert "edge=" in msg
    assert "< -0.05" in msg or f"< {S3_EDGE_MIN}" in msg
    assert result.edge is not None
    assert result.edge == pytest.approx(0.20 - 0.338, abs=1e-9)
    assert result.progress_fields["foundation_skill_wr"] == pytest.approx(0.20)
    assert result.progress_fields["foundation_skill_trades"] == 200


def test_c_honest_edge_pass_leg() -> None:
    result = _s3(
        trades=729,
        wins=200,
        policy_trades=200,
        policy_wins=64,
        occupancy=0.576,
        unique_calendar_days=88,
        median_loss_r=1.05,
    )
    assert result.edge is not None
    assert result.edge == pytest.approx(0.32 - 0.338, abs=1e-9)
    assert result.edge + 1e-12 >= S3_EDGE_MIN
    assert result.passed is True, result.message
    assert "policy_sample" not in result.message
    assert "trades 0 < 400" not in result.message
    assert "net_rr" not in result.message


def test_d_build_foundation_snapshot_skill_clock() -> None:
    empty = build_foundation_snapshot(
        trades=729, wins=200, skill_trades=0, skill_wins=0, p_ft=0.338
    )
    assert empty.edge is None
    assert empty.trades == 729
    assert empty.skill_trades == 0
    assert empty.skill_wr == pytest.approx(0.0)

    thin = build_foundation_snapshot(
        trades=729,
        wins=200,
        skill_trades=149,
        skill_wins=80,
        p_ft=0.338,
    )
    assert thin.edge is None
    assert thin.skill_trades == 149
    assert thin.skill_wr == pytest.approx(80 / 149)

    ready = build_foundation_snapshot(
        trades=729,
        wins=200,
        skill_trades=150,
        skill_wins=48,
        p_ft=0.338,
    )
    assert ready.edge == pytest.approx(0.32 - 0.338, abs=1e-9)
    assert ready.skill_wr == pytest.approx(0.32)

    compat = build_foundation_snapshot(trades=200, wins=80, p_ft=0.338)
    assert compat.skill_trades == 200
    assert compat.skill_wins == 80
    assert compat.skill_wr == pytest.approx(0.40)
    assert compat.edge == pytest.approx(0.40 - 0.338, abs=1e-9)

    fields = empty.to_progress_fields()
    assert fields["foundation_skill_trades"] == 0
    assert fields["foundation_skill_wins"] == 0
    assert fields["edge_vs_first_touch"] is None
    assert fields["foundation_skill_wr"] == pytest.approx(0.0)


def test_e_s2_volume_clock_no_policy_sample() -> None:
    def _s2(**overrides: object):
        payload = _physics(
            trades=815,
            wins=250,
            occupancy=0.50,
            range_round_trips=100,
            target_trades=250,
            **overrides,
        )
        return evaluate_stage_pass(CurriculumStage.STAGE2_RANGE, **payload)  # type: ignore[arg-type]

    with_pilot = _s2(policy_trades=253, policy_wins=80)
    assert "trades 0 < 250" not in with_pilot.message
    assert "policy_sample" not in with_pilot.message
    assert with_pilot.trades == 815
    assert with_pilot.passed is True, with_pilot.message

    no_pilot = _s2(policy_trades=0, policy_wins=0)
    assert "policy_sample" not in no_pilot.message
    assert "trades 0 < 250" not in no_pilot.message
    assert no_pilot.trades == 815
    assert no_pilot.passed is True, no_pilot.message

    over_occ = _s2(policy_trades=253, policy_wins=80, occupancy=0.90)
    assert over_occ.passed is False
    assert "occupancy" in over_occ.message
    assert occupancy_control_over(cumulative_flat=0.90, rolling_flat=0.50) == pytest.approx(
        0.90
    )


def test_f_s1_unchanged_no_edge_or_policy_sample() -> None:
    result = evaluate_stage_pass(
        CurriculumStage.STAGE1_TREND,
        **_physics(  # type: ignore[arg-type]
            trades=160,
            wins=50,
            occupancy=None,
            unique_calendar_days=20,
            policy_trades=0,
            policy_wins=0,
            first_touch_hit_rate=0.338,
            geometry_net_rr=1.2,
        ),
    )
    msg = result.message
    assert "policy_sample" not in msg
    assert "occupancy" not in msg
    assert "edge=" not in msg
    assert result.passed is True, msg


def test_g_hud_maps_policy_sample_not_edge() -> None:
    metric, _ = _metric_from_blocker("policy_sample 0 < 150")
    assert metric == "policy_sample"
    edge_metric, _ = _metric_from_blocker("edge=-0.338 < -0.05")
    assert edge_metric == "edge"

    hud = compute_foundation_hud_blocker(
        CurriculumStage.STAGE3_MIXED,
        trades=729,
        wins=200,
        required=400,
        constitution_violations=0,
        occupancy=0.576,
        median_loss_r=1.05,
        first_touch_hit_rate=0.338,
        unique_calendar_days=88,
        settlement_ok=True,
        settlement_share=1.0,
        entropy_alive=True,
        skill_trades=0,
        skill_wins=0,
    )
    assert hud is not None
    metric_id, value, reason = hud
    assert metric_id == "policy_sample"
    assert metric_id != "edge"
    assert reason is not None
    assert "policy_sample" in reason
    assert "edge=-0.338" not in reason
    assert "edge=None" not in reason
    assert value == pytest.approx(0.0)
