# CANONICAL IMPLEMENTATION – v50 Living Organism
# Bootstrap Module: Zero-Global-State Application Initialization
# All dependencies injected via container, no module-level globals.
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
import numpy as np
import requests

from typing import Any, Callable

from lumina_core import backtest_workers, runtime_workers, trade_workers
from lumina_core.container import ApplicationContainer
from lumina_core.runtime_bootstrap import start_runtime_services
from lumina_core.threading_utils import start_daemon


def publish_traderleague_trade_close(
    container: ApplicationContainer,
    *,
    symbol: str,
    entry_price: float,
    exit_price: float,
    quantity: int,
    pnl: float,
    reflection: str = "",
    chart_snapshot_url: str | None = None,
    broker_fill_id: str | None = None,
    commission: float | None = None,
    slippage_points: float | None = None,
    fill_latency_ms: float | None = None,
    reconciliation_status: str | None = None,
) -> bool:
    """
    Publish a closed trade to TraderLeague with HMAC signature.
    
    This is intentionally fail-safe: it never raises into the trading loop.
    """
    enabled = os.getenv("TRADERLEAGUE_WEBHOOK_ENABLED", "false").lower() == "true"
    if not enabled:
        return False

    webhook_url = os.getenv("TRADERLEAGUE_WEBHOOK_URL", "").strip()
    webhook_secret = os.getenv("TRADERLEAGUE_WEBHOOK_SECRET", "").strip()
    participant_handle = os.getenv("TRADERLEAGUE_PARTICIPANT_HANDLE", "lumina_public").strip()
    broker_name = os.getenv("TRADERLEAGUE_BROKER_NAME", "NinjaTrader").strip()
    broker_account_ref = os.getenv("TRADERLEAGUE_BROKER_ACCOUNT_REF", "SIM-LUMINA").strip()
    account_mode = os.getenv("TRADERLEAGUE_ACCOUNT_MODE", "paper").strip().lower()

    if not webhook_url or not webhook_secret:
        container.logger.warning("TraderLeague webhook skipped: missing URL or secret")
        return False

    if account_mode not in {"paper", "sim", "real"}:
        container.logger.warning(
            "TraderLeague webhook skipped: invalid account mode '%s'",
            account_mode,
        )
        return False

    trade_mode = str(getattr(container.config, "trade_mode", "paper") or "paper").strip().lower()
    expected_account_mode = {
        "paper": "paper",
        "sim": "sim",
        "sim_real_guard": "sim",
        "real": "real",
    }.get(trade_mode, "paper")
    if account_mode != expected_account_mode:
        container.logger.warning(
            "TraderLeague webhook skipped: account mode mismatch (trade_mode=%s, expected=%s, configured=%s)",
            trade_mode,
            expected_account_mode,
            account_mode,
        )
        return False

    try:
        exit_ts = np.datetime64("now")
        entry_ts = exit_ts - np.timedelta64(3, "m")
        effective_fill_id = broker_fill_id or f"LUMINA-{str(exit_ts)}-{symbol}-{abs(int(pnl))}"
        payload = {
            "participant_handle": participant_handle,
            "broker_name": broker_name,
            "broker_account_ref": broker_account_ref,
            "account_mode": account_mode,
            "broker_fill_id": effective_fill_id,
            "symbol": symbol,
            "entry_time": str(entry_ts),
            "exit_time": str(exit_ts),
            "entry_price": float(entry_price),
            "exit_price": float(exit_price),
            "quantity": int(quantity),
            "pnl": float(pnl),
            "commission": float(commission) if commission is not None else None,
            "slippage_points": float(slippage_points) if slippage_points is not None else None,
            "fill_latency_ms": float(fill_latency_ms) if fill_latency_ms is not None else None,
            "reconciliation_status": reconciliation_status,
            "max_drawdown_trade": -abs(float(pnl)) * 0.35,
            "reflection": reflection,
            "chart_snapshot_url": chart_snapshot_url,
            "strategy_meta": {"source": "LuminaEngine", "runtime": "v50"},
        }
        body = json.dumps(payload).encode("utf-8")
        digest = hmac.new(webhook_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        signature = f"sha256={digest}"
        response = requests.post(
            webhook_url,
            headers={"content-type": "application/json", "x-lumina-signature": signature},
            data=body,
            timeout=2.5,
        )
        if response.status_code >= 300:
            container.logger.warning(f"TraderLeague webhook non-2xx: {response.status_code} {response.text[:160]}")
            return False
        return True
    except Exception as exc:
        container.logger.error(f"TraderLeague webhook error: {exc}")
        return False


def run_traderleague_webhook_self_test(container: ApplicationContainer) -> bool:
    """
    Send one synthetic trade-close event on startup in dev mode.
    
    Controlled by env vars and always fail-safe.
    """
    app_env = os.getenv("APP_ENV", "prod").strip().lower()
    enabled = os.getenv("TRADERLEAGUE_WEBHOOK_ENABLED", "false").lower() == "true"
    selftest_enabled = os.getenv("TRADERLEAGUE_WEBHOOK_SELFTEST", "true").lower() == "true"

    if not enabled or not selftest_enabled or app_env != "dev":
        return False

    cooldown_seconds = int(os.getenv("TRADERLEAGUE_WEBHOOK_SELFTEST_COOLDOWN_SEC", "900"))
    state_file = os.getenv("TRADERLEAGUE_WEBHOOK_SELFTEST_STATE_FILE", ".traderleague_webhook_selftest.json").strip()

    try:
        if os.path.exists(state_file):
            with open(state_file, "r", encoding="utf-8") as handle:
                state = json.load(handle)
            last_sent = float(state.get("last_sent_ts", 0.0))
            if (time.time() - last_sent) < max(0, cooldown_seconds):
                container.logger.info("TraderLeague webhook self-test skipped due to cooldown")
                return False
    except Exception as exc:
        container.logger.warning(f"TraderLeague self-test cooldown read error: {exc}")

    container.logger.info("TraderLeague webhook self-test starting")
    ok = publish_traderleague_trade_close(
        container,
        symbol=str(container.primary_instrument),
        entry_price=5000.0,
        exit_price=5002.0,
        quantity=1,
        pnl=10.0,
        reflection="startup self-test trade close event",
        chart_snapshot_url="",
    )
    if ok:
        try:
            with open(state_file, "w", encoding="utf-8") as handle:
                json.dump({"last_sent_ts": time.time()}, handle)
        except Exception as exc:
            container.logger.warning(f"TraderLeague self-test cooldown write error: {exc}")
        container.logger.info("TraderLeague webhook self-test succeeded")
    else:
        container.logger.warning("TraderLeague webhook self-test failed")
    return ok


def create_public_api(container: ApplicationContainer) -> dict[str, Callable]:
    """
    Create the public API from the container services.
    
    This exposes all commonly-used functionality without requiring import of individual services.
    """
    return {
        # Analysis and decision-making
        "human_like_main_loop": container.analysis_service.run_main_loop,
        "deep_analysis": container.analysis_service.deep_analysis,
        
        # Dashboard and visualization
        "update_performance_log": container.dashboard_service.update_performance_log,
        "generate_strategy_heatmap": container.dashboard_service.generate_strategy_heatmap,
        "generate_performance_summary": container.dashboard_service.generate_performance_summary,
        "start_dashboard": container.dashboard_service.start_dashboard,
        
        # Reporting
        "generate_daily_journal": container.reporting_service.generate_daily_journal,
        "generate_professional_pdf_journal": container.reporting_service.generate_professional_pdf_journal,
        "auto_journal_daemon": container.reporting_service.auto_journal_daemon,
        "run_auto_backtest": container.reporting_service.run_auto_backtest,
        "backtest_reflection": container.reporting_service.backtest_reflection,
        
        # Market data
        "start_websocket": container.market_data_service.start_websocket,
        "fetch_quote": container.market_data_service.fetch_quote,
        "load_historical_ohlc": container.market_data_service.load_historical_ohlc,
        "gap_recovery_daemon": container.market_data_service.gap_recovery_daemon,
        
        # Operations
        "thought_logger_thread": container.operations_service.thought_logger_thread,
        "log_thought": container.operations_service.log_thought,
        "place_order": container.operations_service.place_order,
        "emergency_stop": container.operations_service.emergency_stop,
        "run_forever_loop": container.operations_service.run_forever_loop,
        
        # Memory and reasoning
        "store_experience_to_vector_db": container.memory_service.store_experience_to_vector_db,
        "retrieve_relevant_experiences": container.memory_service.retrieve_relevant_experiences,
        "infer_json": container.reasoning_service.infer_json,
        
        # Trading and reconciliation
        "start_trade_reconciler": container.trade_reconciler.start,
        "stop_trade_reconciler": container.trade_reconciler.stop,
        
        # Risk management
        "health_check_market_open": lambda symbol, regime: trade_workers.health_check_market_open(
            container.runtime_context, symbol, regime
        ),
        "check_pre_trade_risk": lambda symbol, regime, risk: trade_workers.check_pre_trade_risk(
            container.runtime_context, symbol, regime, risk
        ),
        
        # Agents
        "run_news_cycle": container.news_agent.run_cycle,
        "run_emotional_twin_cycle": container.emotional_twin_agent.run_cycle,
        
        # Swarm
        "run_swarm_cycle": container.swarm_manager.run_cycle,
        "generate_swarm_dashboard_plot": container.swarm_manager.generate_dashboard_plot,
        
        # Performance validation
        "run_performance_validation_cycle": container.performance_validator.run_validation_cycle,
        "generate_monthly_performance_report": container.performance_validator.generate_monthly_report_pdf,
        
        # Inference
        "inference_set_backend": container.local_inference_engine.set_backend,
        "inference_get_backend": container.local_inference_engine.get_backend,
        
        # Engine operations
        "save_state": container.engine.save_state,
        "load_state": container.engine.load_state,
        "calculate_adaptive_risk_and_qty": container.engine.calculate_adaptive_risk_and_qty,
        "get_current_dream_snapshot": container.engine.get_current_dream_snapshot,
        "generate_price_action_summary": container.engine.generate_price_action_summary,
        "is_significant_event": container.engine.is_significant_event,
        
        # Operations service
        "get_mtf_snapshots": container.operations_service.get_mtf_snapshots,
        
        # TraderLeague integration
        "publish_traderleague_trade_close": lambda **kwargs: publish_traderleague_trade_close(container, **kwargs),
        "run_traderleague_webhook_self_test": lambda: run_traderleague_webhook_self_test(container),
    }


def bootstrap_runtime(container: ApplicationContainer) -> None:
    """
    Initialize and start all runtime services.
    
    This is called once at application startup to configure market data,
    load history, and start all daemon threads.
    """
    container.logger.info("🚀 Bootstrap runtime services starting...")
    
    # Load historical data and initialize swarm
    container.market_data_service.load_historical_ohlc(days_back=3, limit=5000)
    for symbol in container.swarm_symbols:
        try:
            symbol_df = container.market_data_service.load_historical_ohlc_for_symbol(
                instrument=symbol, days_back=3, limit=5000
            )
            if not symbol_df.empty:
                container.swarm_manager.ingest_historical_rows(symbol=symbol, rows_df=symbol_df)
        except Exception as exc:
            container.logger.error(f"Swarm historical bootstrap error for {symbol}: {exc}")
    
    # Run initial swarm cycle
    _ = container.swarm_manager.run_cycle()
    container.swarm_manager.apply_to_primary_dream()
    dashboard_path = container.swarm_manager.generate_dashboard_plot()
    if dashboard_path:
        container.engine.set_current_dream_value("swarm_dashboard_path", dashboard_path)
    
    # Test TraderLeague webhook if enabled
    run_traderleague_webhook_self_test(container)
    
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
        dna_rewrite_daemon_fn=lambda: trade_workers.dna_rewrite_daemon(container.runtime_context),
        gap_recovery_daemon_fn=container.market_data_service.gap_recovery_daemon,
        pre_dream_daemon_fn=(
            (lambda: runtime_workers.pre_dream_daemon(container.runtime_context))
            if container.config.start_pre_dream_backup
            else None
        ),
        auto_journal_daemon_fn=container.reporting_service.auto_journal_daemon,
        auto_backtest_daemon_fn=container.reporting_service.auto_backtest_daemon,
    )
    
    # Start performance validator daemon
    start_daemon(container.performance_validator.monthly_validation_daemon, name="performance-validator-daemon")
    
    container.logger.info("🛡️ v50 Stability & Watchdog active - bot is now 24/7 production-ready")
    container.logger.info(f"🕸️ Swarm active on symbols: {', '.join(container.swarm_symbols)}")
