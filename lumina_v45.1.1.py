from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import atexit
import threading
import time
import warnings
import numpy as np
import pyttsx3
import requests

from dotenv import load_dotenv

from lumina_core.engine import DashboardService, EngineConfig, HumanAnalysisService, LocalInferenceEngine, MarketDataService, MemoryService, OperationsService, PerformanceValidator, ReportingService, ReasoningService, SwarmManager, TradeReconciler, VisualizationService
from lumina_agents.news_agent import NewsAgent
from lumina_core.engine.EmotionalTwinAgent import EmotionalTwinAgent
from lumina_core.engine.analysis_helpers import detect_candle_patterns as helper_detect_candle_patterns
from lumina_core.engine.lumina_engine import LuminaEngine
from lumina_core import backtest_workers, runtime_workers, trade_workers
from lumina_core.infinite_simulator import InfiniteSimulator
from lumina_core.ppo_trainer import PPOTrainer
from lumina_core.rl_environment import RLTradingEnvironment
from lumina_core.logging_utils import build_logger
from lumina_core.news_utils import resolve_news_multiplier
from lumina_core.runtime_bootstrap import start_runtime_services
from lumina_core.runtime_context import RuntimeContext
from lumina_core.threading_utils import start_daemon

with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message="aifc was removed in Python 3.13.*",
        category=DeprecationWarning,
    )
    warnings.filterwarnings(
        "ignore",
        message="'aifc' is deprecated and slated for removal in Python 3.13",
        category=DeprecationWarning,
        module="speech_recognition",
    )
    warnings.filterwarnings(
        "ignore",
        message="'audioop' is deprecated and slated for removal in Python 3.13",
        category=DeprecationWarning,
        module="speech_recognition",
    )
    import speech_recognition as sr

load_dotenv()

CONFIG = EngineConfig()
SWARM_SYMBOLS = [str(s).strip().upper() for s in CONFIG.swarm_symbols]
INSTRUMENT = str(CONFIG.instrument).strip().upper()
if INSTRUMENT not in SWARM_SYMBOLS:
    SWARM_SYMBOLS.insert(0, INSTRUMENT)
LOG_LEVEL = __import__("os").getenv("LUMINA_LOG_LEVEL", "INFO").upper()
logger = build_logger("lumina", log_level=LOG_LEVEL, file_path="logs/lumina_full_log.csv")
VOICE_ENABLED = __import__("os").getenv("VOICE_ENABLED", "True").lower() == "true"
VOICE_INPUT_ENABLED = CONFIG.voice_input_enabled
voice_recognizer = sr.Recognizer() if VOICE_INPUT_ENABLED else None


def _init_tts_engine():
    if not VOICE_ENABLED:
        return None
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 172)
        engine.setProperty("volume", 0.95)
        return engine
    except Exception as exc:
        logger.warning(f"TTS init failed, disabling voice output: {exc}")
        return None


def _shutdown_tts_engine() -> None:
    engine = globals().get("tts_engine")
    if engine is None:
        return
    try:
        # stop() is idempotent in pyttsx3; call once for deterministic cleanup.
        engine.stop()
    except Exception:
        pass
    finally:
        globals()["tts_engine"] = None


tts_engine = _init_tts_engine()
atexit.register(_shutdown_tts_engine)
resolve_news_multiplier = resolve_news_multiplier

