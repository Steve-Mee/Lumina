"""Raptor v6: soft entry blocks must not fail stage graduation."""

from __future__ import annotations

import pytest

from lumina_core.birth.birth_constitution_guard import BirthConstitutionGuard
from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage, evaluate_stage_pass
from tests.birth.honest_settlement import foundation_eval_kwargs, honest_closes


@pytest.mark.unit
def test_risk_exceeds_is_soft_block_not_hard_violation() -> None:
    guard = BirthConstitutionGuard(event_bus=None)
    for _ in range(100):
        ok, reason = guard.check_entry(
            tick={"news_window_active": 0.0},
            side=1,
            stop_pct=0.02,  # 2% of equity > 1% risk cap
            equity=50_000.0,
            auto_clip=False,  # legacy veto path
        )
        assert ok is False
        assert reason == "risk_cap"
    assert guard.soft_blocks == 100
    assert guard.violations == 0


@pytest.mark.unit
def test_stage2_passes_with_soft_blocks_only() -> None:
    """Volume + flat band + RT OK; soft blocks must not set constitution_violations."""
    cfg = BirthCurriculumConfig(stage2_edgescore_enabled=False)
    # hard violations = 0 even if policy attempted 679 risk-cap entries
    result = evaluate_stage_pass(
        CurriculumStage.STAGE2_RANGE,
        trades=300,
        wins=96,
        hold_signals=5000,
        total_signals=7000,
        range_hold_signals=5000,
        range_total_signals=7000,
        range_flat_bars=4300,  # ~61% flat
        range_round_trips=300,
        constitution_violations=0,  # hard only
        target_trades=3000,
        cfg=cfg,
        allow_provisional=False,
        **honest_closes(300),
        **foundation_eval_kwargs(),
    )
    assert result.passed is True


@pytest.mark.unit
def test_stage2_fails_on_hard_violations() -> None:
    cfg = BirthCurriculumConfig(stage2_edgescore_enabled=False)
    result = evaluate_stage_pass(
        CurriculumStage.STAGE2_RANGE,
        trades=300,
        wins=96,
        hold_signals=5000,
        total_signals=7000,
        range_hold_signals=5000,
        range_total_signals=7000,
        range_flat_bars=4300,
        range_round_trips=300,
        constitution_violations=5,
        target_trades=3000,
        cfg=cfg,
        allow_provisional=False,
    )
    assert result.passed is False


@pytest.mark.unit
def test_hard_record_increments_violations() -> None:
    guard = BirthConstitutionGuard(event_bus=None)
    guard.record_hard_violation("naked_order_simulated")
    assert guard.violations == 1
    assert guard.soft_blocks == 0
