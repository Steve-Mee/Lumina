"""Stage-2 expectancy quality ladder → meta mapping (Phase C)."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.expectancy_stall import (
    map_expectancy_action_to_meta,
    recommended_expectancy_recovery_action,
)
from lumina_core.birth.meta_controller_types import (
    LearningHealth,
    LearningSnapshot,
    RecoveryStrategy,
)
from lumina_core.birth.meta_decide_pre_rollout import MetaDecidePreRolloutMixin


@pytest.mark.unit
def test_quality_ladder_action_order() -> None:
    assert recommended_expectancy_recovery_action(range_flat_ratio=0.45, remediation_step=0) == (
        "policy_rollback"
    )
    assert recommended_expectancy_recovery_action(range_flat_ratio=0.45, remediation_step=1) == (
        "expectancy_quality_reward"
    )
    assert recommended_expectancy_recovery_action(range_flat_ratio=0.35, remediation_step=2) == (
        "explore_reduce"
    )
    assert recommended_expectancy_recovery_action(range_flat_ratio=0.55, remediation_step=2) == (
        "pattern_inject"
    )
    assert recommended_expectancy_recovery_action(range_flat_ratio=0.45, remediation_step=4) == (
        "swarm_after_quality"
    )


@pytest.mark.unit
def test_quality_ladder_anti_edge_never_pattern_or_swarm() -> None:
    """Live: anti-edge must not escalate to pattern_inject/swarm theater."""
    for step in range(2, 7):
        aid = recommended_expectancy_recovery_action(
            range_flat_ratio=0.45,
            remediation_step=step,
            edge_vs_random=-0.05,
        )
        assert aid == "expectancy_quality_reward", (step, aid)
    from lumina_core.birth.expectancy_stall import build_expectancy_quality_meta_fields

    fields = build_expectancy_quality_meta_fields(
        range_flat_ratio=0.45,
        remediation_step=4,
        base_explore_steps=2000,
        exploration_steps=2000,
        edge_vs_random=-0.05,
    )
    assert fields["primary"] == "explore_reduce"
    assert "beat_random" in str(fields["rationale"])


@pytest.mark.unit
def test_map_expectancy_action_never_hold() -> None:
    for step in range(0, 5):
        aid = recommended_expectancy_recovery_action(range_flat_ratio=0.46, remediation_step=step)
        mapped = map_expectancy_action_to_meta(
            aid,
            base_explore_steps=100,
            exploration_steps=400,
            strong_recovery_explore_fraction=0.35,
        )
        assert mapped["primary"] != "hold"
        assert int(mapped["explore_steps"]) >= 100
        assert "stage2_expectancy" in str(mapped["rationale"])


class _MetaHarness(MetaDecidePreRolloutMixin):
    def __init__(self) -> None:
        self.enabled = True
        self.cfg = BirthCurriculumConfig(
            exploration_steps=400,
            strong_recovery_explore_fraction=0.35,
            stage2_hold_stagnation_rollouts=99,
            stage2_expectancy_floor=-0.15,
        )

    def _constitution_remediation_plan(self, snap):  # noqa: ANN001
        return None


@pytest.mark.unit
def test_meta_pre_rollout_expectancy_uses_quality_ladder() -> None:
    h = _MetaHarness()
    snap = LearningSnapshot(
        winrate_history=(0.24, 0.25, 0.247),
        reward_history=(-0.1, -0.1, -0.1),
        stage_trades=712,
        required_trades=300,
        patterns_mined=0,
        patterns_last_inject=0,
        oracle_wins_last_inject=0,
        buffer_size=200,
        escalation_level=1,
        strong_recovery_mode=False,
        strong_recovery_attempts=0,
        low_velocity_attempts=5,
        data_exhausted=False,
        stage=CurriculumStage.STAGE2_RANGE,
        intra_hard_pct=None,
        volume_gate_passed=True,
        range_flat_ratio=0.46,
        range_round_trips=40,
        learning_health=LearningHealth.DECLINING,
        range_total_signals=800,
        plateau_active=True,
        expectancy_quality_step=1,
        stage_wins=176,
        rolling_winrate=0.25,
    )
    plan = h.decide_pre_rollout(
        snap,
        base_explore_steps=100,
        wall_budget_exhausted=False,
        winrate_stagnation_count=0,
        hold_stagnation_count=0,
        over_trading_trap=False,
    )
    assert plan.primary in {
        RecoveryStrategy.EXPLORE_REDUCE,
        RecoveryStrategy.PATTERN_INJECT,
        RecoveryStrategy.REWARD_SHAPING_TWEAK,
    }
    assert "stage2_expectancy" in plan.rationale
    assert plan.primary != RecoveryStrategy.HOLD
