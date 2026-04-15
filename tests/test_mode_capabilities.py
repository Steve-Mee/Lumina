from __future__ import annotations

import pytest

from lumina_core.engine.mode_capabilities import resolve_mode_capabilities


def test_mode_capabilities_include_sim_real_guard_with_real_like_guards() -> None:
    caps = resolve_mode_capabilities("sim_real_guard")

    assert caps.requires_live_broker is True
    assert caps.risk_enforced is True
    assert caps.session_guard_enforced is True
    assert caps.eod_force_close_enabled is True
    assert caps.reconcile_fills_enabled_default is True
    assert caps.is_learning_mode is False
    assert caps.capital_at_risk is False
    assert caps.account_mode_hint == "sim"


def test_mode_capabilities_preserve_existing_mode_contracts() -> None:
    paper = resolve_mode_capabilities("paper")
    sim = resolve_mode_capabilities("sim")
    real = resolve_mode_capabilities("real")

    assert paper.requires_live_broker is False
    assert paper.risk_enforced is False

    assert sim.requires_live_broker is True
    assert sim.risk_enforced is False
    assert sim.is_learning_mode is True

    assert real.requires_live_broker is True
    assert real.risk_enforced is True
    assert real.capital_at_risk is True


def test_mode_capabilities_reject_unknown_mode() -> None:
    with pytest.raises(ValueError, match="Unsupported trade mode"):
        resolve_mode_capabilities("sandbox")
