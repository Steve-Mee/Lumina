"""bootstrap_runtime entry orchestration."""
# CANONICAL IMPLEMENTATION – v50 Living Organism
# Bootstrap Module: Zero-Global-State Application Initialization
# All dependencies injected via container, no module-level globals.
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import sys
import time
import numpy as np
import requests

from typing import Any, Callable

from lumina_core import backtest_workers, runtime_workers, trade_workers
from lumina_core.container import ApplicationContainer
from lumina_core.risk.mode_capabilities import resolve_mode_capabilities
from lumina_core.logging_utils import flush_logger_handlers
from lumina_core.logging_utils import get_logger
from lumina_core.runtime_bootstrap import start_runtime_services
from lumina_core.threading_utils import start_daemon

logger = logging.getLogger(__name__)
bootstrap_logger = get_logger("lumina.system.bootstrap")


from lumina_core.bootstrap_ohlc import _validate_bootstrapped_ohlc
from lumina_core.bootstrap_public_api import attach_runtime_app_to_module, create_public_api
from lumina_core.bootstrap_traderleague import (
    publish_traderleague_trade_close,
    run_traderleague_webhook_self_test,
)

def bootstrap_runtime(container: ApplicationContainer) -> None:
    """
    Initialize and start all runtime services.

    This is called once at application startup to configure market data,
    load history, and start all daemon threads.
    """
    container.logger.info("🚀 Bootstrap runtime services starting...")
    bootstrap_logger.info("bootstrap.runtime.start", extra={"event_data": {"event": "bootstrap.runtime.start"}})
    previous_hook = sys.excepthook

    def _global_exception_logger(exc_type, exc_value, exc_traceback):
        bootstrap_logger.error(
            "bootstrap.unhandled_exception",
            exc_info=(exc_type, exc_value, exc_traceback),
            extra={"event_data": {"event": "bootstrap.unhandled_exception"}},
        )
        if callable(previous_hook):
            previous_hook(exc_type, exc_value, exc_traceback)

    sys.excepthook = _global_exception_logger
    _caps = resolve_mode_capabilities(str(container.config.trade_mode))
    container.logger.info(
        "RUNTIME_BOOT,"
        f"trade_mode={container.config.trade_mode},"
        f"broker_backend={container.config.broker_backend},"
        f"risk_enforced={_caps.risk_enforced},"
        f"session_guard_enforced={_caps.session_guard_enforced},"
        f"requires_live_broker={_caps.requires_live_broker},"
        f"reconcile_fills_default={_caps.reconcile_fills_enabled_default},"
        f"capital_at_risk={_caps.capital_at_risk}"
    )
    flush_logger_handlers(container.logger)

    container.logger.info(
        "BOOTSTRAP_SLA,market_data_ms=%.0f,reasoning_ms=%.0f",
        float(container.market_data_service.latency_sla_ms),
        float(container.reasoning_service.latency_sla_ms),
    )
    flush_logger_handlers(container.logger)

    # Load historical data and initialize swarm
    _primary = str(getattr(container.config, "instrument", "") or "")
    container.logger.info(f"BOOTSTRAP_HIST_LOAD_START,primary={_primary},swarm_n={len(container.swarm_symbols)}")
    flush_logger_handlers(container.logger)
    container.market_data_service.load_historical_ohlc(days_back=3, limit=5000)
    bootstrap_logger.info(
        "bootstrap.component_loaded",
        extra={"event_data": {"event": "bootstrap.component_loaded", "component": "market_data_history"}},
    )
    container.logger.info("BOOTSTRAP_HIST_LOAD_PRIMARY_DONE")
    flush_logger_handlers(container.logger)
    for symbol in container.swarm_symbols:
        try:
            container.logger.info(f"BOOTSTRAP_HIST_LOAD_SWARM,symbol={symbol}")
            flush_logger_handlers(container.logger)
            symbol_df = container.market_data_service.load_historical_ohlc_for_symbol(
                instrument=symbol, days_back=3, limit=5000
            )
            if not symbol_df.empty:
                container.swarm_manager.ingest_historical_rows(symbol=symbol, rows_df=symbol_df)
        except Exception as exc:
            container.logger.error(f"Swarm historical bootstrap error for {symbol}: {exc}")
            bootstrap_logger.error(
                "bootstrap.component_load_error",
                extra={"event_data": {"event": "bootstrap.component_load_error", "component": f"swarm:{symbol}"}},
            )
    container.logger.info("BOOTSTRAP_HIST_LOAD_SWARM_DONE")
    flush_logger_handlers(container.logger)

    _validate_bootstrapped_ohlc(container)
    flush_logger_handlers(container.logger)

    # Run initial swarm cycle
    _ = container.swarm_manager.run_cycle()
    container.swarm_manager.apply_to_primary_dream()
    dashboard_path = container.swarm_manager.generate_dashboard_plot()
    if dashboard_path:
        container.engine.set_current_dream_value("swarm_dashboard_path", dashboard_path)

    # Test TraderLeague webhook if enabled
    run_traderleague_webhook_self_test(container)

    # LIVE_FEED_* chart/daemon traces go to lumina CSV (INFO), not launcher_runtime_stderr (Streamlit).
    container.logger.info(
        "LIVE_FEED_CONFIG,log_target=logs/lumina_full_log.csv,start_pre_dream_backup=%s,"
        "screen_share_enabled=%s,note=daemon_LIVE_FEED_only_when_start_pre_dream_backup_true",
        str(bool(container.config.start_pre_dream_backup)).lower(),
        str(bool(container.config.screen_share_enabled)).lower(),
    )
    flush_logger_handlers(container.logger)

    # Start all runtime services and daemons
    start_runtime_services(
        start_daemon_fn=start_daemon,
        screen_share_enabled=container.config.screen_share_enabled,
        dashboard_enabled=container.config.dashboard_enabled,
        voice_input_enabled=container.config.voice_input_enabled,
        start_screen_share_window_fn=container.visualization_service.start_screen_share_window,
        thought_logger_thread_fn=container.operations_service.thought_logger_thread,
        start_websocket_fn=container.market_data_service.start_websocket,
        start_trade_reconciler_fn=container.trade_reconciler.start,
        auto_backtester_daemon_fn=lambda: backtest_workers.auto_backtester_daemon(container.runtime_context),
        start_dashboard_fn=container.dashboard_service.start_dashboard,
        voice_listener_thread_fn=lambda: runtime_workers.voice_listener_thread(container.runtime_context),
        supervisor_loop_fn=lambda: runtime_workers.supervisor_loop(container.runtime_context),
        state_persist_daemon_fn=lambda: runtime_workers.state_persist_daemon(container.runtime_context, 30),
        dna_rewrite_daemon_fn=lambda: trade_workers.dna_rewrite_daemon(container.runtime_context),
        gap_recovery_daemon_fn=container.market_data_service.gap_recovery_daemon,
        pre_dream_daemon_fn=(
            (lambda: runtime_workers.pre_dream_daemon(container.runtime_context))
            if container.config.start_pre_dream_backup
            else None
        ),
        auto_journal_daemon_fn=container.reporting_service.auto_journal_daemon,
        auto_backtest_daemon_fn=container.reporting_service.auto_backtest_daemon,
        enforce_birth_guard=True,  # BIRTH ENGINE 2026-05-17
    )
    bootstrap_logger.info(
        "bootstrap.component_loaded",
        extra={"event_data": {"event": "bootstrap.component_loaded", "component": "runtime_services"}},
    )

    # Start performance validator daemon
    start_daemon(container.performance_validator.monthly_validation_daemon, name="performance-validator-daemon")
    bootstrap_logger.info(
        "bootstrap.component_loaded",
        extra={"event_data": {"event": "bootstrap.component_loaded", "component": "performance_validator"}},
    )

    container.logger.info("🛡️ v50 Stability & Watchdog active - bot is now 24/7 production-ready")
    container.logger.info(f"🕸️ Swarm active on symbols: {', '.join(container.swarm_symbols)}")
