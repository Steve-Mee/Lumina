"""Stage-2 skill pass must re-verify with pilot counts (not plant-inflated total)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.stage_pass_receipt_types import StagePassReceipt
from lumina_core.birth.stage_pass_receipt_verify import verify_stage_pass_receipt
from tests.birth.honest_settlement import foundation_receipt_fields, honest_closes


@pytest.mark.unit
def test_stage2_receipt_reeval_uses_skill_policy_counts() -> None:
    """Total WR 25% would fail skill floor; pilot 36% must re-verify OK."""
    cfg = BirthCurriculumConfig(
        stage2_edgescore_enabled=True,
        stage2_skill_metric_policy_only=True,
        stage2_skill_min_trades=100,
        stage2_expectancy_floor=-0.15,
        stage_pass_min_trades=100,
        stage2_range_trades=1000,
        stage_pass_trade_pct=0.30,  # required ~300
    )
    receipt = StagePassReceipt(
        stage=CurriculumStage.STAGE2_RANGE.value,
        trades=400,
        wins=100,  # total 25%
        winrate=0.25,
        required_trades=300,
        pass_criteria_id="range_edgescore",
        provisional=False,
        passed_at=datetime.now(timezone.utc).isoformat(),
        engine_version="test",
        message="range edgescore PASS",
        range_flat_ratio=0.45,
        range_round_trips=50,
        range_total_signals=500,
        range_flat_bars=225,
        hold_signals=200,
        total_signals=500,
        policy_trades=260,
        policy_wins=90,
        plant_trades=140,
        plant_wins=10,
        **honest_closes(400),
        **foundation_receipt_fields(policy_entropy=0.2),
    )
    ok, reason = verify_stage_pass_receipt(
        CurriculumStage.STAGE2_RANGE,
        receipt,
        cfg=cfg,
        training_mode="certified",
    )
    assert ok is True, reason


@pytest.mark.unit
def test_stage2_receipt_fails_when_pilot_weak() -> None:
    cfg = BirthCurriculumConfig(
        stage2_edgescore_enabled=True,
        stage2_skill_metric_policy_only=True,
        stage2_skill_min_trades=100,
        stage2_expectancy_floor=-0.15,
        stage_pass_min_trades=100,
        stage2_range_trades=1000,
        stage_pass_trade_pct=0.30,
    )
    receipt = StagePassReceipt(
        stage=CurriculumStage.STAGE2_RANGE.value,
        trades=400,
        wins=100,
        winrate=0.25,
        required_trades=300,
        pass_criteria_id="range_edgescore",
        provisional=False,
        passed_at=datetime.now(timezone.utc).isoformat(),
        engine_version="test",
        message="range edgescore",
        range_flat_ratio=0.45,
        range_round_trips=50,
        range_total_signals=500,
        range_flat_bars=225,
        hold_signals=200,
        total_signals=500,
        policy_entropy=0.2,
        policy_trades=200,
        policy_wins=50,  # 25% pilot
        plant_trades=200,
        plant_wins=50,
    )
    ok, reason = verify_stage_pass_receipt(
        CurriculumStage.STAGE2_RANGE,
        receipt,
        cfg=cfg,
        training_mode="certified",
    )
    assert ok is False
    assert "re_eval_failed" in reason or "missing_" in reason
