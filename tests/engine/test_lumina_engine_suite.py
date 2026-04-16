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


def test_state_snapshot_contexts_are_structured(engine: LuminaEngine) -> None:
    engine.live_quotes = [{"last": 5001.0}, {"last": 5002.0}]
    engine.current_candle = {"open": 5000.0, "close": 5002.0}
    engine.candle_start_ts = 12345.678
    engine.sim_position_qty = 1
    engine.live_position_qty = 2
    engine.last_entry_price = 5000.25
    engine.live_trade_signal = "BUY"
    engine.account_equity = 51234.56
    engine.realized_pnl_today = 123.45
    engine.open_pnl = 12.3
    engine.pending_trade_reconciliations = [{"id": "r1"}, {"id": "r2"}]
    engine.set_current_dream_fields({"regime": "TRENDING", "confidence": 0.88, "chosen_strategy": "fast_path"})

    snap = engine.serialize_state_snapshot()

    assert snap["market"]["quote_count"] == 2
    assert snap["position"]["live_trade_signal"] == "BUY"
    assert snap["risk"]["pending_reconciliations"] == 2
    assert snap["agent"]["regime"] == "TRENDING"


def test_state_snapshot_serialization_is_deterministic(engine: LuminaEngine) -> None:
    engine.set_current_dream_fields({"regime": "NEUTRAL", "confidence": 0.5, "chosen_strategy": "test"})
    first = engine.serialize_state_snapshot()
    second = engine.serialize_state_snapshot()
    assert first == second


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


def test_dashboard_service_sums_mode_metric_with_labels() -> None:
    snapshot = {
        "lumina_mode_guard_block_total{mode=\"sim_real_guard\",reason=\"outside_trading_session\"}": {
            "name": "lumina_mode_guard_block_total",
            "value": 3.0,
            "labels": {"mode": "sim_real_guard", "reason": "outside_trading_session"},
        },
        "lumina_mode_guard_block_total{mode=\"sim_real_guard\",reason=\"risk_daily_loss_cap\"}": {
            "name": "lumina_mode_guard_block_total",
            "value": 2.0,
            "labels": {"mode": "sim_real_guard", "reason": "risk_daily_loss_cap"},
        },
        "lumina_mode_guard_block_total{mode=\"real\",reason=\"outside_trading_session\"}": {
            "name": "lumina_mode_guard_block_total",
            "value": 9.0,
            "labels": {"mode": "real", "reason": "outside_trading_session"},
        },
    }

    total = DashboardService._sum_metric(
        snapshot,
        "lumina_mode_guard_block_total",
        labels={"mode": "sim_real_guard"},
    )

    assert total == 5.0


def test_dashboard_service_builds_mode_parity_panel(engine: LuminaEngine) -> None:
    engine.config.trade_mode = "sim_real_guard"
    engine.trade_log = [{"signal": "BUY"}] * 9
    engine.pending_trade_reconciliations = [{"id": "r1"}, {"id": "r2"}]
    engine.trade_reconciler_status = {"last_reconciled_trade": {"status": "reconciled_fill"}}
    engine.observability_service = type(
        "_Obs",
        (),
        {
            "snapshot": staticmethod(
                lambda: {
                    "b": {
                        "name": "lumina_mode_guard_block_total",
                        "value": 1.0,
                        "labels": {"mode": "sim_real_guard", "reason": "outside_trading_session"},
                    },
                    "p": {
                        "name": "lumina_mode_parity_drift_total",
                        "value": 0.55,
                        "labels": {"baseline": "real", "candidate": "sim_real_guard"},
                    },
                    "e": {
                        "name": "lumina_mode_eod_force_close_total",
                        "value": 2.0,
                        "labels": {"mode": "sim_real_guard"},
                    },
                }
            )
        },
    )()

    panel = DashboardService(engine=engine)._build_mode_parity_panel()
    lines = [str(getattr(child, "children", "")) for child in panel.children]

    assert "Gate reject ratio" in lines[0]
    assert "Reconciliation delta (vs real baseline): 0.550" in lines[1]
    assert "Force-close count (SIM_REAL_GUARD): 2" in lines[2]
    assert "Reconciler pending: 2 | last status: reconciled_fill" in lines[3]


