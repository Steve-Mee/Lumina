from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.stage_scorecard import compute_stage_blocker
from lumina_core.birth.starship_birth import (
    EdgeScoreResult,
    humanize_edgescore_blocker,
)
from tests.birth.honest_settlement import honest_closes


@pytest.mark.unit
def test_humanize_edgescore_blocker_expectancy_uses_percents() -> None:
    cfg = BirthCurriculumConfig(
        stage1_edgescore_enabled=True,
        stage1_expectancy_floor=-0.15,
        stage1_winrate_pass_floor=0.35,
    )
    edge = EdgeScoreResult(
        passed=False,
        score=0.25,
        hygiene_ok=True,
        activity_ok=True,
        entropy_ok=True,
        expectancy_ok=False,
        constitution_ok=True,
        message="edgescore=0.450 wr=32.6% blockers=expectancy",
    )
    text = humanize_edgescore_blocker(edge, cfg=cfg, wins=70, trades=215, entropy=0.2)
    assert "edgescore=" not in text.lower()
    assert "blockers=" not in text.lower()
    assert "Expectancy" in text
    # Survival-mode expectancy floor is -50% (legacy -15% was pre-survival).
    assert "-50%" in text or ">= -50%" in text
    assert "EdgeScore 25%" in text


@pytest.mark.unit
def test_humanize_edgescore_blocker_entropy_missing() -> None:
    cfg = BirthCurriculumConfig(stage1_edgescore_enabled=True)
    edge = EdgeScoreResult(
        passed=False,
        score=0.25,
        hygiene_ok=True,
        activity_ok=True,
        entropy_ok=False,
        expectancy_ok=True,
        constitution_ok=True,
        message="debug",
    )
    text = humanize_edgescore_blocker(edge, cfg=cfg, wins=100, trades=200, entropy=None)
    assert text.startswith("Entropy missing")
    assert "EdgeScore 25%" in text


@pytest.mark.unit
def test_compute_stage_blocker_entropy_missing_not_raw_message() -> None:
    cfg = BirthCurriculumConfig(
        stage1_edgescore_enabled=True,
        stage1_winrate_pass_floor=0.35,
        stage1_expectancy_floor=-0.15,
        stage1_entropy_floor=0.05,
        starship_entropy_required_after_ppo_steps=500,
    )
    # WR 40% => hygiene + expectancy ok; entropy missing after warm-up.
    metric, value, reason = compute_stage_blocker(
        CurriculumStage.STAGE1_TREND,
        stage_trades=250,
        stage_wins=100,
        hold_ratio=0.50,
        required=200,
        constitution_violations=0,
        range_flat_ratio=0.5,
        range_round_trips=20,
        range_total_signals=100,
        cfg=cfg,
        rolling_winrate=0.40,
        policy_entropy=None,
        ppo_steps=5000,
    )
    assert metric == "entropy"
    assert reason is not None
    assert "edgescore=" not in reason.lower()
    assert "Entropy missing" in reason


@pytest.mark.unit
def test_compute_stage_blocker_expectancy_not_raw_message() -> None:
    cfg = BirthCurriculumConfig(
        stage1_edgescore_enabled=True,
        stage1_winrate_pass_floor=0.35,
        stage1_expectancy_floor=-0.15,
        stage1_entropy_floor=0.05,
        starship_entropy_required_after_ppo_steps=500,
    )
    # Both lifetime and rolling below hygiene -> expectancy also fails (aligned).
    metric, value, reason = compute_stage_blocker(
        CurriculumStage.STAGE1_TREND,
        stage_trades=250,
        stage_wins=25,  # 10% — fails survival hygiene before expectancy
        hold_ratio=0.50,
        required=200,
        constitution_violations=0,
        range_flat_ratio=0.5,
        range_round_trips=20,
        range_total_signals=100,
        cfg=cfg,
        rolling_winrate=0.10,
        policy_entropy=0.20,
        ppo_steps=5000,
    )
    # Hygiene is checked before expectancy in blocker order.
    assert metric == "winrate"
    assert reason is not None
    assert "edgescore=" not in reason.lower()
    assert "blockers=" not in reason.lower()
    assert "Hygiene" in reason or "hygiene" in reason.lower() or "Survival WR" in reason
    assert "EdgeScore" in reason


