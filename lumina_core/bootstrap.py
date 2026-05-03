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
from lumina_core.risk.mode_capabilities import resolve_mode_capabilities
from lumina_core.logging_utils import flush_logger_handlers
from lumina_core.runtime_bootstrap import start_runtime_services
from lumina_core.threading_utils import start_daemon

logger = logging.getLogger(__name__)


def _validate_bootstrapped_ohlc(container: ApplicationContainer) -> None:
    """Log structured quality checks on primary ``ohlc_1min`` after historical bootstrap."""
    import pandas as pd

    logger = container.logger
    df = getattr(container.engine, "ohlc_1min", None)
    rows = len(df) if df is not None else 0
    issues: list[str] = []
    span_h = 0.0
    t_first = ""
    t_last = ""

    if df is None or rows == 0:
        issues.append("primary_ohlc_empty")
    else:
        if rows < 120:
            issues.append(f"primary_rows_low:{rows}")
        if "timestamp" in df.columns:
            ts = pd.to_datetime(df["timestamp"], errors="coerce").dropna()
            if len(ts) >= 2:
                span_h = float((ts.max() - ts.min()).total_seconds() / 3600.0)
                t_first = str(ts.iloc[0])
                t_last = str(ts.iloc[-1])
                if span_h < 2.0:
                    issues.append(f"span_hours_low:{span_h:.2f}")
                if not bool(ts.is_monotonic_increasing):
                    issues.append("timestamps_not_sorted")
                dup = int(ts.duplicated().sum())
                if dup > 0:
                    issues.append(f"duplicate_timestamps:{dup}")
            elif len(ts) < 2:
                issues.append("timestamps_insufficient")
        for col in ("open", "high", "low", "close"):
            if col in df.columns and bool(df[col].isna().any()):
                issues.append(f"nan_{col}")
        if "high" in df.columns and "low" in df.columns:
            try:
                if bool((df["high"] < df["low"]).any()):
                    issues.append("high_lt_low_rows")
            except Exception:
                logging.exception("Unhandled broad exception fallback in lumina_core/bootstrap.py:66")
                issues.append("ohlc_compare_failed")
        if "volume" in df.columns:
            try:
                if bool((df["volume"] < 0).any()):
                    issues.append("negative_volume")
            except Exception:
                logger.exception("Bootstrap OHLC quality check failed during negative volume validation")

    status = "ok"
    if issues:
        status = "fail" if "primary_ohlc_empty" in issues else "degraded"

    logger.info(
        "BOOTSTRAP_OHLC_QUALITY,status=%s,primary_rows=%d,span_hours=%.2f,t_first=%s,t_last=%s,issues=%s",
        status,
        rows,
        span_h,
        (t_first[:28] if t_first else ""),
        (t_last[:28] if t_last else ""),
        ";".join(issues) if issues else "none",
    )
    if status == "fail":
        logger.error(
            "BOOTSTRAP_OHLC_QUALITY | Geen historische 1m-bars voor primair instrument — "
            "controleer CROSSTRADE_TOKEN, instrument en netwerk."
        )
    elif status == "degraded":
        logger.warning(
            "BOOTSTRAP_OHLC_QUALITY | Data geladen maar kwaliteit kan onvoldoende zijn voor RL/neuro (zie issues). "
            "Overweeg echte simulator-data, meer historie, of symbolavailability."
        )


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


def attach_runtime_app_to_module(container: ApplicationContainer, runtime_module: Any) -> None:
    """Populate bound ``__main__`` with the same API ``lumina_runtime`` exposes via ``__getattr__``.

    ``runtime_entrypoint`` binds ``sys.modules['__main__']`` as ``engine.app``; that module does not
    define legacy helpers unless we attach them here (see HumanAnalysisService, PerformanceValidator).
    """
    if getattr(runtime_module, "logger", None) is None:
        runtime_module.logger = container.logger

    api = create_public_api(container)
    for name, fn in api.items():
        setattr(runtime_module, name, fn)

    runtime_module.detect_market_regime = container.engine.detect_market_regime
    runtime_module.detect_market_structure = container.engine.detect_market_structure
    runtime_module.run_async_safely = container.engine.run_async_safely

    runtime_module.multi_agent_consensus = container.reasoning_service.multi_agent_consensus
    runtime_module.meta_reasoning_and_counterfactuals = container.reasoning_service.meta_reasoning_and_counterfactuals
    runtime_module.update_world_model = container.memory_service.update_world_model
    runtime_module.generate_multi_tf_chart = container.visualization_service.generate_multi_tf_chart

    cfg = container.config
    runtime_module.container = container
    runtime_module.engine = container.engine
    runtime_module.config = cfg
    runtime_module.CONFIG = cfg
    runtime_module.INSTRUMENT = container.primary_instrument
    runtime_module.SWARM_SYMBOLS = list(container.swarm_symbols)

    vc = container.voice_config
    runtime_module.VOICE_ENABLED = bool(vc.output_enabled or vc.input_enabled)
    runtime_module.tts_engine = container.tts_engine
    runtime_module.FAST_PATH_ONLY = False

    runtime_module.DASHBOARD_ENABLED = bool(cfg.dashboard_enabled)
    runtime_module.SCREEN_SHARE_ENABLED = bool(cfg.screen_share_enabled)
    runtime_module.CROSSTRADE_TOKEN = str(cfg.crosstrade_token or "")
    runtime_module.CROSSTRADE_ACCOUNT = str(cfg.crosstrade_account or "")

    runtime_module.blackboard = container.blackboard
    runtime_module.news_agent = container.news_agent
    runtime_module.emotional_twin_agent = container.emotional_twin_agent
    runtime_module.swarm_manager = container.swarm_manager
    runtime_module.trade_reconciler = container.trade_reconciler
    runtime_module.local_inference_engine = container.local_inference_engine


def bootstrap_runtime(container: ApplicationContainer) -> None:
    """
    Initialize and start all runtime services.

    This is called once at application startup to configure market data,
    load history, and start all daemon threads.
    """
    container.logger.info("🚀 Bootstrap runtime services starting...")
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
    )

    # Start performance validator daemon
    start_daemon(container.performance_validator.monthly_validation_daemon, name="performance-validator-daemon")

    container.logger.info("🛡️ v50 Stability & Watchdog active - bot is now 24/7 production-ready")
    container.logger.info(f"🕸️ Swarm active on symbols: {', '.join(container.swarm_symbols)}")
