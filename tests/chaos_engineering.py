"""Chaos engineering tests for Lumina v50.

These tests inject failures and validate graceful degradation behavior without
changing normal runtime behavior.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import pytest

from lumina_core.engine.LocalInferenceEngine import LocalInferenceEngine
from lumina_core.engine.lumina_engine import LuminaEngine
from lumina_core.engine.market_data_service import MarketDataService
from lumina_core.engine.reasoning_service import ReasoningService
from lumina_core.engine.risk_controller import HardRiskController, RiskLimits
from lumina_core.engine.trade_reconciler import TradeReconciler


@pytest.fixture
def mock_app() -> SimpleNamespace:
    app = SimpleNamespace()
    app.logger = MagicMock()
    app.logger.info = MagicMock()
    app.logger.warning = MagicMock()
    app.logger.error = MagicMock()
    app.FAST_PATH_ONLY = False
    app.INSTRUMENT = "MES JUN26"
    app.SWARM_SYMBOLS = ["MES JUN26", "ES JUN26"]
    app.CROSSTRADE_ACCOUNT = "test-account"
    app.CROSSTRADE_TOKEN = "test-token"
    app.TICK_PRINT_INTERVAL_SEC = 9999
    return app


@pytest.fixture
def lightweight_engine(mock_app: SimpleNamespace, tmp_path: Path) -> SimpleNamespace:
    config = SimpleNamespace(
        instrument="MES JUN26",
        swarm_symbols=["MES JUN26", "ES JUN26"],
        crosstrade_account="test-account",
        crosstrade_token="test-token",
        reconciliation_method="websocket",
        reconcile_fills=True,
        use_real_fill_for_pnl=True,
        crosstrade_fill_ws_url="wss://example.invalid/ws",
        crosstrade_fill_poll_url="https://example.invalid/fills",
        trade_mode="real",
        trade_reconciler_status_file=tmp_path / "reconcile_status.json",
        trade_reconciler_audit_log=tmp_path / "reconcile_audit.jsonl",
        agent_styles={
            "scalper": "style-a",
            "risk": "style-b",
        },
    )

    risk = HardRiskController(
        RiskLimits(
            daily_loss_cap=-1000.0,
            max_consecutive_losses=3,
            max_open_risk_per_instrument=500.0,
            max_exposure_per_regime=2000.0,
            cooldown_after_streak=30,
        ),
        enforce_rules=True,
    )

    return SimpleNamespace(
        app=mock_app,
        config=config,
        risk_controller=risk,
        pending_trade_reconciliations=[],
        trade_reconciler_status={},
        market_data=SimpleNamespace(process_quote_tick=lambda **_: None, get_tape_snapshot=lambda: {}),
    )


@pytest.fixture
def market_data_service(lightweight_engine: SimpleNamespace) -> MarketDataService:
    return MarketDataService(engine=cast(LuminaEngine, lightweight_engine))


@pytest.fixture
def reasoning_service(lightweight_engine: SimpleNamespace) -> ReasoningService:
    return ReasoningService(engine=cast(LuminaEngine, lightweight_engine))


@pytest.mark.chaos_websocket
@pytest.mark.chaos_websocket_drop
def test_websocket_drop_is_handled(market_data_service: MarketDataService, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*args, **kwargs):
        raise ConnectionError("simulated websocket drop")

    monkeypatch.setattr("lumina_core.engine.market_data_service.websockets.connect", _boom)
    asyncio.run(market_data_service.websocket_listener())


@pytest.mark.chaos_websocket
@pytest.mark.chaos_websocket_reconnect
def test_websocket_connect_uses_ping_timeouts(market_data_service: MarketDataService, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _capture(uri, **kwargs):
        captured["uri"] = uri
        captured.update(kwargs)
        raise RuntimeError("stop after capture")

    monkeypatch.setattr("lumina_core.engine.market_data_service.websockets.connect", _capture)
    asyncio.run(market_data_service.websocket_listener())

    assert captured["ping_interval"] == 20
    assert captured["ping_timeout"] == 20


@pytest.mark.chaos_api
@pytest.mark.chaos_api_5xx_storm
def test_api_5xx_storm_returns_safe_default(market_data_service: MarketDataService, monkeypatch: pytest.MonkeyPatch) -> None:
    response = SimpleNamespace(status_code=503, json=lambda: {"last": 9999, "volume": 1})
    monkeypatch.setattr("lumina_core.engine.market_data_service.requests.get", lambda *_, **__: response)

    price, volume = market_data_service.fetch_quote()
    assert (price, volume) == (0.0, 0)


@pytest.mark.chaos_api
@pytest.mark.chaos_api_signature_mismatch
def test_api_signature_mismatch_returns_safe_default(
    market_data_service: MarketDataService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = SimpleNamespace(status_code=401, json=lambda: {})
    monkeypatch.setattr("lumina_core.engine.market_data_service.requests.get", lambda *_, **__: response)

    price, volume = market_data_service.fetch_quote()
    assert (price, volume) == (0.0, 0)


@pytest.mark.chaos_degradation
@pytest.mark.chaos_degrade_high_latency
def test_market_data_latency_breach_enables_fast_path(market_data_service: MarketDataService) -> None:
    app = market_data_service.engine.app
    assert app is not None
    assert app.FAST_PATH_ONLY is False

    market_data_service._record_latency(420.0, "websocket")
    market_data_service._record_latency(410.0, "websocket")
    market_data_service._record_latency(430.0, "websocket")

    assert app.FAST_PATH_ONLY is True


@pytest.mark.chaos_degradation
@pytest.mark.chaos_degrade_recovery
def test_market_data_latency_recovery_disables_fast_path(market_data_service: MarketDataService) -> None:
    app = market_data_service.engine.app
    assert app is not None

    market_data_service._record_latency(420.0, "websocket")
    market_data_service._record_latency(420.0, "websocket")
    market_data_service._record_latency(420.0, "websocket")
    assert app.FAST_PATH_ONLY is True

    for _ in range(5):
        market_data_service._record_latency(50.0, "websocket")

    assert app.FAST_PATH_ONLY is False


@pytest.mark.chaos_inference
@pytest.mark.chaos_inference_timeout
def test_inference_timeout_degrades_to_hold(reasoning_service: ReasoningService, monkeypatch: pytest.MonkeyPatch) -> None:
    def _timeout(*args, **kwargs):
        raise TimeoutError("provider timeout")

    reasoning_service.inference_engine = cast(LocalInferenceEngine, SimpleNamespace(infer_json=_timeout))

    result = asyncio.run(
        reasoning_service.multi_agent_consensus(
            price=5000.0,
            mtf_data="flat",
            pa_summary="neutral",
            structure={"bos": False, "choch": False},
            fib_levels={"0.5": 5000.0},
        )
    )

    assert result["signal"] == "HOLD"
    assert "agent_votes" in result


@pytest.mark.chaos_inference
@pytest.mark.chaos_inference_timeout
def test_ollama_timeout_path_triggers_fast_path(reasoning_service: ReasoningService) -> None:
    app = reasoning_service.engine.app
    assert app is not None

    reasoning_service._record_latency(450.0, "ollama_timeout")
    reasoning_service._record_latency(460.0, "ollama_timeout")

    assert app.FAST_PATH_ONLY is True


@pytest.mark.chaos_inference
@pytest.mark.chaos_inference_http5xx
def test_vllm_http_5xx_like_timeout_triggers_fast_path(reasoning_service: ReasoningService) -> None:
    app = reasoning_service.engine.app
    assert app is not None

    reasoning_service._record_latency(510.0, "vllm_5xx")
    reasoning_service._record_latency(520.0, "vllm_5xx")

    assert app.FAST_PATH_ONLY is True


@pytest.mark.chaos_inference
@pytest.mark.chaos_inference_xai_rate_limit
def test_xai_timeout_triggers_fast_path(reasoning_service: ReasoningService) -> None:
    app = reasoning_service.engine.app
    assert app is not None

    reasoning_service._record_latency(700.0, "xai_timeout")
    reasoning_service._record_latency(720.0, "xai_timeout")

    assert app.FAST_PATH_ONLY is True


@pytest.mark.chaos_degradation
@pytest.mark.chaos_degrade_fast_path_only
def test_reasoning_fast_path_short_circuit(reasoning_service: ReasoningService) -> None:
    app = reasoning_service.engine.app
    assert app is not None
    setattr(app, "FAST_PATH_ONLY", True)

    result = asyncio.run(
        reasoning_service.multi_agent_consensus(
            price=5000.0,
            mtf_data="flat",
            pa_summary="neutral",
            structure={"bos": False, "choch": False},
            fib_levels={"0.5": 5000.0},
        )
    )

    assert result["signal"] == "HOLD"
    assert "Fast-path mode" in result["reason"]


@pytest.mark.chaos_degradation
@pytest.mark.chaos_integration_reasoning_sla
def test_reasoning_latency_breach_enables_fast_path(reasoning_service: ReasoningService) -> None:
    app = reasoning_service.engine.app
    assert app is not None

    reasoning_service._record_latency(600.0, "infer")
    reasoning_service._record_latency(620.0, "infer")

    assert app.FAST_PATH_ONLY is True


@pytest.mark.chaos_fills
@pytest.mark.chaos_fills_duplicate
def test_duplicate_fill_is_rejected(lightweight_engine: SimpleNamespace) -> None:
    reconciler = TradeReconciler(engine=cast(LuminaEngine, lightweight_engine))
    payload = {
        "type": "fill",
        "fillId": "fill-1",
        "instrument": "MES JUN26",
        "side": "BUY",
        "quantity": 1,
        "fillPrice": 5000.25,
        "timestamp": "2026-04-06T12:00:00Z",
    }

    first = reconciler.ingest_fill_event(payload)
    second = reconciler.ingest_fill_event(payload)

    assert first is True
    assert second is False


@pytest.mark.chaos_fills
@pytest.mark.chaos_fills_partial
def test_partial_fill_ingestion_is_accepted(lightweight_engine: SimpleNamespace) -> None:
    reconciler = TradeReconciler(engine=cast(LuminaEngine, lightweight_engine))
    payload = {
        "type": "fill",
        "fillId": "fill-partial-1",
        "instrument": "MES JUN26",
        "side": "SELL",
        "quantity": 2,
        "fillPrice": 4998.75,
        "timestamp": "2026-04-06T12:01:00Z",
    }

    assert reconciler.ingest_fill_event(payload) is True


@pytest.mark.chaos_risk
@pytest.mark.chaos_risk_kill_switch
def test_risk_controller_hard_block_under_chaos(lightweight_engine: SimpleNamespace) -> None:
    risk = lightweight_engine.risk_controller
    assert risk is not None

    risk.state.kill_switch_engaged = True
    risk.state.kill_switch_reason = "chaos cascade"

    allowed, reason = risk.check_can_trade(symbol="MES JUN26", regime="VOLATILE", proposed_risk=25.0)
    assert allowed is False
    assert "KILL SWITCH ENGAGED" in reason


@pytest.mark.chaos_risk
@pytest.mark.chaos_risk_daily_loss_cap
def test_risk_controller_daily_cap_blocks_and_engages_kill_switch(lightweight_engine: SimpleNamespace) -> None:
    risk = lightweight_engine.risk_controller
    assert risk is not None

    risk.state.daily_pnl = -1500.0
    allowed, reason = risk.check_can_trade(symbol="MES JUN26", regime="VOLATILE", proposed_risk=10.0)

    assert allowed is False
    assert "DAILY LOSS CAP" in reason
    assert risk.state.kill_switch_engaged is True


@pytest.mark.chaos_ci_integration
@pytest.mark.chaos_ci_smoke
def test_chaos_smoke_suite_fixture(lightweight_engine: SimpleNamespace) -> None:
    assert lightweight_engine.config.reconcile_fills is True
    assert lightweight_engine.config.reconciliation_method == "websocket"


@pytest.mark.chaos_ci_integration
@pytest.mark.chaos_ci_nightly
def test_chaos_nightly_marker_path(lightweight_engine: SimpleNamespace) -> None:
    assert lightweight_engine.config.trade_mode == "real"
