"""S2 must not weaken S0/S1/D6/D8 or open live orders."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.engine.supervisor_tick_exec import run_tick_exec
from lumina_core.order_gatekeeper.ungated_place_block import (
    freeze_is_armed,
    research_execution_mode_from_mapping,
)
from lumina_core.research_bridge.horizon import HorizonRefused, require_expected_horizon_bars
from lumina_core.risk.live_release import LIVE_ACCOUNT_PATH_CLOSED_S1, admit_live_orders
from tests.research_bridge.helpers import make_runtime, sealed_candidate


class _Places:
    def __init__(self) -> None:
        self.calls = 0

    def place_order(self, *args: object, **kwargs: object) -> None:
        self.calls += 1


@pytest.mark.unit
@pytest.mark.safety_gate
def test_yaml_sim_does_not_lift_freeze() -> None:
    assert freeze_is_armed() is True
    assert research_execution_mode_from_mapping({"research_execution_mode": "sim", "mode": "sim"}) == "sim"
    assert freeze_is_armed() is True


@pytest.mark.unit
@pytest.mark.safety_gate
def test_live_path_closed_and_horizon_required() -> None:
    ok, reason = admit_live_orders(None)
    assert ok is False
    assert reason != "ok"
    assert LIVE_ACCOUNT_PATH_CLOSED_S1
    with pytest.raises(HorizonRefused):
        require_expected_horizon_bars(None)
    with pytest.raises(HorizonRefused):
        require_expected_horizon_bars(0)
    assert require_expected_horizon_bars(8) == 8
    assert require_expected_horizon_bars(20) == 20


@pytest.mark.unit
@pytest.mark.safety_gate
def test_supervisor_tick_exec_still_cannot_place() -> None:
    places = _Places()

    class _Logger:
        def warning(self, *args: object, **kwargs: object) -> None:
            return None

        def info(self, *args: object, **kwargs: object) -> None:
            return None

        def error(self, *args: object, **kwargs: object) -> None:
            return None

    class _SM:
        app = places
        engine = type("E", (), {"live_position_qty": 0})()
        valuation_engine = object()
        _logger = _Logger()

    ctx = type(
        "Ctx",
        (),
        {
            "dream_snapshot": {"confluence_score": 0.99, "regime": "NEUTRAL", "stop": 1.0},
            "signal": "BUY",
            "trade_mode": "sim",
            "min_confluence": 0.1,
            "qty_multiplier": 1.0,
            "stop_widen_multiplier": 1.0,
            "price": 5000.0,
            "cfg": {},
            "swarm_manager": None,
            "push_trader_league_trade": None,
        },
    )()
    sm = _SM()
    sm.app.calculate_adaptive_risk_and_qty = lambda *a, **k: 1  # type: ignore[attr-defined]
    sm.app.sim_position_qty = 0  # type: ignore[attr-defined]
    run_tick_exec(sm, ctx)  # type: ignore[arg-type]
    assert places.calls == 0


@pytest.mark.unit
@pytest.mark.safety_gate
def test_stale_or_lost_still_means_no_new_orders(tmp_path: Path) -> None:
    _bus, authority, runtime, _alerts, observe = make_runtime(tmp_path, healthy=False)
    intent = runtime.on_candidate(sealed_candidate(authority))
    assert intent is None
    runtime.assert_no_broker_submit()
    assert observe.calls == []


@pytest.mark.unit
def test_shadow_still_never_places(tmp_path: Path) -> None:
    _bus, authority, runtime, _alerts, _observe = make_runtime(tmp_path, healthy=True)
    intent = runtime.on_candidate(sealed_candidate(authority))
    assert intent is not None
    runtime.assert_no_broker_submit()
    assert intent.expected_horizon >= 1
