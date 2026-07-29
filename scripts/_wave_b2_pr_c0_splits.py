"""Wave B2 PR-C0 — behavior-preserving LOC splits with thin façades.

1. admin_endpoints_core → admin_endpoints_panels (+ thin AdminEndpoints)
2. backtester_engine → backtester_fills + backtester_validation (+ thin BacktesterEngine)
3. observability_service → observability_recorders (+ thin ObservabilityService)
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "lumina_core" / "engine"
CORE = ROOT / "lumina_core"
MON = ROOT / "lumina_core" / "monitoring"


def lines_of(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines(keepends=True)


def extract(lines: list[str], start: int, end: int) -> str:
    return "".join(lines[start - 1 : end])


def write(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)} ({len(text.splitlines())} lines)")


def split_admin() -> None:
    print("== admin_endpoints ==")
    src = ENGINE / "admin_endpoints_core.py"
    lines = lines_of(src)

    # Panel builders + start_dashboard (lines 48–end of class methods)
    panels_body = extract(lines, 48, len(lines))

    panels = '''"""Admin dashboard panel builders + Dash start_dashboard.

Extracted from ``admin_endpoints_core`` (Wave B2 PR-C0).
Public surface remains ``AdminEndpoints`` via the core façade.
"""
from __future__ import annotations

from typing import Any

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import threading
import time
import webbrowser
from dash import Input, Output, State, dcc, html

from lumina_core.evolution.bot_stress_choices import (
    TOOLTIP_NEURO_OHLC_NL,
    TOOLTIP_OHLC_DNA_NL,
    resolve_neuro_ohlc_stress_rollouts,
    resolve_ohlc_reality_stress_enabled,
    save_bot_stress_choices,
)
from lumina_core.evolution.parallel_reality_config import (
    format_tooltip_nl,
    recommend_parallel_realities,
    resolve_parallel_realities,
    save_parallel_realities_session,
)
from .state_visualizer import StateVisualizer


class AdminEndpointsPanelsMixin:
    """Swarm / blackboard / inference panel helpers + dashboard lifecycle."""

'''
    panels += panels_body
    write(ENGINE / "admin_endpoints_panels.py", panels)

    facade = '''"""Admin endpoints — thin façade (Wave B2 PR-C0).

Panel builders and ``start_dashboard`` live in ``admin_endpoints_panels``.
Public imports remain stable via ``admin_endpoints`` / this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .admin_endpoints_panels import AdminEndpointsPanelsMixin
from .metrics_collector import MetricsCollectorProtocol
from .state_visualizer import StateVisualizerProtocol


class AdminEndpointsProtocol(Protocol):
    visualization_service: Any | None

    def start_dashboard(self) -> None: ...


@dataclass
class AdminEndpoints(AdminEndpointsPanelsMixin):
    engine: Any
    metrics: MetricsCollectorProtocol
    visualizer: StateVisualizerProtocol
    visualization_service: Any | None = None

    def generate_strategy_heatmap(self) -> Any:
        return self.metrics.generate_strategy_heatmap()

    def generate_performance_summary(self) -> dict[str, Any]:
        return self.metrics.generate_performance_summary()


__all__ = ["AdminEndpoints", "AdminEndpointsProtocol", "AdminEndpointsPanelsMixin"]
'''
    # Re-export mixin name for discoverability without forcing callers to change.
    facade = facade.replace(
        'from .admin_endpoints_panels import AdminEndpointsPanelsMixin',
        'from .admin_endpoints_panels import AdminEndpointsPanelsMixin',
    )
    write(src, facade)


def split_backtester() -> None:
    print("== backtester_engine ==")
    src = CORE / "backtester_engine.py"
    lines = lines_of(src)

    run_single = extract(lines, 126, 278)
    regime_avg_queue_slip = extract(lines, 411, 443)
    normalize_regime = extract(lines, 445, 462)
    fill_helpers = extract(lines, 558, 578)
    order_book = extract(lines, 754, 847)

    fills = '''"""Backtester fill / slippage simulation + OrderBookReplay.

Extracted from ``backtester_engine`` (Wave B2 PR-C0).
Canonical import: ``from lumina_core.backtester_engine import OrderBookReplay``.
"""
from __future__ import annotations

import logging
import random
import statistics
from typing import Any

logger = logging.getLogger(__name__)


class BacktesterFillsMixin:
    """Single-path fill simulation helpers for ``BacktesterEngine``."""

    __slots__ = ()

