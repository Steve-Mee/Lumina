"""Chaos engineering tests for Lumina v50.

These tests inject failures and validate graceful degradation behavior without
changing normal runtime behavior.
"""

from __future__ import annotations

import asyncio
from collections import deque
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import pytest
import pandas as pd

from lumina_core.reasoning.local_inference_engine import LocalInferenceEngine
from lumina_core.risk.regime_detector import RegimeDetector
from lumina_core.engine.lumina_engine import LuminaEngine
from lumina_core.engine.market_data_service import MarketDataIngestService
from lumina_core.engine.portfolio_var_allocator import PortfolioVaRAllocator
from lumina_core.reasoning.reasoning_service import ReasoningService
from lumina_core.risk.risk_controller import HardRiskController, RiskLimits
from lumina_core.risk.session_guard import SessionGuard
from lumina_core.engine.trade_reconciler import TradeReconciler
from lumina_core.engine.valuation_engine import ValuationEngine


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
            enforce_session_guard=False,
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
def market_data_service(lightweight_engine: SimpleNamespace) -> MarketDataIngestService:
    return MarketDataIngestService(engine=cast(LuminaEngine, lightweight_engine))


@pytest.fixture
def reasoning_service(lightweight_engine: SimpleNamespace) -> ReasoningService:
    return ReasoningService(engine=cast(LuminaEngine, lightweight_engine))


@pytest.mark.chaos_websocket
@pytest.mark.chaos_websocket_drop
def test_websocket_drop_is_handled(
    market_data_service: MarketDataIngestService, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*args, **kwargs):
        raise ConnectionError("simulated websocket drop")

    monkeypatch.setattr("lumina_core.engine.market_data_service.websockets.connect", _boom)
    asyncio.run(market_data_service.websocket_listener())


@pytest.mark.chaos_websocket
@pytest.mark.chaos_websocket_reconnect
def test_websocket_connect_uses_ping_timeouts(
    market_data_service: MarketDataIngestService, monkeypatch: pytest.MonkeyPatch
) -> None:
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
def test_api_5xx_storm_returns_safe_default(
    market_data_service: MarketDataIngestService, monkeypatch: pytest.MonkeyPatch
) -> None:
    response = SimpleNamespace(status_code=503, json=lambda: {"last": 9999, "volume": 1})
    monkeypatch.setattr("lumina_core.engine.market_data_service.requests.get", lambda *_, **__: response)

    price, volume = market_data_service.fetch_quote()
    assert (price, volume) == (0.0, 0)


@pytest.mark.chaos_api
@pytest.mark.chaos_api_signature_mismatch
def test_api_signature_mismatch_returns_safe_default(
    market_data_service: MarketDataIngestService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = SimpleNamespace(status_code=401, json=lambda: {})
    monkeypatch.setattr("lumina_core.engine.market_data_service.requests.get", lambda *_, **__: response)

    price, volume = market_data_service.fetch_quote()
    assert (price, volume) == (0.0, 0)


@pytest.mark.chaos_degradation
@pytest.mark.chaos_degrade_high_latency
def test_market_data_latency_breach_enables_fast_path(market_data_service: MarketDataIngestService) -> None:
    app = market_data_service.engine.app
    assert app is not None
    assert app.FAST_PATH_ONLY is False

    market_data_service._record_latency(420.0, "websocket")
    market_data_service._record_latency(410.0, "websocket")
    market_data_service._record_latency(430.0, "websocket")

    assert app.FAST_PATH_ONLY is True


@pytest.mark.chaos_degradation
@pytest.mark.chaos_degrade_recovery
def test_market_data_latency_recovery_disables_fast_path(market_data_service: MarketDataIngestService) -> None:
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
def test_inference_timeout_degrades_to_hold(
    reasoning_service: ReasoningService, monkeypatch: pytest.MonkeyPatch
) -> None:
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


@pytest.mark.chaos_risk
@pytest.mark.chaos_ci_smoke
def test_correlated_mes_nq_spike_triggers_portfolio_var_block(lightweight_engine: SimpleNamespace) -> None:
    mes = [5000.0 + i * 0.4 for i in range(70)]
    nq = [17000.0 + i * 1.0 for i in range(70)]
    for idx in range(62, 70):
        mes[idx] = mes[idx - 1] - 55.0
        nq[idx] = nq[idx - 1] - 120.0

    mes_df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-04-06T14:30:00+00:00", periods=len(mes), freq="1min"),
            "open": mes,
            "high": mes,
            "low": mes,
            "close": mes,
            "volume": [1500.0] * len(mes),
        }
    )
    nq_df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-04-06T14:30:00+00:00", periods=len(nq), freq="1min"),
            "open": nq,
            "high": nq,
            "low": nq,
            "close": nq,
            "volume": [1500.0] * len(nq),
        }
    )

    lightweight_engine.swarm = SimpleNamespace(
        nodes={
            "MES JUN26": SimpleNamespace(
                market_data=SimpleNamespace(copy_ohlc=lambda: mes_df.copy()),
                prices_rolling=deque(mes, maxlen=120),
            ),
            "NQ JUN26": SimpleNamespace(
                market_data=SimpleNamespace(copy_ohlc=lambda: nq_df.copy()),
                prices_rolling=deque(nq, maxlen=120),
            ),
        }
    )
    lightweight_engine.risk_controller.portfolio_var_allocator = PortfolioVaRAllocator(
        valuation_engine=ValuationEngine(),
        swarm_manager=lightweight_engine.swarm,
        config={
            "confidence": 0.95,
            "window_days": 30,
            "max_var_usd": 50.0,
            "max_total_open_risk": 5000.0,
            "method": "historical",
            "min_points": 20,
        },
    )
    lightweight_engine.risk_controller.state.open_risk_by_symbol = {
        "MES JUN26": 900.0,
        "NQ JUN26": 900.0,
    }

    allowed, reason = lightweight_engine.risk_controller.check_can_trade(
        symbol="MES JUN26",
        regime="VOLATILE",
        proposed_risk=500.0,
    )

    assert allowed is False
    assert "PORTFOLIO VAR breached" in reason


