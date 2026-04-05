from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

from lumina_core.engine import DashboardService, EngineConfig, HumanAnalysisService, ReportingService
from lumina_core.engine.lumina_engine import LuminaEngine


def test_candle_building_closes_minute(engine: LuminaEngine) -> None:
    md = engine.market_data

    ts0 = datetime(2026, 1, 2, 14, 30, 5)
    ts1 = datetime(2026, 1, 2, 14, 30, 45)
    ts2 = datetime(2026, 1, 2, 14, 31, 2)

    closed0 = md.process_quote_tick(ts=ts0, price=5000.0, bid=4999.75, ask=5000.25, volume_cumulative=100)
    assert closed0 is None

    closed1 = md.process_quote_tick(ts=ts1, price=5001.0, bid=5000.75, ask=5001.25, volume_cumulative=130)
    assert closed1 is None

    closed2 = md.process_quote_tick(ts=ts2, price=5002.0, bid=5001.75, ask=5002.25, volume_cumulative=170)
    assert closed2 is not None
    assert float(closed2["open"]) == 5000.0
    assert float(closed2["close"]) == 5001.0
    assert float(closed2["high"]) >= 5001.0
    assert float(closed2["low"]) <= 5000.0
    assert int(closed2["volume"]) >= 30


@pytest.mark.integration
@pytest.mark.real_data
def test_regime_detection_with_real_mes_data(engine: LuminaEngine, real_mes_ohlc: pd.DataFrame) -> None:
    engine.ohlc_1min = real_mes_ohlc.tail(1000).copy()
    regime = engine.detect_market_regime(engine.ohlc_1min)
    assert regime in {"TRENDING", "RANGING", "VOLATILE", "BREAKOUT", "NEUTRAL", "UNKNOWN"}


def test_dream_snapshot_roundtrip(engine: LuminaEngine) -> None:
    engine.set_current_dream_fields({"signal": "BUY", "confluence_score": 0.88})
    snap1 = engine.get_current_dream_snapshot()
    assert snap1["signal"] == "BUY"
    assert snap1["confluence_score"] == 0.88

    engine.set_current_dream_value("target", 5050.5)
    snap2 = engine.get_current_dream_snapshot()
    assert snap2["target"] == 5050.5


def test_cache_validity(engine: LuminaEngine) -> None:
    svc = HumanAnalysisService(engine=engine)

    now = datetime.now()
    svc.last_deep_analysis.update(
        {
            "timestamp": now,
            "price": 5000.0,
            "regime": "TRENDING",
            "pa_hash": str(hash("pa summary"))[:12],
        }
    )

    assert svc.is_cache_valid(5000.2, "TRENDING", "pa summary") is True

    svc.last_deep_analysis["timestamp"] = now - timedelta(seconds=svc.cache_ttl_seconds + 1)
    assert svc.is_cache_valid(5000.2, "TRENDING", "pa summary") is False


@pytest.mark.integration
@pytest.mark.real_data
def test_backtest_engine_with_real_mes_data(engine: LuminaEngine, real_mes_ohlc: pd.DataFrame) -> None:
    engine.ohlc_1min = real_mes_ohlc.tail(2000).copy()

    engine.set_current_dream_fields(
        {
            "signal": "BUY",
            "confluence_score": 0.95,
            "stop": float(engine.ohlc_1min["close"].iloc[-1]) * 0.995,
            "target": float(engine.ohlc_1min["close"].iloc[-1]) * 1.005,
        }
    )

    reporting = ReportingService(engine=engine, dashboard_service=DashboardService(engine=engine))
    result = reporting.run_auto_backtest(days=3)

    assert set(result.keys()) == {"sharpe", "winrate", "maxdd", "trades", "avg_pnl"}
    assert isinstance(result["trades"], int)
    assert result["trades"] >= 0


def test_cost_tracker_updates(engine: LuminaEngine) -> None:
    before = dict(engine.cost_tracker)
    engine.update_cost_tracker_from_usage({"total_tokens": 1200}, channel="reasoning")
    engine.update_cost_tracker_from_usage({"total_tokens": 800}, channel="vision")

    assert engine.cost_tracker["reasoning_tokens"] > before["reasoning_tokens"]
    assert engine.cost_tracker["vision_tokens"] > before["vision_tokens"]
    assert engine.cost_tracker["today"] > before["today"]


def test_dashboard_service_formats_inference_status(engine: LuminaEngine) -> None:
    engine.cost_tracker.update(
        {
            "local_inference_requests": 4,
            "local_inference_latency_ms_total": 180.0,
            "local_inference_last_provider": "ollama",
            "local_inference_last_latency_ms": 38.0,
            "local_inference_failures": 1,
            "local_inference_cost_today": 0.0,
        }
    )

    lines = DashboardService._build_inference_status_lines(engine.cost_tracker)

    assert lines[0] == "Inference: ollama | avg 45.0 ms | last 38.0 ms"
    assert lines[1] == "Inference Requests: 4 | Failures: 1 | Local Cost: $0.0000"


def test_dashboard_service_includes_inference_warning_line(engine: LuminaEngine) -> None:
    engine.cost_tracker.update(
        {
            "local_inference_requests": 1,
            "local_inference_latency_ms_total": 120.0,
            "local_inference_last_provider": "ollama",
            "local_inference_last_latency_ms": 120.0,
            "local_inference_failures": 0,
            "local_inference_cost_today": 0.0,
            "local_inference_warning": "vLLM unavailable - auto-routed to fallback providers",
        }
    )

    lines = DashboardService._build_inference_status_lines(engine.cost_tracker)

    assert len(lines) == 3
    assert lines[2] == "Warning: vLLM unavailable - auto-routed to fallback providers"


def test_dashboard_service_builds_inference_provider_figure(engine: LuminaEngine) -> None:
    engine.cost_tracker.update(
        {
            "local_inference_provider_stats": {
                "ollama": {"successes": 5, "failures": 1},
                "vllm": {"successes": 2, "failures": 0},
            }
        }
    )

    fig = DashboardService._build_inference_provider_figure(engine.cost_tracker)

    assert fig.layout.title.text == "Inference Provider History"
    assert len(fig.data) == 2


@pytest.mark.parametrize(
    "profile,expected",
    [
        ("conservative", 0.82),
        ("balanced", 0.75),
        ("aggressive", 0.65),
    ],
)
def test_risk_profile_min_confluence(monkeypatch: pytest.MonkeyPatch, profile: str, expected: float) -> None:
    monkeypatch.setenv("LUMINA_RISK_PROFILE", profile)
    cfg = EngineConfig()
    assert cfg.min_confluence == expected


@pytest.mark.parametrize(
    "regime,winrate",
    [
        ("TRENDING", 0.70),
        ("RANGING", 0.55),
        ("VOLATILE", 0.50),
        ("BREAKOUT", 0.62),
        ("NEUTRAL", 0.48),
    ],
)
def test_dynamic_confluence_is_bounded(regime: str, winrate: float) -> None:
    engine = LuminaEngine(config=EngineConfig())
    score = engine.calculate_dynamic_confluence(regime, winrate)
    assert 0.55 <= score <= 0.95