@pytest.mark.unit
def test_stage3_blocker_is_mixed_quality_not_survival() -> None:
    """12/08 stall copy: Stage-3 WR fail must not say Survival WR."""
    cfg = BirthCurriculumConfig(
        stage3_edgescore_enabled=True,
        stage3_winrate_floor=0.35,
        stage3_occupancy_pass_enabled=True,
        birth_survival_pass_enabled=True,
    )
    metric, _value, reason = compute_stage_blocker(
        CurriculumStage.STAGE3_MIXED,
        stage_trades=636,
        stage_wins=163,  # 25.6%
        hold_ratio=0.16,
        required=500,
        constitution_violations=0,
        range_flat_ratio=0.32,
        range_round_trips=636,
        range_total_signals=2000,
        cfg=cfg,
        rolling_winrate=0.256,
        policy_entropy=0.20,
        ppo_steps=5000,
    )
    assert metric == "winrate"
    assert reason is not None
    assert "Survival WR" not in reason
    assert "Mixed quality WR" in reason


@pytest.mark.unit
def test_stage3_occupancy_blocker_not_survival() -> None:
    cfg = BirthCurriculumConfig(
        stage3_edgescore_enabled=True,
        stage3_occupancy_pass_enabled=True,
        stage3_position_flat_min=0.25,
        birth_survival_pass_enabled=True,
    )
    metric, _value, reason = compute_stage_blocker(
        CurriculumStage.STAGE3_MIXED,
        stage_trades=500,
        stage_wins=200,  # 40% hygiene OK
        hold_ratio=0.30,
        required=500,
        constitution_violations=0,
        range_flat_ratio=0.023,
        range_round_trips=500,
        range_total_signals=2000,
        cfg=cfg,
        rolling_winrate=0.40,
        policy_entropy=0.20,
        ppo_steps=5000,
        **honest_closes(500),
    )
    assert metric == "occupancy"
    assert reason is not None
    assert "Survival WR" not in reason
    assert "Occupancy" in reason


@pytest.mark.unit
def test_stage2_durable_lifetime_blocker_not_false_green_expectancy() -> None:
    """Rolling 40% / exp −10% must not read as already clearing −15%."""
    cfg = BirthCurriculumConfig(
        stage2_edgescore_enabled=True,
        stage2_expectancy_floor=-0.15,
        stage2_pass_durable_enabled=True,
        stage2_pass_lifetime_delta=0.05,
        stage2_pass_rolling_streak=2,
    )
    metric, value, reason = compute_stage_blocker(
        CurriculumStage.STAGE2_RANGE,
        stage_trades=834,
        stage_wins=249,  # 29.86%
        hold_ratio=0.88,
        required=300,
        constitution_violations=0,
        range_flat_ratio=0.32,
        range_round_trips=834,
        range_total_signals=12584,
        cfg=cfg,
        rolling_winrate=0.40,
        rolling_winrate_display=0.40,
        rolling_wr_eligible=True,
        policy_entropy=5.67,
        ppo_steps=23000,
        policy_trades=834,
        policy_wins=249,
        consecutive_rolling_pass_windows=7,
        **honest_closes(834),
    )
    assert metric in {"durable_lifetime", "expectancy", "occupancy", "median_loss_r"}
    assert value is not None
    assert reason is not None


@pytest.mark.unit
def test_stage3_durable_lifetime_blocker_on_rolling_lift() -> None:
    cfg = BirthCurriculumConfig(
        stage3_edgescore_enabled=True,
        stage3_winrate_floor=0.35,
        stage3_pass_durable_enabled=True,
        stage3_pass_lifetime_delta=0.05,
        stage3_occupancy_pass_enabled=True,
        birth_survival_pass_enabled=True,
    )
    metric, value, reason = compute_stage_blocker(
        CurriculumStage.STAGE3_MIXED,
        stage_trades=636,
        stage_wins=190,  # 29.87%
        hold_ratio=0.50,
        required=500,
        constitution_violations=0,
        range_flat_ratio=0.32,
        range_round_trips=636,
        range_total_signals=2000,
        cfg=cfg,
        rolling_winrate=0.40,
        rolling_winrate_display=0.40,
        rolling_wr_eligible=True,
        policy_entropy=0.20,
        ppo_steps=5000,
        consecutive_rolling_pass_windows=2,
    )
    assert metric == "durable_lifetime"
    assert value is not None
    assert float(value) < 0.30
    assert reason is not None
    assert "Durable lifetime WR" in reason
    assert "30%" in reason
    assert "Survival WR" not in reason
