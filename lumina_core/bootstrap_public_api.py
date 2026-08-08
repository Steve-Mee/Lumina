"""Public API object construction for bootstrap."""
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