def test_dashboard_service_builds_blackboard_health_panel(engine: LuminaEngine) -> None:
    engine.observability_service = type(
        "_Obs",
        (),
        {
            "snapshot": staticmethod(
                lambda: {
                    "lat": {
                        "name": "lumina_blackboard_publish_latency_ms",
                        "value": 24.5,
                        "labels": {},
                    },
                    "rej": {
                        "name": "lumina_blackboard_reject_total",
                        "value": 2.0,
                        "labels": {},
                    },
                    "drop": {
                        "name": "lumina_blackboard_drop_total",
                        "value": 1.0,
                        "labels": {},
                    },
                    "sub": {
                        "name": "lumina_blackboard_subscription_error_total",
                        "value": 3.0,
                        "labels": {},
                    },
                }
            )
        },
    )()
    engine.blackboard = type(
        "_Blackboard",
        (),
        {
            "latest": staticmethod(
                lambda _topic: type(
                    "_Event",
                    (),
                    {"confidence": 0.84, "sequence": 17},
                )()
            )
        },
    )()
    engine.meta_agent_orchestrator = object()

    panel = DashboardService(engine=engine)._build_blackboard_health_panel()
    lines = [str(getattr(child, "children", "")) for child in panel.children]

    assert "Status: RED | Blackboard: enabled | Meta-Orchestrator: enabled" in lines[0]
    assert "Publish latency sum: 24.50 ms | Rejects: 2 | Drops: 1" in lines[1]
    assert "Subscriber errors: 3 | Latest execution seq: 17 | Latest conf: 0.84" in lines[2]
    assert "Reason: unauthorized or malformed events rejected" in lines[3]


def test_dashboard_service_builds_green_blackboard_health_panel(engine: LuminaEngine) -> None:
    engine.observability_service = type(
        "_Obs",
        (),
        {
            "snapshot": staticmethod(
                lambda: {
                    "lat": {
                        "name": "lumina_blackboard_publish_latency_ms",
                        "value": 24.5,
                        "labels": {},
                    },
                    "rej": {
                        "name": "lumina_blackboard_reject_total",
                        "value": 0.0,
                        "labels": {},
                    },
                    "drop": {
                        "name": "lumina_blackboard_drop_total",
                        "value": 0.0,
                        "labels": {},
                    },
                    "sub": {
                        "name": "lumina_blackboard_subscription_error_total",
                        "value": 0.0,
                        "labels": {},
                    },
                }
            )
        },
    )()
    engine.blackboard = type(
        "_Blackboard",
        (),
        {
            "latest": staticmethod(
                lambda _topic: type(
                    "_Event",
                    (),
                    {"confidence": 0.91, "sequence": 42},
                )()
            )
        },
    )()
    engine.meta_agent_orchestrator = object()

    panel = DashboardService(engine=engine)._build_blackboard_health_panel()
    lines = [str(getattr(child, "children", "")) for child in panel.children]

    assert "Status: GREEN | Blackboard: enabled | Meta-Orchestrator: enabled" in lines[0]
    assert "Reason: blackboard and orchestrator healthy" in lines[3]


def test_dashboard_service_builds_amber_blackboard_health_panel(engine: LuminaEngine) -> None:
    engine.observability_service = type(
        "_Obs",
        (),
        {
            "snapshot": staticmethod(
                lambda: {
                    "lat": {
                        "name": "lumina_blackboard_publish_latency_ms",
                        "value": 410.0,
                        "labels": {},
                    },
                    "rej": {
                        "name": "lumina_blackboard_reject_total",
                        "value": 0.0,
                        "labels": {},
                    },
                    "drop": {
                        "name": "lumina_blackboard_drop_total",
                        "value": 0.0,
                        "labels": {},
                    },
                    "sub": {
                        "name": "lumina_blackboard_subscription_error_total",
                        "value": 0.0,
                        "labels": {},
                    },
                }
            )
        },
    )()
    engine.blackboard = type(
        "_Blackboard",
        (),
        {
            "latest": staticmethod(
                lambda _topic: type(
                    "_Event",
                    (),
                    {"confidence": 0.88, "sequence": 23},
                )()
            )
        },
    )()
    engine.meta_agent_orchestrator = object()

    panel = DashboardService(engine=engine)._build_blackboard_health_panel()
    lines = [str(getattr(child, "children", "")) for child in panel.children]

    assert "Status: AMBER | Blackboard: enabled | Meta-Orchestrator: enabled" in lines[0]
    assert "Reason: publish latency above 250 ms" in lines[3]


def test_dashboard_service_builds_red_blackboard_health_panel_for_low_confidence(engine: LuminaEngine) -> None:
    engine.observability_service = type(
        "_Obs",
        (),
        {
            "snapshot": staticmethod(
                lambda: {
                    "lat": {
                        "name": "lumina_blackboard_publish_latency_ms",
                        "value": 12.0,
                        "labels": {},
                    },
                    "rej": {
                        "name": "lumina_blackboard_reject_total",
                        "value": 0.0,
                        "labels": {},
                    },
                    "drop": {
                        "name": "lumina_blackboard_drop_total",
                        "value": 0.0,
                        "labels": {},
                    },
                    "sub": {
                        "name": "lumina_blackboard_subscription_error_total",
                        "value": 0.0,
                        "labels": {},
                    },
                }
            )
        },
    )()
    engine.blackboard = type(
        "_Blackboard",
        (),
        {
            "latest": staticmethod(
                lambda _topic: type(
                    "_Event",
                    (),
                    {"confidence": 0.74, "sequence": 8},
                )()
            )
        },
    )()
    engine.meta_agent_orchestrator = object()

    panel = DashboardService(engine=engine)._build_blackboard_health_panel()
    lines = [str(getattr(child, "children", "")) for child in panel.children]

    assert "Status: RED | Blackboard: enabled | Meta-Orchestrator: enabled" in lines[0]
    assert "Reason: latest aggregate confidence below 0.80" in lines[3]


