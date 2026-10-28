"""Capacity scale-back and Risk Core sizing reductions."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from lumina_research.evolution.regime import RegimeObservation
from lumina_research.risk_core.types import DecisionKind
from tests.research.phase4_harness import admit_signal, make_runtime


@pytest.mark.unit
def test_capacity_scales_back_over_concentration(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-c1", trial_id=1, quantity=2.0, notional=12_000.0, instrument="MES")
    admit_signal(runtime, "hyp-c2", trial_id=2, quantity=2.0, notional=12_000.0, instrument="MES")
    admit_signal(runtime, "hyp-c3", trial_id=3, quantity=2.0, notional=12_000.0, instrument="MNQ")
    changed = runtime.rebalance()
    assert changed
    for signal in runtime.registry.signals():
        assert signal.capacity_scale <= 1.0
    mes = [item for item in runtime.registry.signals() if item.instrument == "MES"]
    assert any(item.capacity_scale < 1.0 for item in mes)
    events = runtime.capacity.events()
    assert events
    assert all(item.new_scale <= item.previous_scale for item in events)


@pytest.mark.unit
def test_sizing_goes_through_risk_core_and_only_reduces(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-sz", trial_id=1, quantity=2.0, notional=10_000.0)
    now = datetime.now(timezone.utc)
    runtime.core.heartbeat(now)
    decision = runtime.sizer.propose("hyp-sz", quantity=2.0, price=5_000.0, at=now)
    assert decision.kind in {DecisionKind.APPROVED, DecisionKind.SCALED}
    assert decision.quantity <= 2.0
    runtime.registry.apply_stage("hyp-sz", "suspended")
    blocked = runtime.sizer.propose("hyp-sz", quantity=2.0, price=5_000.0, at=now)
    assert blocked.kind is DecisionKind.REJECTED
    assert blocked.reason == "monitoring_zero_weight"


@pytest.mark.unit
def test_regime_multiplier_cannot_increase(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-rg", trial_id=1, quantity=2.0, notional=10_000.0)
    action = runtime.regime.act(RegimeObservation(vol="high", trend="down"))
    assert action.size_multiplier < 1.0
    now = datetime.now(timezone.utc)
    decision = runtime.sizer.propose("hyp-rg", quantity=2.0, price=5_000.0, at=now, regime=action)
    assert decision.quantity <= 2.0 * action.size_multiplier + 1e-9
    with pytest.raises(Exception, match="switch"):
        runtime.regime.switch_strategy(RegimeObservation(vol="low", trend="up"), "other")
