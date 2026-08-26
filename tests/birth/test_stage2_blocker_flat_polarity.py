"""Stage-2 blocker humanize: low flat = over-trading, not 'need more activity'."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.stage_blocker import compute_stage_blocker
from tests.birth.honest_settlement import honest_closes


@pytest.mark.unit
def test_low_flat_blocker_says_over_trading() -> None:
    cfg = BirthCurriculumConfig(stage2_edgescore_enabled=True)
    metric, value, reason = compute_stage_blocker(
        CurriculumStage.STAGE2_RANGE,
        stage_trades=400,
        stage_wins=100,
        hold_ratio=0.28,
        required=300,
        constitution_violations=0,
        range_flat_ratio=0.28,
        range_round_trips=50,
        range_total_signals=500,
        cfg=cfg,
        policy_entropy=0.2,
        ppo_steps=10_000,
        **honest_closes(400),
    )
    assert metric == "position_flat"
    assert value == pytest.approx(0.28)
    assert reason is not None
    assert "over-trading" in reason
    assert "need more in-range activity" not in reason


@pytest.mark.unit
def test_high_flat_blocker_says_under_activity() -> None:
    cfg = BirthCurriculumConfig(stage2_edgescore_enabled=True)
    metric, value, reason = compute_stage_blocker(
        CurriculumStage.STAGE2_RANGE,
        stage_trades=400,
        stage_wins=140,
        hold_ratio=0.90,
        required=300,
        constitution_violations=0,
        range_flat_ratio=0.90,
        range_round_trips=50,
        range_total_signals=500,
        cfg=cfg,
        policy_entropy=0.2,
        ppo_steps=10_000,
        **honest_closes(400),
    )
    assert metric == "position_flat"
    assert reason is not None
    assert "under-activity" in reason
