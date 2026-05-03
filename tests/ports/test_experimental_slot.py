from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from lumina_core.ports import EngineServicePorts


def _base_ports() -> EngineServicePorts:
    return EngineServicePorts(
        risk=cast(
            Any,
            SimpleNamespace(
            session_guard=None,
            risk_controller=None,
            risk_policy=None,
            final_arbitration=object(),
            mode_risk_profile={"real_kelly_fraction": 0.2},
            dynamic_kelly_estimator=object(),
            calculate_adaptive_risk_and_qty=lambda price, regime, stop_price, confidence=None: 1,
            ),
        ),
        audit=cast(Any, SimpleNamespace(log_decision=lambda payload, is_real_mode=False: True)),
        orchestration=cast(
            Any,
            SimpleNamespace(
            publish=lambda **kwargs: kwargs,
            subscribe=lambda topic, callback: "tok",
            ),
        ),
        broker=cast(
            Any,
            SimpleNamespace(
            submit_order=lambda order: None,
            get_account_info=lambda: None,
            get_positions=lambda: [],
            get_fills=lambda: [],
            connect=lambda: True,
            disconnect=lambda: None,
            ),
        ),
        market_data=cast(Any, SimpleNamespace(load_historical_ohlc=lambda days_back=3, limit=5000: True)),
        execution=cast(
            Any,
            SimpleNamespace(
            apply_rl_live_decision=lambda **kwargs: True,
            update_performance_log=lambda performance_log, trade_data: None,
            ),
        ),
        dream=cast(
            Any,
            SimpleNamespace(
            get_current_dream_snapshot=lambda: {},
            set_current_dream_fields=lambda updates: None,
            ),
        ),
    )


@pytest.mark.unit
def test_experimental_slot_accepts_emergent_capability_without_engine_changes() -> None:
    # gegeven
    ports = _base_ports()

    # wanneer
    ports.experimental["quantum_strategy_port"] = SimpleNamespace(run=lambda: "ok")

    # dan
    assert "quantum_strategy_port" in ports.experimental
    assert ports.experimental["quantum_strategy_port"].run() == "ok"
