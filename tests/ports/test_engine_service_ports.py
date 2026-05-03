from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydantic import ValidationError

from lumina_core.ports import EngineServicePorts


def _ports_payload() -> dict[str, Any]:
    return {
        "risk": cast(
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
        "audit": cast(Any, SimpleNamespace(log_decision=lambda payload, is_real_mode=False: True)),
        "orchestration": cast(
            Any,
            SimpleNamespace(
            publish=lambda **kwargs: kwargs,
            subscribe=lambda topic, callback: "tok",
            ),
        ),
        "broker": cast(
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
        "market_data": cast(Any, SimpleNamespace(load_historical_ohlc=lambda days_back=3, limit=5000: True)),
        "execution": cast(
            Any,
            SimpleNamespace(
            apply_rl_live_decision=lambda **kwargs: True,
            update_performance_log=lambda performance_log, trade_data: None,
            ),
        ),
        "dream": cast(
            Any,
            SimpleNamespace(
            get_current_dream_snapshot=lambda: {},
            set_current_dream_fields=lambda updates: None,
            ),
        ),
        "reasoning": cast(
            Any,
            SimpleNamespace(
            infer_json=lambda payload, timeout=20, context="xai_json", max_retries=1, decision_context_id=None: {}
            ),
        ),
        "evolution": None,
    }


@pytest.mark.unit
def test_engine_service_ports_rejects_unknown_fields() -> None:
    # gegeven
    payload = _ports_payload()
    payload["unknown_field"] = "boom"

    # wanneer/dan
    with pytest.raises(ValidationError):
        EngineServicePorts(**payload)


@pytest.mark.integration
def test_engine_service_ports_accepts_typed_payload() -> None:
    # gegeven/wanneer
    ports = EngineServicePorts(**_ports_payload())

    # dan
    assert ports.risk is not None
    assert ports.audit is not None
    assert ports.experimental == {}