@pytest.mark.chaos_risk
@pytest.mark.chaos_ci_smoke
def test_session_guard_holiday_closed() -> None:
    """Holiday chaos case: CME should be closed on Christmas day."""
    guard = SessionGuard(calendar_name="CME")
    holiday_ts = datetime(2026, 12, 25, 15, 0, tzinfo=timezone.utc)

    assert guard.is_market_open(holiday_ts) is False
    assert guard.is_trading_session(holiday_ts) is False


@pytest.mark.chaos_risk
@pytest.mark.chaos_ci_smoke
def test_session_guard_rollover_window_blocks_session() -> None:
    """Rollover chaos case: daily maintenance window should be blocked."""
    guard = SessionGuard(calendar_name="CME")
    # 22:00 UTC is inside the 16:55-18:05 America/Chicago rollover range during CDT.
    rollover_ts = datetime(2026, 4, 6, 22, 0, tzinfo=timezone.utc)

    assert guard.is_rollover_window(rollover_ts) is True
    assert guard.is_trading_session(rollover_ts) is False


@pytest.mark.chaos_ci_integration
@pytest.mark.chaos_ci_smoke
def test_chaos_smoke_suite_fixture(lightweight_engine: SimpleNamespace) -> None:
    assert lightweight_engine.config.reconcile_fills is True
    assert lightweight_engine.config.reconciliation_method == "websocket"


@pytest.mark.chaos_ci_integration
@pytest.mark.chaos_ci_nightly
def test_chaos_nightly_marker_path(lightweight_engine: SimpleNamespace) -> None:
    assert lightweight_engine.config.trade_mode == "real"


@pytest.mark.chaos_degradation
@pytest.mark.chaos_regime
@pytest.mark.chaos_regime_flip
def test_regime_flip_tightens_risk_limits(lightweight_engine: SimpleNamespace) -> None:
    timestamps = pd.date_range("2026-04-06T14:30:00+00:00", periods=140, freq="1min")
    trending_rows = []
    trending_close = 5000.0
    for idx, ts in enumerate(timestamps):
        trending_close += 0.45
        trending_rows.append(
            {
                "timestamp": ts.isoformat(),
                "open": trending_close - 0.2,
                "high": trending_close + 0.4,
                "low": trending_close - 0.4,
                "close": trending_close,
                "volume": 1400.0,
                "spread": 0.25,
            }
        )

    news_rows = list(trending_rows)
    last_close = float(news_rows[-1]["close"])
    for offset in range(8):
        last_close += 6.0
        row = dict(news_rows[-8 + offset])
        row["open"] = last_close - 1.5
        row["high"] = last_close + 2.0
        row["low"] = last_close - 2.0
        row["close"] = last_close
        row["volume"] = 4200.0
        row["spread"] = 0.35
        news_rows[-8 + offset] = row

    lightweight_engine.ohlc_1min = pd.DataFrame(trending_rows)
    lightweight_engine.current_regime_snapshot = {}
    lightweight_engine.get_current_dream_snapshot = lambda: {"confluence_score": 0.92}
    lightweight_engine.regime_detector = RegimeDetector()

    reasoning = ReasoningService(
        engine=cast(LuminaEngine, lightweight_engine),
        inference_engine=cast(
            LocalInferenceEngine,
            SimpleNamespace(infer_json=lambda *args, **kwargs: {"signal": "BUY", "confidence": 0.8, "reason": "ok"}),
        ),
        regime_detector=lightweight_engine.regime_detector,
    )

    first = reasoning.refresh_regime_snapshot(structure={"bos": True})
    assert first.label == "TRENDING"
    base_limit = lightweight_engine.risk_controller.get_status()["active_limits"]["max_open_risk_per_instrument"]

    lightweight_engine.ohlc_1min = pd.DataFrame(news_rows)
    second = reasoning.refresh_regime_snapshot(structure={"bos": True, "fvg": [1]})
    tightened_limit = lightweight_engine.risk_controller.get_status()["active_limits"]["max_open_risk_per_instrument"]

    assert second.label in {"NEWS_DRIVEN", "HIGH_VOLATILITY"}
    assert second.risk_state == "HIGH_RISK"
    assert tightened_limit < base_limit