ENGINE = LuminaEngine(CONFIG)
RUNTIME_CONTEXT = RuntimeContext(engine=ENGINE, app=sys.modules[__name__])
LOCAL_INFERENCE_ENGINE = LocalInferenceEngine(context=RUNTIME_CONTEXT)
ENGINE.local_engine = LOCAL_INFERENCE_ENGINE  # self.local_engine op LuminaEngine zelf
ANALYSIS_SERVICE = HumanAnalysisService(engine=ENGINE)
DASHBOARD_SERVICE = DashboardService(engine=ENGINE)
REPORTING_SERVICE = ReportingService(engine=ENGINE, dashboard_service=DASHBOARD_SERVICE)
VISUALIZATION_SERVICE = VisualizationService(engine=ENGINE)
MARKET_DATA_SERVICE = MarketDataService(engine=ENGINE)
MEMORY_SERVICE = MemoryService(engine=ENGINE)
REASONING_SERVICE = ReasoningService(engine=ENGINE, inference_engine=LOCAL_INFERENCE_ENGINE)
NEWS_AGENT = NewsAgent(engine=ENGINE)
OPERATIONS_SERVICE = OperationsService(engine=ENGINE)
PPO_TRAINER = PPOTrainer(engine=ENGINE)
EMOTIONAL_TWIN_AGENT = EmotionalTwinAgent(engine=ENGINE)
INFINITE_SIMULATOR = InfiniteSimulator(
    runtime=RUNTIME_CONTEXT,
    market_data_service=MARKET_DATA_SERVICE,
    ppo_trainer=PPO_TRAINER,
)
PERFORMANCE_VALIDATOR = PerformanceValidator(
    engine=ENGINE,
    market_data_service=MARKET_DATA_SERVICE,
    ppo_trainer=PPO_TRAINER,
)
ENGINE.validator = PERFORMANCE_VALIDATOR
TRADE_RECONCILER = TradeReconciler(engine=ENGINE)
atexit.register(TRADE_RECONCILER.stop)
SWARM_MANAGER = ENGINE.swarm if getattr(ENGINE, "swarm", None) is not None else SwarmManager(ENGINE)
ENGINE.swarm = SWARM_MANAGER
DASHBOARD_SERVICE.visualization_service = VISUALIZATION_SERVICE
VISUALIZATION_SERVICE.dashboard_launcher = DASHBOARD_SERVICE.start_dashboard
setattr(sys.modules[__name__], "emotional_twin_agent", EMOTIONAL_TWIN_AGENT)
setattr(sys.modules[__name__], "swarm_manager", SWARM_MANAGER)
setattr(sys.modules[__name__], "local_inference_engine", LOCAL_INFERENCE_ENGINE)
setattr(sys.modules[__name__], "news_agent", NEWS_AGENT)
setattr(sys.modules[__name__], "performance_validator", PERFORMANCE_VALIDATOR)
setattr(sys.modules[__name__], "SWARM_SYMBOLS", SWARM_SYMBOLS)
setattr(sys.modules[__name__], "INSTRUMENT", INSTRUMENT)


def validate_runtime_config() -> bool:
    if not CONFIG.crosstrade_token:
        logger.error("Config validation failed: CROSSTRADE_TOKEN ontbreekt")
        print("❌ FOUT: CROSSTRADE_TOKEN ontbreekt in .env !")
        return False
    allowed_roots = set(CONFIG.supported_swarm_roots)
    invalid = [sym for sym in SWARM_SYMBOLS if str(sym).split(" ")[0] not in allowed_roots]
    if invalid:
        logger.error(f"Config validation failed: unsupported SWARM_SYMBOLS={invalid}")
        print(f"❌ FOUT: unsupported SWARM_SYMBOLS: {invalid}")
        return False
    return True


def rate_limit_backoff() -> None:
    ENGINE.rate_limit_backoff_seconds = min(ENGINE.rate_limit_backoff_seconds + 5, 60)
    print(f"⏳ Rate-limit backoff: {ENGINE.rate_limit_backoff_seconds} seconden")
    import time

    time.sleep(ENGINE.rate_limit_backoff_seconds)