'''
    fills += run_single + "\n"
    fills += regime_avg_queue_slip + "\n"
    fills += normalize_regime + "\n"
    fills += fill_helpers + "\n\n"
    fills += order_book
    write(CORE / "backtester_fills.py", fills)

    mc_wf = extract(lines, 280, 409)
    infer_bars = extract(lines, 464, 482)
    purged_cpcv = extract(lines, 621, 702)

    validation = '''"""Backtester Monte Carlo / walk-forward / purged CV helpers.

Extracted from ``backtester_engine`` (Wave B2 PR-C0).
"""
from __future__ import annotations

import logging
import random
import statistics
from datetime import datetime
from typing import Any

from lumina_core.engine.backtest.cross_validation import CombinatorialPurgedCV, PurgedWalkForwardCV

logger = logging.getLogger(__name__)


class BacktesterValidationMixin:
    """MC / WF / CPCV validation paths for ``BacktesterEngine``."""

    __slots__ = ()

'''
    validation += mc_wf + "\n"
    validation += infer_bars + "\n"
    validation += purged_cpcv
    write(CORE / "backtester_validation.py", validation)

    # Façade: header through generate_full_report, then metrics/dashboard/reality-gap
    header = extract(lines, 1, 125)
    # Rewrite imports + class bases
    facade_header = '''from __future__ import annotations

import json
import logging
import math
import random
import statistics
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

from lumina_core.runtime_context import RuntimeContext
from lumina_core.engine.valuation_engine import ValuationEngine
from lumina_core.engine.backtest.order_book import DynamicSlippageModel
from lumina_core.engine.backtest.reality_gap import RealityGapTracker
from lumina_core.backtester_fills import BacktesterFillsMixin, OrderBookReplay
from lumina_core.backtester_validation import BacktesterValidationMixin

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BacktesterEngine(BacktesterFillsMixin, BacktesterValidationMixin):
    """Realistic execution backtester with Monte Carlo and walk-forward support.

    v2 upgrades:
      - DynamicSlippageModel (ATR-based, regime-aware, time-of-day-aware)
      - PurgedWalkForwardCV  (embargo-gap CV with Sharpe consistency metrics)
      - CombinatorialPurgedCV (PBO + Deflated Sharpe Ratio)
      - RealityGapTracker    (rolling SIM/REAL divergence with RED/YELLOW/GREEN bands)

    Fill simulation: ``backtester_fills``. Validation: ``backtester_validation``.
    """

    app: RuntimeContext
    point_value: float = 5.0
    commission_per_side_points: float = 0.25
    valuation_engine: ValuationEngine = field(default_factory=ValuationEngine)
    dynamic_slippage: DynamicSlippageModel = field(default_factory=DynamicSlippageModel)
    reality_gap_tracker: RealityGapTracker = field(default_factory=RealityGapTracker)

'''
    # Keep __post_init__ through generate_full_report from original (lines 40-124)
    post_and_public = extract(lines, 40, 124)
    dashboard = extract(lines, 484, 556)
    metrics = extract(lines, 580, 619)
    reality = extract(lines, 704, 751)

    facade = facade_header + post_and_public + "\n"
    facade += dashboard + "\n"
    facade += metrics + "\n"
    facade += reality + "\n\n"
    facade += '''__all__ = ["BacktesterEngine", "OrderBookReplay", "BacktesterFillsMixin", "BacktesterValidationMixin"]
'''
    # silence unused header var
    _ = header
    write(src, facade)


def split_observability() -> None:
    print("== observability_service ==")
    src = MON / "observability_service.py"
    lines = lines_of(src)

    # Metric constants used by recorders
    constants = extract(lines, 47, 85)
    record_api = extract(lines, 216, 610)

    recorders = '''"""Observability metric recording helpers (Wave B2 PR-C0).

Canonical surface: ``ObservabilityService`` in ``observability_service``.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("lumina.observability")

'''
    recorders += constants + "\n\n"
    recorders += '''class ObservabilityRecordersMixin:
    """record_* API for ``ObservabilityService``."""

    __slots__ = ()

'''
    # record_api starts with comment line then methods — strip the section comment
    recorders += record_api
    write(MON / "observability_recorders.py", recorders)

    # Façade: module docstring + imports + config + class lifecycle/alerts
    # Keep metric constants as re-exports from recorders for public import stability
    facade = '''# CANONICAL IMPLEMENTATION – v50 Living Organism
"""Observability service for Lumina v50 – real-time metrics + webhook alerts.

Tracks every critical trading-system metric:
  • Latency per agent layer (inference, market_data, reasoning, meta_reasoning)
  • Risk Controller status (kill-switch, daily PnL, consecutive losses)
  • Self-Evolution proposals + acceptance rate
  • PnL real-time vs valuation engine
  • Chaos events (websocket drops, API errors, latency breaches)
  • WebSocket health (connected, reconnects, heartbeat age)
  • Model confidence drift per agent

