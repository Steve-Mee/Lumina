"""Brain caps-bypass in mode sim is closed (ADR-0064 Proposed / needs human review)."""

from __future__ import annotations

import pytest

from lumina_core.risk.risk_controller import HardRiskController
from lumina_core.risk.risk_limits import RiskLimits


@pytest.mark.unit
@pytest.mark.safety_gate
def test_sim_mode_flag_does_not_bypass_when_enforced() -> None:
    limits = RiskLimits(sim_mode=True, daily_loss_cap=-150.0, enforce_session_guard=False)
    controller = HardRiskController(limits, enforce_rules=True)
    controller.state.daily_pnl = -2000.0
    allowed, reason = controller.check_can_trade("MES", "trending_up", 100.0)
    assert allowed is False
    assert "DAILY LOSS CAP" in reason or "daily" in reason.lower()


@pytest.mark.unit
def test_advisory_path_remains_when_not_enforced() -> None:
    limits = RiskLimits(sim_mode=True, daily_loss_cap=-150.0, enforce_session_guard=False)
    controller = HardRiskController(limits, enforce_rules=False)
    controller.state.daily_pnl = -2000.0
    allowed, reason = controller.check_can_trade("MES", "trending_up", 100.0)
    assert allowed is True
    assert "bypass" in reason.lower() or "learning" in reason.lower()


@pytest.mark.unit
def test_sim_mode_flag_does_not_skip_eod_force_close() -> None:
    limits = RiskLimits(
        sim_mode=True,
        enforce_session_guard=True,
        eod_force_close_minutes_before_session_end=30,
    )

    class _Guard:
        def should_force_close_eod(self, force_close_minutes: int) -> bool:
            del force_close_minutes
            return True

        def minutes_to_session_end(self) -> float:
            return 12.0

    controller = HardRiskController(limits, enforce_rules=True, session_guard=_Guard())
    should_close, reason = controller.should_force_close_eod()
    assert should_close is True
    assert "force-close" in reason
