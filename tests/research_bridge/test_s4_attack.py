"""Attack tests for S4 fail-closed paths."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from lumina_core.engine.mode_capabilities import resolve_mode_capabilities
from lumina_core.order_gatekeeper.engine_helpers import MODES_REQUIRING_EQUITY_SNAPSHOT
from lumina_core.research_bridge.continuity_meter import measure_fixture_daily
from lumina_core.research_bridge.sim_gate import MIN_SURVIVORS, evaluate
from lumina_research.cycles.sim_plan import SIM_MIN_SURVIVORS, SIM_TARGET_SURVIVORS
from tests.research_bridge.s3_helpers import passing_context, passing_meter, survivor


@pytest.mark.unit
@pytest.mark.safety_gate
def test_min_survivors_stays_two_target_is_three() -> None:
    assert MIN_SURVIVORS == 2
    assert SIM_MIN_SURVIVORS == 2
    assert SIM_TARGET_SURVIVORS == 3
    ok, reason = evaluate(passing_context(survivors=(survivor(tag="only", family="trend"),)))
    assert ok is False
    assert reason == "survivors_insufficient"


@pytest.mark.unit
@pytest.mark.safety_gate
def test_config_yaml_not_sim_and_flatten_grace() -> None:
    text = Path("config.yaml").read_text(encoding="utf-8")
    assert "research_execution_mode: sim" not in text
    assert "research_execution_mode: shadow" in text
    assert "flatten_grace_ms: 30000" in text
    assert "flatten_grace_ms: 15000" not in text
    assert "fallback_companion: true" in text
    assert 'default_template: ""' in text
    adr = Path("docs/adr/0064-s4-sim-entry-hardening.md").read_text(encoding="utf-8")
    assert "Not B" in adr or "not b" in adr.lower()
    assert "not d" in adr.lower()
    assert "atm_strategy_template" in adr
    runbook = Path("docs/runbooks/nt8-atm-template.md").read_text(encoding="utf-8")
    assert "LuminaProtective" in runbook
    assert "1.5 × ATR" in runbook or "1.5 x ATR" in runbook or "ATR × 1.5" in runbook or "multiplier **1.5**" in runbook
    assert "ES" in runbook and "NQ" in runbook and "MES" in runbook and "MNQ" in runbook
    assert "atm_confirm_timeout_ms: 5000" in text
    assert "fill-before-ATM" in runbook or "fill-before-ATM race" in runbook


@pytest.mark.unit
@pytest.mark.safety_gate
def test_sim_requires_equity_snapshot_and_caps() -> None:
    assert "sim" in MODES_REQUIRING_EQUITY_SNAPSHOT
    assert resolve_mode_capabilities("sim").risk_enforced is True
    adr = Path("docs/adr/0064-s4-sim-entry-hardening.md").read_text(encoding="utf-8")
    assert "Accepted" in adr
    assert "NOT approved" in adr


@pytest.mark.unit
@pytest.mark.safety_gate
def test_ttd_and_power_floors_on_gate() -> None:
    report = passing_meter()
    slow = replace(report, ttd_slow_days=46.0, passed=False, reason="ttd_slow_above_floor")
    ok, reason = evaluate(passing_context(meter=slow))
    assert ok is False
    assert reason == "ttd_slow_above_floor"
    weak = replace(report, power=0.84, passed=False, reason="power_below_floor")
    ok, reason = evaluate(passing_context(meter=weak))
    assert ok is False
    assert reason == "power_below_floor"
    ok, reason = evaluate(passing_context(meter=measure_fixture_daily()))
    assert ok is True
