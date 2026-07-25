"""Raptor v11: beyond-gate prefer train over recovery spam."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.plateau_escalator import should_trades_beyond_gate_hard_stop
from lumina_core.birth.stage_loop_recovery_adaptation import StageLoopRecoveryAdaptationMixin


class _FakeRecovery(StageLoopRecoveryAdaptationMixin):
    def __init__(self) -> None:
        self.cur_cfg = BirthCurriculumConfig(
            adaptation_enabled=True,
            wall_behavior="adaptive",
            adaptation_stuck_min_rollouts=5,
            plateau_trades_beyond_gate_multiplier=3,
            stage3_mixed_trades=500,
            max_adaptation_tiers=4,
            max_stage_retries=3,
            max_escalation_level=5,
        )
        self.stage = CurriculumStage.STAGE3_MIXED
        self.stage_trades = 2000
        self.required = 500
        self.rollouts_since_last_adaptation = 0
        self.adaptation_tier = 3
        self.retries_this_stage = 0
        self.plateau_state = SimpleNamespace(active=True, evolution_step=2)
        self.host = SimpleNamespace(cumulative_trades=15000, buffer=[], ppo_steps=100)
        self.bus = MagicMock()
        self.effective_trade_budget_cap = 50_000
        self.remediation_state = SimpleNamespace(
            active=False, remediation_step=0, remediation_cycle=0
        )

    def _should_terminal_stall_in_adaptive(self) -> bool:
        return False

    def _maybe_extend_trade_budget(self) -> bool:
        return False

    def _adaptation_recovery_context(self, **kwargs):  # type: ignore[no-untyped-def]
        return kwargs

    def _apply_bus_adaptation_result(self, result):  # type: ignore[no-untyped-def]
        return bool(result.get("applied"))


@pytest.mark.unit
def test_beyond_gate_hard_stop_at_2000_with_required_500() -> None:
    cfg = BirthCurriculumConfig(plateau_trades_beyond_gate_multiplier=3)
    assert should_trades_beyond_gate_hard_stop(2000, 500, cfg) is True


@pytest.mark.unit
def test_adaptive_recovery_debounced_beyond_gate() -> None:
    fake = _FakeRecovery()
    fake.rollouts_since_last_adaptation = 1
    fake.bus.adaptation_try_recovery.return_value = {"applied": True}
    assert (
        fake._try_adaptive_stall_recovery(
            failure_key="stage3_foundation",
            trigger_type="certified_stall",
        )
        is False
    )
    fake.bus.adaptation_try_recovery.assert_not_called()


@pytest.mark.unit
def test_adaptive_recovery_allowed_after_min_rollouts() -> None:
    fake = _FakeRecovery()
    fake.rollouts_since_last_adaptation = 5
    fake.bus.adaptation_try_recovery.return_value = {"applied": True}
    assert (
        fake._try_adaptive_stall_recovery(
            failure_key="stage3_foundation",
            trigger_type="certified_stall",
        )
        is True
    )
    fake.bus.adaptation_try_recovery.assert_called_once()


@pytest.mark.unit
def test_adaptive_recovery_not_debounced_before_gate() -> None:
    fake = _FakeRecovery()
    fake.stage_trades = 100
    fake.required = 500
    fake.rollouts_since_last_adaptation = 0
    fake.bus.adaptation_try_recovery.return_value = {"applied": True}
    assert (
        fake._try_adaptive_stall_recovery(
            failure_key="stage3_foundation",
            trigger_type="certified_stall",
        )
        is True
    )
