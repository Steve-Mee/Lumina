"""S3 invariants: supervisor closed, MES/MNQ, ADR-0055 untouched, pin closed."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.order_gatekeeper.ungated_place_block import S0_PLACE_SOURCE_ALLOWLIST
from lumina_core.research_bridge.sim_gate import S3_INSTRUMENTS, supervisor_source_blocked
from lumina_research.cycles.holdout import HOLDOUT_PIN_ISO, holdout_pin_is_closed
from lumina_research.validation.cost_calibrate import card_commission_usd


@pytest.mark.unit
def test_instruments_and_pin() -> None:
    assert S3_INSTRUMENTS == frozenset({"MES", "MNQ"})
    assert holdout_pin_is_closed() is True
    assert HOLDOUT_PIN_ISO == "2026-01-28T23:00:00Z"
    assert S0_PLACE_SOURCE_ALLOWLIST == frozenset()
    assert supervisor_source_blocked("supervisor_tick_exec.run_tick_exec") is True
    assert supervisor_source_blocked("ninjatrader.broker.submit_order") is False


@pytest.mark.unit
def test_adr0055_still_cost_ssot() -> None:
    assert card_commission_usd("MES") == pytest.approx(0.94)
    assert card_commission_usd("MNQ") == pytest.approx(0.94)
    frozen = (
        Path("lumina_core/risk/live_release.py"),
        Path("lumina_core/risk/sim_account_guard.py"),
        Path("lumina_core/risk/admission_chain.py"),
        Path("lumina_core/risk/risk_gates.py"),
        Path("lumina_research/risk_core/limits.toml"),
    )
    for path in frozen:
        assert path.is_file(), path
