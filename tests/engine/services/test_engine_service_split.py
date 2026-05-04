from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from lumina_core.engine.dream_state import DreamState
from lumina_core.engine.dream_state_manager import DreamStateManager
from lumina_core.engine.execution_service import ExecutionService
from lumina_core.engine.market_data_domain_service import MarketDataDomainService
from lumina_core.engine.regime_detector import RegimeDetector as EngineRegimeDetector
from lumina_core.engine.technical_analysis_service import TechnicalAnalysisService
from lumina_core.risk.orchestration import RiskOrchestrator


@pytest.mark.unit
def test_dream_state_manager_updates_and_publishes_event() -> None:
    # gegeven
    published: list[dict[str, object]] = []

    class _Bus:
        def publish_validated(self, **kwargs):
            published.append(kwargs)

    engine = SimpleNamespace(event_bus=_Bus())
    manager = DreamStateManager(engine=engine, dream_state=DreamState())

    # wanneer
    manager.set_fields({"signal": "BUY", "confluence_score": 0.91})

    # dan
    snapshot = manager.snapshot()
    assert snapshot["signal"] == "BUY"
    assert snapshot["confluence_score"] == 0.91
    assert published
    assert published[0]["topic"] == "trading_engine.dream_state.updated"


@pytest.mark.unit
def test_market_data_domain_service_generates_summary() -> None:
    # gegeven
    rows = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp("2026-01-02 10:00:00"),
                "open": 100.0,
                "high": 101.0,
                "low": 99.5,
                "close": 100.5,
                "volume": 200,
            },
            {
                "timestamp": pd.Timestamp("2026-01-02 10:01:00"),
                "open": 100.5,
                "high": 101.2,
                "low": 100.2,
                "close": 101.0,
                "volume": 220,
            },
        ]
    )
    engine = SimpleNamespace(
        market_data=SimpleNamespace(copy_ohlc=lambda: rows),
        config=SimpleNamespace(timeframes={"1min": 60}),
    )
    service = MarketDataDomainService(engine=engine)

    # wanneer
    summary = service.generate_price_action_summary()

    # dan
    assert isinstance(summary, str)
    assert summary != ""


@pytest.mark.unit
def test_technical_analysis_service_fallback_regime_sets_snapshot() -> None:
    # gegeven
    df = pd.DataFrame(
        [
            {"open": 100.0, "high": 101.0, "low": 99.8, "close": 100.7, "volume": 100},
            {"open": 100.7, "high": 101.4, "low": 100.5, "close": 101.2, "volume": 120},
            {"open": 101.2, "high": 101.3, "low": 100.6, "close": 100.8, "volume": 110},
        ]
    )
    engine = SimpleNamespace(
        config=SimpleNamespace(instrument="MES JUN26", event_threshold=0.0025),
        regime_detector=None,
        current_regime_snapshot={},
        cost_tracker={},
        get_current_dream_snapshot=lambda: {"confluence_score": 0.2},
    )
    service = TechnicalAnalysisService(engine=engine)

    # wanneer
    regime = service.detect_market_regime(df)

    # dan
    assert isinstance(regime, str)
    assert "label" in engine.current_regime_snapshot
    assert "adaptive_policy" in engine.current_regime_snapshot


@pytest.mark.unit
def test_technical_analysis_service_handles_nullable_ohlcv_with_engine_detector() -> None:
    # gegeven
    rows: list[dict[str, object]] = []
    base = pd.Timestamp("2026-05-04 19:30:00+00:00")
    for idx in range(90):
        close = 5000.0 + idx * 0.12
        rows.append(
            {
                "timestamp": (base + pd.Timedelta(minutes=idx)).isoformat(),
                "open": close - 0.1 if idx % 8 else pd.NA,
                "high": close + 0.3 if idx % 11 else pd.NA,
                "low": close - 0.3 if idx % 13 else pd.NA,
                "close": close if idx % 7 else pd.NA,
                "volume": 1000.0 + idx if idx % 9 else pd.NA,
            }
        )
    df = pd.DataFrame(rows, dtype="object")
    engine = SimpleNamespace(
        config=SimpleNamespace(instrument="MES JUN26", event_threshold=0.0025),
        regime_detector=EngineRegimeDetector(),
        current_regime_snapshot={},
        cost_tracker={},
        get_current_dream_snapshot=lambda: {"confluence_score": 0.7},
    )
    service = TechnicalAnalysisService(engine=engine)

    # wanneer
    regime = service.detect_market_regime(df)

    # dan
    assert isinstance(regime, str) and regime
    assert engine.current_regime_snapshot.get("label") == regime
    assert "adx" in dict(engine.current_regime_snapshot.get("features", {}))


@pytest.mark.unit
def test_risk_orchestrator_real_mode_under_one_contract_fails_closed() -> None:
    # gegeven
    config = SimpleNamespace(
        regime_risk_multipliers={"NEUTRAL": 1.0},
        trade_mode="real",
        max_risk_percent=0.001,
        instrument="MES",
    )
    app = SimpleNamespace(
        logger=SimpleNamespace(warning=lambda *args, **kwargs: None, info=lambda *args, **kwargs: None)
    )
    engine = SimpleNamespace(
        config=config,
        account_equity=1000.0,
        valuation_engine=SimpleNamespace(point_value_for=lambda _instrument: 50.0),
        app=app,
    )
    orchestrator = RiskOrchestrator(
        engine=engine, mode_risk_profile={"kelly_baseline": 0.25, "real_kelly_fraction": 0.25}
    )

    # wanneer
    qty = orchestrator.calculate_adaptive_risk_and_qty(
        price=5000.0, regime="NEUTRAL", stop_price=4999.0, confidence=1.0
    )

    # dan
    assert qty == 0


@pytest.mark.unit
def test_execution_service_routes_to_blackboard_or_dream_state() -> None:
    # gegeven
    proposals: list[dict[str, object]] = []

    class _Blackboard:
        def add_proposal(self, **kwargs):
            proposals.append(kwargs)

    updates_seen: list[dict[str, object]] = []
    engine = SimpleNamespace(
        blackboard=_Blackboard(),
        set_current_dream_fields=lambda payload: updates_seen.append(payload),
    )
    service = ExecutionService(engine=engine)

    # wanneer
    accepted = service.apply_rl_live_decision(
        action_payload={"signal": "BUY", "confidence": 0.9, "qty": 1, "stop": 0.0, "target": 0.0},
        current_price=5000.0,
        regime="TRENDING",
        confidence_threshold=0.78,
    )

    # dan
    assert accepted is True
    assert proposals
    assert not updates_seen
