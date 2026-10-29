from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.risk.mode_capabilities import resolve_mode_capabilities
from lumina_core.risk.orchestration import RiskOrchestrator


@pytest.mark.unit
@pytest.mark.safety_gate
def test_orchestrator_enforce_rules_follows_capabilities() -> None:
    mapping = {
        "sim": False,
        "sim_real_guard": True,
        "real": True,
        "paper": False,
    }
    for mode, expected in mapping.items():
        assert resolve_mode_capabilities(mode).risk_enforced is expected
        engine = SimpleNamespace(
            config=SimpleNamespace(
                trade_mode=mode,
                session={},
                state_dir=None,
                ninjatrader_sim_account_whitelist=("Sim101",),
            )
        )
        orch = RiskOrchestrator(engine=engine)
        orch.initialize()
        assert orch.risk_controller is not None
        assert bool(orch.risk_controller.enforce_rules) is expected


@pytest.mark.unit
def test_unknown_mode_fail_closes_enforce_rules() -> None:
    engine = SimpleNamespace(config=SimpleNamespace(trade_mode="not-a-mode", session={}, state_dir=None))
    orch = RiskOrchestrator(engine=engine)
    orch.initialize()
    assert orch.risk_controller is not None
    assert orch.risk_controller.enforce_rules is True