Alerts are dispatched via webhook (Discord / Slack / Telegram) with a
per-alert-type cooldown so paging storms are impossible.

Integration:
    obs = ObservabilityService.from_config(yaml_config_dict)
    obs.start()                               # launches background flush thread
    obs.record_latency("inference", 45.2)
    obs.record_risk_status(daily_pnl=-150.0, kill_switch=False, consecutive_losses=1)
    obs.stop()                                # flushes remaining SQLite rows

Zero-overhead when disabled:
    If monitoring.enabled = false, from_config() returns a service backed by
    NullMetricsCollector; all record_* calls are pure no-ops.

Recording helpers: ``observability_recorders``. This module keeps lifecycle + alerts.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .metrics_collector import MetricsCollector, NullMetricsCollector
from .observability_recorders import (  # noqa: F401 — public metric name re-exports
    M_ALERTS_SENT,
    M_BLACKBOARD_DROP_TOTAL,
    M_BLACKBOARD_PUBLISH_LATENCY,
    M_BLACKBOARD_REJECT_TOTAL,
    M_BLACKBOARD_SUBSCRIPTION_ERROR_TOTAL,
    M_CHAOS_EVENTS,
    M_EVOLUTION_ACCEPTANCE_RATE,
    M_EVOLUTION_ACCEPTANCES,
    M_EVOLUTION_LAST_CONFIDENCE,
    M_EVOLUTION_PROPOSALS,
    M_LATENCY,
    M_MODE_EOD_FORCE_CLOSE_TOTAL,
    M_MODE_GUARD_BLOCK_TOTAL,
    M_MODE_PARITY_DRIFT_TOTAL,
    M_MODEL_ABSTENTION_RATE,
    M_MODEL_ABSTENTIONS,
    M_MODEL_CONFIDENCE,
    M_MODEL_DECISIONS,
    M_MODEL_DRIFT,
    M_PNL_DAILY,
    M_PNL_TOTAL,
    M_PNL_UNREALIZED,
    M_PORTFOLIO_TOTAL_OPEN_RISK_USD,
    M_PORTFOLIO_VAR_LIMIT_USD,
    M_PORTFOLIO_VAR_USD,
    M_REGIME_CONFIDENCE,
    M_REGIME_CURRENT,
    M_REGIME_HIGH_RISK_OVERRIDES,
    M_REGIME_MEAN_PNL,
    M_REGIME_WINRATE,
    M_RESTARTS,
    M_RISK_CONSEC_LOSS,
    M_RISK_DAILY_PNL,
    M_RISK_KILL_SWITCH,
    M_UPTIME,
    M_WS_CONNECTED,
    M_WS_HEARTBEAT_AGE,
    M_WS_RECONNECTS,
    ObservabilityRecordersMixin,
)

logger = logging.getLogger("lumina.observability")


@dataclass
class AlertThresholds:
    latency_ms: float = 500.0
    daily_loss_usd: float = -800.0
    websocket_heartbeat_stale_s: float = 60.0
    model_confidence_drift: float = 0.25
    consecutive_losses: int = 3


@dataclass
class WebhookConfig:
    url: str = ""
    platform: str = "discord"  # "discord" | "slack" | "telegram"
    telegram_chat_id: str = ""
    enabled: bool = True
    timeout_s: float = 5.0


@dataclass(slots=True)
class ObservabilityService(ObservabilityRecordersMixin):
    """Central observability hub – metrics, alerts, Prometheus export."""

    collector: MetricsCollector | NullMetricsCollector
    thresholds: AlertThresholds
    webhook: WebhookConfig
    flush_interval_s: float = 30.0
    _started_at: float = field(default_factory=time.time)
    _bg_thread: threading.Thread | None = field(default=None)
    _stop_event: threading.Event = field(default_factory=threading.Event)
    _alert_cooldown: dict[str, float] = field(default_factory=dict)
    _alert_cooldown_s: float = 120.0  # minimum gap between identical alerts
    _last_regime_labels: dict[str, str] | None = field(default=None)

'''
    # factories + lifecycle (130-214)
    factories_lifecycle = extract(lines, 129, 214)
    snapshot_alerts = extract(lines, 612, len(lines))

    facade += factories_lifecycle + "\n"
    facade += snapshot_alerts
    write(src, facade)


def main() -> None:
    split_admin()
    split_backtester()
    split_observability()
    print("done")


if __name__ == "__main__":
    main()