def test_dashboard_service_uses_configurable_blackboard_thresholds(engine: LuminaEngine) -> None:
    engine.config.blackboard_health_latency_amber_ms = 500.0
    engine.config.blackboard_health_latency_red_ms = 1500.0
    engine.config.blackboard_health_min_confidence = 0.70
    engine.observability_service = type(
        "_Obs",
        (),
        {
            "snapshot": staticmethod(
                lambda: {
                    "lat": {
                        "name": "lumina_blackboard_publish_latency_ms",
                        "value": 410.0,
                        "labels": {},
                    },
                    "rej": {
                        "name": "lumina_blackboard_reject_total",
                        "value": 0.0,
                        "labels": {},
                    },
                    "drop": {
                        "name": "lumina_blackboard_drop_total",
                        "value": 0.0,
                        "labels": {},
                    },
                    "sub": {
                        "name": "lumina_blackboard_subscription_error_total",
                        "value": 0.0,
                        "labels": {},
                    },
                }
            )
        },
    )()
    engine.blackboard = type(
        "_Blackboard",
        (),
        {
            "latest": staticmethod(
                lambda _topic: type(
                    "_Event",
                    (),
                    {"confidence": 0.74, "sequence": 5},
                )()
            )
        },
    )()
    engine.meta_agent_orchestrator = object()

    panel = DashboardService(engine=engine)._build_blackboard_health_panel()
    lines = [str(getattr(child, "children", "")) for child in panel.children]

    assert "Status: GREEN | Blackboard: enabled | Meta-Orchestrator: enabled" in lines[0]
    assert "Reason: blackboard and orchestrator healthy" in lines[3]


def test_dashboard_service_builds_blackboard_trend_figure(engine: LuminaEngine) -> None:
    service = DashboardService(engine=engine)
    service._record_blackboard_health_sample(
        {
            "publish_latency": 100.0,
            "reject_total": 0.0,
            "drop_total": 1.0,
            "sub_error_total": 0.0,
            "status": "AMBER",
        }
    )
    service._record_blackboard_health_sample(
        {
            "publish_latency": 60.0,
            "reject_total": 0.0,
            "drop_total": 0.0,
            "sub_error_total": 0.0,
            "status": "GREEN",
        }
    )

    fig = service._build_blackboard_health_trend_figure()

    assert fig.layout.title.text == "Blackboard Health Trend"
    assert len(fig.data) == 3
    assert list(fig.data[0].y) == [100.0, 60.0]
    assert list(fig.data[1].y) == [0.0, 0.0]
    assert list(fig.data[2].y) == [1.0, 0.0]


def test_engine_config_reads_blackboard_health_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLACKBOARD_HEALTH_LATENCY_AMBER_MS", "333")
    monkeypatch.setenv("BLACKBOARD_HEALTH_LATENCY_RED_MS", "1444")
    monkeypatch.setenv("BLACKBOARD_HEALTH_MIN_CONFIDENCE", "0.83")
    monkeypatch.setenv("BLACKBOARD_HEALTH_TREND_POINTS", "12")

    cfg = EngineConfig()

    assert cfg.blackboard_health_latency_amber_ms == 333.0
    assert cfg.blackboard_health_latency_red_ms == 1444.0
    assert cfg.blackboard_health_min_confidence == 0.83
    assert cfg.blackboard_health_trend_points == 12


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


@pytest.mark.safety_gate
def test_sim_mode_sizes_larger_than_real_for_same_inputs(
    engine: LuminaEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SIM should produce larger position sizing than REAL with identical market inputs."""
    engine.account_equity = 50_000.0
    engine.config.max_risk_percent = 1.0
    monkeypatch.setattr(
        type(engine.valuation_engine),
        "point_value_for",
        lambda self, _symbol: 5.0,
        raising=False,
    )
    engine.mode_risk_profile = {
        "sim_kelly_fraction": 1.0,
        "real_kelly_fraction": 0.25,
        "kelly_min_confidence": 0.65,
        "kelly_baseline": 0.25,
    }

    engine.config.trade_mode = "real"
    qty_real = engine.calculate_adaptive_risk_and_qty(
        price=5000.0,
        regime="NEUTRAL",
        stop_price=4998.0,
        confidence=0.9,
    )

    engine.config.trade_mode = "sim"
    qty_sim = engine.calculate_adaptive_risk_and_qty(
        price=5000.0,
        regime="NEUTRAL",
        stop_price=4998.0,
        confidence=0.9,
    )

    assert qty_sim > qty_real