def publish_traderleague_trade_close(
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
    """Publish a closed trade to TraderLeague with HMAC signature.

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
        logger.warning("TraderLeague webhook skipped: missing URL or secret")
        return False

    if account_mode not in {"paper", "real"}:
        account_mode = "paper"

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
            "strategy_meta": {"source": "LuminaEngine", "runtime": "v45.1.1"},
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
            logger.warning(f"TraderLeague webhook non-2xx: {response.status_code} {response.text[:160]}")
            return False
        return True
    except Exception as exc:
        logger.error(f"TraderLeague webhook error: {exc}")
        return False


def run_traderleague_webhook_self_test() -> bool:
    """Send one synthetic trade-close event on startup in dev mode.

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
                logger.info("TraderLeague webhook self-test skipped due to cooldown")
                return False
    except Exception as exc:
        logger.warning(f"TraderLeague self-test cooldown read error: {exc}")

    logger.info("TraderLeague webhook self-test starting")
    ok = publish_traderleague_trade_close(
        symbol=str(INSTRUMENT),
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
            logger.warning(f"TraderLeague self-test cooldown write error: {exc}")
        logger.info("TraderLeague webhook self-test succeeded")
    else:
        logger.warning("TraderLeague webhook self-test failed")
    return ok


PUBLIC_API = {
    "human_like_main_loop": ANALYSIS_SERVICE.run_main_loop,
    "deep_analysis": ANALYSIS_SERVICE.deep_analysis,
    "update_performance_log": DASHBOARD_SERVICE.update_performance_log,
    "generate_strategy_heatmap": DASHBOARD_SERVICE.generate_strategy_heatmap,
    "generate_performance_summary": DASHBOARD_SERVICE.generate_performance_summary,
    "generate_daily_journal": REPORTING_SERVICE.generate_daily_journal,
    "generate_professional_pdf_journal": REPORTING_SERVICE.generate_professional_pdf_journal,
    "auto_journal_daemon": REPORTING_SERVICE.auto_journal_daemon,
    "run_auto_backtest": REPORTING_SERVICE.run_auto_backtest,
    "backtest_reflection": REPORTING_SERVICE.backtest_reflection,
    "auto_backtest_daemon": REPORTING_SERVICE.auto_backtest_daemon,
    "start_screen_share_window": VISUALIZATION_SERVICE.start_screen_share_window,
    "update_live_chart": VISUALIZATION_SERVICE.update_live_chart,
    "generate_multi_tf_chart": VISUALIZATION_SERVICE.generate_multi_tf_chart,
    "start_dashboard": DASHBOARD_SERVICE.start_dashboard,
    "start_websocket": MARKET_DATA_SERVICE.start_websocket,
    "websocket_listener": MARKET_DATA_SERVICE.websocket_listener,
    "fetch_quote": MARKET_DATA_SERVICE.fetch_quote,
    "load_historical_ohlc": MARKET_DATA_SERVICE.load_historical_ohlc,
    "gap_recovery_daemon": MARKET_DATA_SERVICE.gap_recovery_daemon,
    "save_state": ENGINE.save_state,
    "load_state": ENGINE.load_state,
    "calculate_adaptive_risk_and_qty": ENGINE.calculate_adaptive_risk_and_qty,
    "thought_logger_thread": OPERATIONS_SERVICE.thought_logger_thread,
    "log_thought": OPERATIONS_SERVICE.log_thought,
    "detect_swing_and_fibs": OPERATIONS_SERVICE.detect_swing_and_fibs,
    "get_mtf_snapshots": OPERATIONS_SERVICE.get_mtf_snapshots,
    "get_high_impact_news": OPERATIONS_SERVICE.get_high_impact_news,
    "speak": OPERATIONS_SERVICE.speak,
    "fetch_account_balance": OPERATIONS_SERVICE.fetch_account_balance,
    "place_order": OPERATIONS_SERVICE.place_order,
    "emergency_stop": OPERATIONS_SERVICE.emergency_stop,
    "is_market_open": OPERATIONS_SERVICE.is_market_open,
    "run_forever_loop": OPERATIONS_SERVICE.run_forever_loop,
    "store_experience_to_vector_db": MEMORY_SERVICE.store_experience_to_vector_db,
    "retrieve_relevant_experiences": MEMORY_SERVICE.retrieve_relevant_experiences,
    "update_world_model": MEMORY_SERVICE.update_world_model,
    "infer_json": REASONING_SERVICE.infer_json,
    "run_news_cycle": NEWS_AGENT.run_cycle,
    "run_performance_validation_cycle": PERFORMANCE_VALIDATOR.run_validation_cycle,
    "generate_monthly_performance_report": PERFORMANCE_VALIDATOR.generate_monthly_report_pdf,
    "multi_agent_consensus": REASONING_SERVICE.multi_agent_consensus,
    "meta_reasoning_and_counterfactuals": REASONING_SERVICE.meta_reasoning_and_counterfactuals,
    "inference_set_backend": LOCAL_INFERENCE_ENGINE.set_backend,
    "inference_get_backend": LOCAL_INFERENCE_ENGINE.get_backend,
    "inference_start_vllm_server": LOCAL_INFERENCE_ENGINE.start_vllm_server,
    "inference_stop_vllm_server": LOCAL_INFERENCE_ENGINE.stop_vllm_server,
    "rate_limit_backoff": rate_limit_backoff,
    "publish_traderleague_trade_close": publish_traderleague_trade_close,
    "push_traderleague_trade": runtime_workers._push_trader_league_trade,
    "run_traderleague_webhook_self_test": run_traderleague_webhook_self_test,
    "trade_reconciler": TRADE_RECONCILER,
    "start_trade_reconciler": TRADE_RECONCILER.start,
    "stop_trade_reconciler": TRADE_RECONCILER.stop,
    "run_trade_reconciler_self_test": TRADE_RECONCILER.run_self_test,
    "detect_market_regime": ENGINE.detect_market_regime,
    "detect_market_structure": ENGINE.detect_market_structure,
    "calculate_dynamic_confluence": ENGINE.calculate_dynamic_confluence,
    "update_cost_tracker_from_usage": ENGINE.update_cost_tracker_from_usage,
    "run_async_safely": ENGINE.run_async_safely,
    "parse_json_loose": ENGINE.parse_json_loose,
    "build_pa_signature": ENGINE.build_pa_signature,
    "is_cache_valid": ANALYSIS_SERVICE.is_cache_valid,
    "detect_candle_patterns": helper_detect_candle_patterns,
    "generate_price_action_summary": ENGINE.generate_price_action_summary,
    "train_ppo_policy": PPO_TRAINER.train,
    "train_nightly_ppo": PPO_TRAINER.train_nightly_on_infinite_simulator,
    "load_ppo_policy": PPO_TRAINER.load_policy,
    "clear_rl_policy": ENGINE.clear_rl_policy,
    "set_rl_policy": ENGINE.set_rl_policy,
    "rl_environment_cls": RLTradingEnvironment,
    "run_nightly_infinite_simulator": INFINITE_SIMULATOR.run_nightly,
    "run_emotional_twin_cycle": EMOTIONAL_TWIN_AGENT.run_cycle,
    "train_emotional_twin_nightly": EMOTIONAL_TWIN_AGENT.train_nightly,
    "run_swarm_cycle": SWARM_MANAGER.run_cycle,
    "generate_swarm_dashboard_plot": SWARM_MANAGER.generate_dashboard_plot,
}


ENGINE.load_state()
globals().update(PUBLIC_API)


def bootstrap_runtime() -> None:
    """Validate config, pre-load history, and start all runtime services."""
    if not validate_runtime_config():
        raise SystemExit(1)

    MARKET_DATA_SERVICE.load_historical_ohlc(days_back=3, limit=5000)
    for symbol in SWARM_SYMBOLS:
        try:
            symbol_df = MARKET_DATA_SERVICE.load_historical_ohlc_for_symbol(instrument=symbol, days_back=3, limit=5000)
            if not symbol_df.empty:
                SWARM_MANAGER.ingest_historical_rows(symbol=symbol, rows_df=symbol_df)
        except Exception as exc:
            logger.error(f"Swarm historical bootstrap error for {symbol}: {exc}")

    _ = SWARM_MANAGER.run_cycle()
    SWARM_MANAGER.apply_to_primary_dream()
    dashboard_path = SWARM_MANAGER.generate_dashboard_plot()
    if dashboard_path:
        ENGINE.set_current_dream_value("swarm_dashboard_path", dashboard_path)

    run_traderleague_webhook_self_test()

    start_runtime_services(
        start_daemon_fn=start_daemon,
        screen_share_enabled=CONFIG.screen_share_enabled,
        dashboard_enabled=CONFIG.dashboard_enabled,
        voice_input_enabled=CONFIG.voice_input_enabled,
        start_screen_share_window_fn=VISUALIZATION_SERVICE.start_screen_share_window,
        thought_logger_thread_fn=OPERATIONS_SERVICE.thought_logger_thread,
        start_websocket_fn=MARKET_DATA_SERVICE.start_websocket,
        start_trade_reconciler_fn=TRADE_RECONCILER.start,
        auto_backtester_daemon_fn=lambda: backtest_workers.auto_backtester_daemon(RUNTIME_CONTEXT),
        start_dashboard_fn=DASHBOARD_SERVICE.start_dashboard,
        voice_listener_thread_fn=lambda: runtime_workers.voice_listener_thread(RUNTIME_CONTEXT),
        supervisor_loop_fn=lambda: runtime_workers.supervisor_loop(RUNTIME_CONTEXT),
        dna_rewrite_daemon_fn=lambda: trade_workers.dna_rewrite_daemon(RUNTIME_CONTEXT),
        gap_recovery_daemon_fn=MARKET_DATA_SERVICE.gap_recovery_daemon,
        pre_dream_daemon_fn=(lambda: runtime_workers.pre_dream_daemon(RUNTIME_CONTEXT)) if CONFIG.start_pre_dream_backup else None,
        auto_journal_daemon_fn=REPORTING_SERVICE.auto_journal_daemon,
        auto_backtest_daemon_fn=REPORTING_SERVICE.auto_backtest_daemon,
    )

    start_daemon(PERFORMANCE_VALIDATOR.monthly_validation_daemon, name="performance-validator-daemon")

    print("🛡️ v44 Stability & Watchdog active - bot is now 24/7 production-ready")
    print(f"🕸️ Swarm active on symbols: {', '.join(SWARM_SYMBOLS)}")

human_like_main_loop = ANALYSIS_SERVICE.run_main_loop
run_forever_loop = OPERATIONS_SERVICE.run_forever_loop


def main() -> None:
    print(f"🚀 LUMINA OOP runtime gestart (Mode: {CONFIG.trade_mode.upper()})")
    bootstrap_runtime()
    if CONFIG.use_human_main_loop:
        threading.Thread(target=human_like_main_loop, daemon=True).start()
    else:
        print("ℹ️ USE_HUMAN_MAIN_LOOP=False -> human-like loop niet gestart")
    run_forever_loop()


if __name__ == "__main__":
    main()
