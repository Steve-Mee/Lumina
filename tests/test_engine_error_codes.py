from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock
from unittest.mock import patch

from lumina_core.engine.errors import BrokerBridgeError, PolicyGateError, format_error_code
from lumina_core.engine.local_inference_engine import LocalInferenceEngine
from lumina_core.engine.lumina_engine import LuminaEngine
from lumina_core.engine.operations_service import OperationsService
from lumina_core.engine.reasoning_service import ReasoningService


def test_format_error_code_maps_typed_exceptions() -> None:
    assert format_error_code("ops_place_order", BrokerBridgeError("x")) == "OPS_PLACE_ORDER_BROKER_BRIDGE_ERROR"
    assert format_error_code("reasoning", PolicyGateError("x")) == "REASONING_POLICY_GATE_BLOCKED"


def test_operations_fetch_balance_logs_broker_error_code() -> None:
    logger = MagicMock()
    engine = SimpleNamespace(
        app=SimpleNamespace(logger=logger),
        config=SimpleNamespace(trade_mode="real", instrument="MES JUN26", thought_log=MagicMock()),
    )
    svc = OperationsService.__new__(OperationsService)
    object.__setattr__(svc, "engine", engine)
    object.__setattr__(svc, "container", SimpleNamespace(broker=None))

    ok = svc.fetch_account_balance()

    assert ok is False
    logged = str(logger.error.call_args[0][0])
    assert "OPS_BALANCE_BROKER_BRIDGE_ERROR" in logged


def test_reasoning_meta_error_logs_code_and_returns_fallback() -> None:
    logger = MagicMock()
    engine = SimpleNamespace(
        config=SimpleNamespace(instrument="MES JUN26", min_confluence=0.5, trade_mode="sim", agent_styles={}),
        app=SimpleNamespace(logger=logger, FAST_PATH_ONLY=False),
        get_current_dream_snapshot=lambda: {"confluence_score": 0.9, "regime": "NEUTRAL", "hold_until_ts": 0.0},
    )
    inference_engine = SimpleNamespace(active_provider="ollama")
    service = ReasoningService(
        engine=cast(LuminaEngine, cast(Any, engine)),
        inference_engine=cast(LocalInferenceEngine, cast(Any, inference_engine)),
        regime_detector=None,
        container=SimpleNamespace(broker=SimpleNamespace(submit_order=lambda _order: None)),
    )

    with patch.object(
        ReasoningService,
        "infer_json",
        side_effect=TimeoutError("xai timeout"),
    ):
        result = asyncio.run(
            service.meta_reasoning_and_counterfactuals(
                consensus={"signal": "BUY", "confidence": 0.8},
                price=5000.0,
                pa_summary="ok",
                past_experiences="none",
            )
        )

    assert result["meta_reasoning"] == "Meta-reasoning niet gelukt"
    logged = str(logger.error.call_args[0][0])
    assert "REASONING_META_TIMEOUT" in logged
