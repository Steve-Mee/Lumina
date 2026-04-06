# CANONICAL IMPLEMENTATION – v50 Living Organism
"""Unit + chaos tests for the Lumina v50 Observability Layer.

Coverage:
  - MetricsCollector: counter, gauge, histogram, percentiles, snapshot, Prometheus text
  - NullMetricsCollector: zero-overhead no-ops
  - ObservabilityService: disabled factory, latency recording, alert firing (with
    cooldown), risk kill-switch alert, evolution proposal acceptance rate,
    model confidence drift, SQLite persistence
  - Chaos: high latency → alert fires; sequential alerts respect cooldown;
    kill-switch triggers critical alert
"""
from __future__ import annotations

import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from lumina_core.monitoring.metrics_collector import (
    MetricsCollector,
    NullMetricsCollector,
)
from lumina_core.monitoring.observability_service import (
    AlertThresholds,
    ObservabilityService,
    WebhookConfig,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def collector() -> MetricsCollector:
    return MetricsCollector()


@pytest.fixture()
def obs_enabled() -> ObservabilityService:
    """Observability service with no real webhook (url is empty)."""
    return ObservabilityService(
        collector=MetricsCollector(),
        thresholds=AlertThresholds(
            latency_ms=200.0,
            daily_loss_usd=-500.0,
            websocket_heartbeat_stale_s=30.0,
            model_confidence_drift=0.20,
            consecutive_losses=3,
        ),
        webhook=WebhookConfig(url="", enabled=False),
        flush_interval_s=3600.0,  # prevent background flush in tests
        _alert_cooldown_s=0.0,    # disable cooldown so alerts always fire
    )


@pytest.fixture()
def obs_disabled() -> ObservabilityService:
    return ObservabilityService.from_config({})


# ── MetricsCollector: counter ──────────────────────────────────────────────────


@pytest.mark.chaos_metrics
def test_counter_increments_by_one(collector: MetricsCollector) -> None:
    collector.inc("trades_total", help_="total trades")
    collector.inc("trades_total")
    assert collector.get("trades_total") == 2.0


@pytest.mark.chaos_metrics
def test_counter_increments_by_custom_amount(collector: MetricsCollector) -> None:
    collector.inc("bytes_sent", amount=512.0, help_="bytes")
    collector.inc("bytes_sent", amount=256.0)
    assert collector.get("bytes_sent") == 768.0


@pytest.mark.chaos_metrics
def test_counter_with_labels(collector: MetricsCollector) -> None:
    collector.inc("events_total", labels={"type": "chaos"}, help_="events")
    collector.inc("events_total", labels={"type": "chaos"})
    collector.inc("events_total", labels={"type": "normal"})
    assert collector.get("events_total", labels={"type": "chaos"}) == 2.0
    assert collector.get("events_total", labels={"type": "normal"}) == 1.0


# ── MetricsCollector: gauge ────────────────────────────────────────────────────


@pytest.mark.chaos_metrics
def test_gauge_set_and_overwrite(collector: MetricsCollector) -> None:
    collector.set("pnl", 100.0, help_="pnl")
    collector.set("pnl", -50.5)
    assert collector.get("pnl") == -50.5


@pytest.mark.chaos_metrics
def test_gauge_missing_key_returns_zero(collector: MetricsCollector) -> None:
    assert collector.get("nonexistent_metric") == 0.0


# ── MetricsCollector: histogram ────────────────────────────────────────────────


@pytest.mark.chaos_metrics
def test_histogram_running_mean(collector: MetricsCollector) -> None:
    for val in [10.0, 20.0, 30.0]:
        collector.observe("latency_ms", val, help_="latency")
    mean = collector.get("latency_ms")
    assert abs(mean - 20.0) < 0.01


@pytest.mark.chaos_metrics
def test_histogram_percentile_p95(collector: MetricsCollector) -> None:
    for val in range(1, 101):
        collector.observe("latency_ms", float(val), help_="latency")
    p95 = collector.get_percentile("latency_ms", 0.95)
    # 100 values: p95 index = max(0, int(100*0.95)-1) = 94 → value 95
    assert p95 == 95.0


@pytest.mark.chaos_metrics
def test_histogram_snapshot_includes_percentiles(collector: MetricsCollector) -> None:
    for val in [100.0, 200.0, 300.0, 400.0, 500.0]:
        collector.observe("lat", val, help_="lat")
    snap = collector.snapshot()
    entry = snap["lat"]
    assert "p50" in entry
    assert "p95" in entry
    assert "p99" in entry
    assert entry["count"] == 5


# ── MetricsCollector: Prometheus text ─────────────────────────────────────────


@pytest.mark.chaos_metrics
def test_prometheus_text_contains_help_and_type(collector: MetricsCollector) -> None:
    collector.set("lumina_risk_daily_pnl", -200.0, help_="Daily PnL in USD")
    text = collector.prometheus_text()
    assert "# HELP lumina_risk_daily_pnl" in text
    assert "# TYPE lumina_risk_daily_pnl gauge" in text
    assert "lumina_risk_daily_pnl -200.0" in text


@pytest.mark.chaos_metrics
def test_prometheus_text_histogram_has_bucket_lines(collector: MetricsCollector) -> None:
    for v in [10.0, 50.0, 100.0, 200.0, 300.0]:
        collector.observe("lumina_latency_ms", v, help_="latency")
    text = collector.prometheus_text()
    assert "lumina_latency_ms_count" in text
    assert "lumina_latency_ms_sum" in text
    assert "lumina_latency_ms_bucket" in text


@pytest.mark.chaos_metrics
def test_prometheus_text_labels_correct_format(collector: MetricsCollector) -> None:
    collector.inc("events", labels={"source": "inference"}, help_="events")
    text = collector.prometheus_text()
    assert 'source="inference"' in text


# ── NullMetricsCollector: zero-overhead ────────────────────────────────────────


@pytest.mark.chaos_metrics
def test_null_collector_all_writes_are_noop() -> None:
    null = NullMetricsCollector()
    null.inc("x")
    null.set("y", 1.0)
    null.observe("z", 42.0)
    assert null.get("x") == 0.0
    assert null.get("y") == 0.0
    assert null.get("z") == 0.0


@pytest.mark.chaos_metrics
def test_null_collector_snapshot_is_empty() -> None:
    null = NullMetricsCollector()
    null.inc("foo")
    assert null.snapshot() == {}


@pytest.mark.chaos_metrics
def test_null_collector_prometheus_text_is_disabled_notice() -> None:
    assert "disabled" in NullMetricsCollector().prometheus_text()


@pytest.mark.chaos_metrics
def test_null_collector_query_history_is_empty_list() -> None:
    assert NullMetricsCollector().query_history("any_metric") == []


# ── ObservabilityService: disabled factory ─────────────────────────────────────


@pytest.mark.chaos_metrics
def test_obs_disabled_uses_null_collector(obs_disabled: ObservabilityService) -> None:
    assert isinstance(obs_disabled.collector, NullMetricsCollector)


@pytest.mark.chaos_metrics
def test_obs_disabled_snapshot_is_empty(obs_disabled: ObservabilityService) -> None:
    obs_disabled.record_latency("inference", 999.0)
    snap = obs_disabled.snapshot()
    # Only _meta key is allowed (added by snapshot())
    assert all(k == "_meta" for k in snap if k not in ("_meta",))


# ── ObservabilityService: latency recording ────────────────────────────────────


@pytest.mark.chaos_metrics
@pytest.mark.chaos_metrics_latency
def test_latency_below_threshold_no_alert(obs_enabled: ObservabilityService) -> None:
    obs_enabled.record_latency("inference", 100.0)  # threshold = 200 ms
    assert obs_enabled.collector.get("lumina_alerts_sent_total") == 0.0


@pytest.mark.chaos_metrics
@pytest.mark.chaos_metrics_latency
def test_latency_above_threshold_fires_alert(obs_enabled: ObservabilityService) -> None:
    obs_enabled.record_latency("inference", 500.0)  # > 200 ms threshold
    alerts = obs_enabled.collector.get(
        "lumina_alerts_sent_total", labels={"type": "latency_inference"}
    )
    assert alerts == 1.0


@pytest.mark.chaos_metrics
@pytest.mark.chaos_metrics_latency
def test_latency_alert_cooldown_prevents_duplicate(obs_enabled: ObservabilityService) -> None:
    """Two alerts of the same type within cooldown → only one dispatched."""
    # Set a non-zero cooldown to test suppression
    object.__setattr__(obs_enabled, "_alert_cooldown_s", 60.0)
    obs_enabled.record_latency("market_data", 1000.0)
    obs_enabled.record_latency("market_data", 1000.0)
    alerts = obs_enabled.collector.get(
        "lumina_alerts_sent_total", labels={"type": "latency_market_data"}
    )
    assert alerts == 1.0  # second call suppressed by cooldown


# ── ObservabilityService: chaos – high latency spike ──────────────────────────


@pytest.mark.chaos
@pytest.mark.chaos_metrics
@pytest.mark.chaos_metrics_latency
def test_chaos_latency_spike_increments_counter(obs_enabled: ObservabilityService) -> None:
    """Simulate a latency spike (chaos scenario) and verify alert counter fires."""
    for latency_ms in [50.0, 80.0, 600.0, 750.0, 90.0]:
        obs_enabled.record_latency("reasoning", latency_ms)

    # At least 2 spikes above 200 ms → but cooldown_s = 0 so both fire
    alerts = obs_enabled.collector.get(
        "lumina_alerts_sent_total", labels={"type": "latency_reasoning"}
    )
    assert alerts >= 2.0


# ── ObservabilityService: risk controller ─────────────────────────────────────


@pytest.mark.chaos_metrics
def test_risk_daily_pnl_recorded(obs_enabled: ObservabilityService) -> None:
    obs_enabled.record_risk_status(
        daily_pnl=-200.0, kill_switch=False, consecutive_losses=1
    )
    assert obs_enabled.collector.get("lumina_risk_daily_pnl") == -200.0


@pytest.mark.chaos_metrics
def test_risk_kill_switch_fires_critical_alert(obs_enabled: ObservabilityService) -> None:
    obs_enabled.record_risk_status(
        daily_pnl=-1200.0, kill_switch=True, consecutive_losses=5
    )
    alerts = obs_enabled.collector.get(
        "lumina_alerts_sent_total", labels={"type": "kill_switch"}
    )
    assert alerts == 1.0
    assert obs_enabled.collector.get("lumina_risk_kill_switch_active") == 1.0


@pytest.mark.chaos_metrics
def test_risk_loss_threshold_fires_warning(obs_enabled: ObservabilityService) -> None:
    obs_enabled.record_risk_status(
        daily_pnl=-600.0, kill_switch=False, consecutive_losses=1
    )
    alerts = obs_enabled.collector.get(
        "lumina_alerts_sent_total", labels={"type": "daily_loss"}
    )
    assert alerts == 1.0


@pytest.mark.chaos_metrics
def test_risk_consecutive_losses_fires_alert(obs_enabled: ObservabilityService) -> None:
    obs_enabled.record_risk_status(
        daily_pnl=50.0, kill_switch=False, consecutive_losses=3
    )
    alerts = obs_enabled.collector.get(
        "lumina_alerts_sent_total", labels={"type": "consecutive_losses"}
    )
    assert alerts == 1.0


# ── ObservabilityService: evolution proposals ─────────────────────────────────


@pytest.mark.chaos_metrics
def test_evolution_acceptance_rate_computed(obs_enabled: ObservabilityService) -> None:
    obs_enabled.record_evolution_proposal(
        status="proposed", confidence=70.0, best_candidate="challenger_a"
    )
    obs_enabled.record_evolution_proposal(
        status="proposed", confidence=75.0, best_candidate="challenger_b"
    )
    obs_enabled.record_evolution_proposal(
        status="applied", confidence=90.0, best_candidate="challenger_c"
    )
    rate = obs_enabled.collector.get("lumina_evolution_acceptance_rate")
    assert abs(rate - 1 / 3) < 0.01


@pytest.mark.chaos_metrics
def test_evolution_last_confidence_updated(obs_enabled: ObservabilityService) -> None:
    obs_enabled.record_evolution_proposal(status="proposed", confidence=88.5)
    assert obs_enabled.collector.get("lumina_evolution_last_confidence") == 88.5


# ── ObservabilityService: PnL tracking ───────────────────────────────────────


@pytest.mark.chaos_metrics
def test_pnl_gauges_recorded(obs_enabled: ObservabilityService) -> None:
    obs_enabled.record_pnl(daily=450.25, unrealized=30.5, total=1200.0)
    assert obs_enabled.collector.get("lumina_pnl_daily") == 450.25
    assert obs_enabled.collector.get("lumina_pnl_unrealized") == 30.5
    assert obs_enabled.collector.get("lumina_pnl_total") == 1200.0


# ── ObservabilityService: chaos events ────────────────────────────────────────


@pytest.mark.chaos_metrics
def test_chaos_event_increments_counter(obs_enabled: ObservabilityService) -> None:
    obs_enabled.record_chaos_event("websocket_drop")
    obs_enabled.record_chaos_event("websocket_drop")
    obs_enabled.record_chaos_event("api_5xx")
    assert (
        obs_enabled.collector.get(
            "lumina_chaos_events_total", labels={"type": "websocket_drop"}
        )
        == 2.0
    )
    assert (
        obs_enabled.collector.get(
            "lumina_chaos_events_total", labels={"type": "api_5xx"}
        )
        == 1.0
    )


# ── ObservabilityService: WebSocket health ─────────────────────────────────────


@pytest.mark.chaos_metrics
def test_websocket_disconnect_fires_alert(obs_enabled: ObservabilityService) -> None:
    obs_enabled.record_websocket_status(connected=False, reconnects=2)
    assert obs_enabled.collector.get("lumina_websocket_connected") == 0.0
    alerts = obs_enabled.collector.get(
        "lumina_alerts_sent_total", labels={"type": "websocket_down"}
    )
    assert alerts == 1.0


@pytest.mark.chaos_metrics
def test_websocket_stale_heartbeat_fires_alert(obs_enabled: ObservabilityService) -> None:
    obs_enabled.record_websocket_heartbeat_age(90.0)  # threshold = 30 s
    alerts = obs_enabled.collector.get(
        "lumina_alerts_sent_total", labels={"type": "websocket_stale"}
    )
    assert alerts == 1.0


# ── ObservabilityService: model confidence drift ──────────────────────────────


@pytest.mark.chaos_metrics
def test_model_confidence_drift_alert(obs_enabled: ObservabilityService) -> None:
    """Seed a mean ~0.8, then inject 0.1 → large drift → alert fires."""
    for _ in range(10):
        obs_enabled.record_model_confidence("ollama", 0.80)
    # Inject an outlier with very different confidence
    obs_enabled.record_model_confidence("ollama", 0.10)
    alerts = obs_enabled.collector.get(
        "lumina_alerts_sent_total", labels={"type": "confidence_drift_ollama"}
    )
    assert alerts >= 1.0


@pytest.mark.chaos_metrics
def test_model_confidence_no_drift_no_alert(obs_enabled: ObservabilityService) -> None:
    for v in [0.79, 0.80, 0.81, 0.80, 0.79]:
        obs_enabled.record_model_confidence("vllm", v)
    alerts = obs_enabled.collector.get(
        "lumina_alerts_sent_total", labels={"type": "confidence_drift_vllm"}
    )
    assert alerts == 0.0


# ── SQLite persistence ────────────────────────────────────────────────────────


@pytest.mark.chaos_metrics
def test_sqlite_flush_and_query_history() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_metrics.db"
        col = MetricsCollector(db_path=db_path)
        col.set("lumina_pnl_daily", 123.45, help_="pnl")
        col.flush_to_sqlite()
        history = col.query_history("lumina_pnl_daily", limit=10)
    assert len(history) == 1
    assert abs(history[0]["value"] - 123.45) < 0.001


@pytest.mark.chaos_metrics
def test_sqlite_query_history_empty_when_no_db() -> None:
    col = MetricsCollector(db_path=None)
    col.set("x", 1.0)
    assert col.query_history("x") == []


# ── ObservabilityService: from_config factory ─────────────────────────────────


@pytest.mark.chaos_metrics
def test_from_config_enabled_creates_real_collector() -> None:
    cfg: dict[str, Any] = {
        "monitoring": {
            "enabled": True,
            "db_path": "",  # no SQLite in test
            "alert_thresholds": {"latency_ms": 300.0},
            "webhook": {"enabled": False},
        }
    }
    obs = ObservabilityService.from_config(cfg)
    assert isinstance(obs.collector, MetricsCollector)
    assert obs.thresholds.latency_ms == 300.0


@pytest.mark.chaos_metrics
def test_from_config_disabled_creates_null_collector() -> None:
    obs = ObservabilityService.from_config({"monitoring": {"enabled": False}})
    assert isinstance(obs.collector, NullMetricsCollector)


# ── Chaos CI hook ─────────────────────────────────────────────────────────────


@pytest.mark.chaos_ci_nightly
@pytest.mark.chaos_metrics
def test_chaos_ci_nightly_monitoring_smoke(obs_enabled: ObservabilityService) -> None:
    """Nightly CI: exercise every record_* path end-to-end."""
    obs_enabled.record_latency("inference", 45.0)
    obs_enabled.record_latency("market_data", 12.0)
    obs_enabled.record_risk_status(daily_pnl=320.0, kill_switch=False, consecutive_losses=0)
    obs_enabled.record_evolution_proposal(status="proposed", confidence=72.0)
    obs_enabled.record_pnl(daily=320.0, unrealized=15.0, total=4200.0)
    obs_enabled.record_chaos_event("api_timeout")
    obs_enabled.record_websocket_status(connected=True)
    obs_enabled.record_model_confidence("ollama", 0.78)
    obs_enabled.record_process_restart()

    snap = obs_enabled.snapshot()
    assert snap.get("lumina_pnl_daily", {}).get("value") == 320.0
    assert snap.get("lumina_risk_kill_switch_active", {}).get("value") == 0.0
    assert snap.get("lumina_model_confidence{agent=\"ollama\"}", {}).get("value", 0) > 0
