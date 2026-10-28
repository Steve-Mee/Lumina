"""Foundation pass law stays fail-closed (skill split + idle IMU do not lower floors)."""

from __future__ import annotations

from lumina_core.birth.curriculum import CurriculumStage, evaluate_stage_pass
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES, S3_MIN_TRADES
from tests.birth.honest_settlement import honest_closes


def test_s3_replica_still_policy_sample_not_volume_zero() -> None:
    result = evaluate_stage_pass(
        CurriculumStage.STAGE3_MIXED,
        trades=729,
        wins=200,
        hold_signals=100,
        total_signals=1000,
        range_flat_bars=576,
        range_total_signals=1000,
        constitution_violations=0,
        target_trades=400,
        policy_entropy=0.5,
        ppo_steps=1000,
        occupancy=0.576,
        unique_calendar_days=88,
        median_loss_r=1.05,
        mean_r=-0.1,
        first_touch_hit_rate=0.338,
        geometry_net_rr=1.2,
        policy_trades=0,
        policy_wins=0,
        plant_trades=729,
        plant_wins=200,
        **honest_closes(729),
    )
    assert result.passed is False
    assert "policy_sample" in result.message
    assert f"{POLICY_EDGE_MIN_TRADES}" in result.message
    assert "trades 0 < 400" not in result.message
    assert f"trades {729} < {S3_MIN_TRADES}" not in result.message
    assert "edge=-0.338" not in result.message
