"""Raptor v8: stage2 hard receipts must survive integrity re-eval with range metrics."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage, evaluate_stage_pass
from lumina_core.birth.stage_pass_receipt import (
    receipt_from_stage_result,
    verify_stage_pass_receipt,
)
from tests.birth.honest_settlement import foundation_eval_kwargs, honest_closes


@pytest.mark.unit
def test_stage2_receipt_with_range_fields_verifies_certified() -> None:
    cfg = BirthCurriculumConfig(stage2_edgescore_enabled=False)
    result = evaluate_stage_pass(
        CurriculumStage.STAGE2_RANGE,
        trades=300,
        wins=96,
        hold_signals=1000,
        total_signals=2000,
        range_hold_signals=4000,
        range_total_signals=7121,
        range_flat_bars=int(0.6155 * 7121),
        range_round_trips=300,
        constitution_violations=0,
        target_trades=3000,
        cfg=cfg,
        allow_provisional=False,
        **honest_closes(300),
        **foundation_eval_kwargs(),
    )
    assert result.passed is True
    receipt = receipt_from_stage_result(
        CurriculumStage.STAGE2_RANGE,
        result,
        cfg=cfg,
        hold_signals=1000,
        total_signals=2000,
        range_hold_signals=4000,
        range_total_signals=7121,
        range_flat_bars=int(0.6155 * 7121),
    )
    assert receipt.range_total_signals >= 50
    assert receipt.range_flat_ratio > 0.3
    ok, reason = verify_stage_pass_receipt(
        CurriculumStage.STAGE2_RANGE,
        receipt,
        cfg=cfg,
        training_mode="certified",
    )
    assert ok is True, reason


@pytest.mark.unit
def test_legacy_stage2_message_fails_without_settlement_ssot() -> None:
    """Older receipts without foundation_v2 fail-closed."""
    from lumina_core.birth.stage_pass_receipt import StagePassReceipt

    cfg = BirthCurriculumConfig(stage2_edgescore_enabled=False)
    receipt = StagePassReceipt(
        stage="stage2_range",
        trades=300,
        wins=96,
        winrate=0.32,
        required_trades=300,
        pass_criteria_id="range_roundtrip",
        provisional=False,
        passed_at="2026-07-25T10:57:09+00:00",
        engine_version="BRO-v2",
        message=(
            "range_flat_ratio=61.55% round_trips=300 trades=300/300 "
            "constitution_violations=0 (range_ticks=7121)"
        ),
        winrate_gate=None,
    )
    ok, reason = verify_stage_pass_receipt(
        CurriculumStage.STAGE2_RANGE,
        receipt,
        cfg=cfg,
        training_mode="certified",
    )
    assert ok is False
    assert (
        "settle" in (reason or "").lower()
        or "settlement" in (reason or "").lower()
        or "missing_or_invalid_foundation_schema" in (reason or "")
        or "missing_median_loss_r" in (reason or "")
    )
