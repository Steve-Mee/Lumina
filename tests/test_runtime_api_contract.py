"""
Regression test for runtime module API contracts.

Ensures that critical functions exposed on lumina_runtime remain available
for validators and runtime callers.

This catches attribute errors early and prevents them from surfacing in production logs.
"""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

# Ensure module path is accessible
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def _load_runtime_module():
    module_path = Path(__file__).resolve().parents[1] / "lumina_runtime.py"
    spec = importlib.util.spec_from_file_location("lumina_runtime_api_contract", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load lumina_runtime.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _noop(*_args, **_kwargs):
    return None


def _build_runtime_container_stub() -> SimpleNamespace:
    return SimpleNamespace(
        analysis_service=SimpleNamespace(run_main_loop=_noop, deep_analysis=_noop),
        dashboard_service=SimpleNamespace(
            update_performance_log=_noop,
            generate_strategy_heatmap=_noop,
            generate_performance_summary=_noop,
            start_dashboard=_noop,
        ),
        reporting_service=SimpleNamespace(
            generate_daily_journal=_noop,
            generate_professional_pdf_journal=_noop,
            auto_journal_daemon=_noop,
            run_auto_backtest=_noop,
            backtest_reflection=_noop,
        ),
        market_data_service=SimpleNamespace(
            start_websocket=_noop,
            fetch_quote=_noop,
            load_historical_ohlc=_noop,
            gap_recovery_daemon=_noop,
        ),
        operations_service=SimpleNamespace(
            thought_logger_thread=_noop,
            log_thought=_noop,
            place_order=_noop,
            emergency_stop=_noop,
            run_forever_loop=_noop,
            get_mtf_snapshots=_noop,
        ),
        memory_service=SimpleNamespace(
            store_experience_to_vector_db=_noop,
            retrieve_relevant_experiences=_noop,
        ),
        reasoning_service=SimpleNamespace(infer_json=_noop),
        trade_reconciler=SimpleNamespace(start=_noop, stop=_noop),
        news_agent=SimpleNamespace(run_cycle=_noop),
        emotional_twin_agent=SimpleNamespace(run_cycle=_noop),
        swarm_manager=SimpleNamespace(run_cycle=_noop, generate_dashboard_plot=_noop),
        performance_validator=SimpleNamespace(run_validation_cycle=_noop, generate_monthly_report_pdf=_noop),
        local_inference_engine=SimpleNamespace(set_backend=_noop, get_backend=lambda: "ollama"),
        engine=SimpleNamespace(
            save_state=_noop,
            load_state=_noop,
            calculate_adaptive_risk_and_qty=_noop,
            get_current_dream_snapshot=_noop,
            generate_price_action_summary=_noop,
            is_significant_event=_noop,
            detect_market_regime=_noop,
        ),
        runtime_context=SimpleNamespace(),
        logger=SimpleNamespace(info=_noop, warning=_noop, error=_noop),
        swarm_symbols=["MES JUN26"],
        primary_instrument="MES JUN26",
        config=SimpleNamespace(use_human_main_loop=False),
    )


def test_runtime_module_critical_functions_exposed(monkeypatch):
    """
    Test that all critical functions are exposed on the runtime module.

    These functions are called by legacy workers, validators, and the main analysis loop.
    Missing exports cause AttributeError and degrade bot performance.
    """
    runtime_module = _load_runtime_module()
    container_stub = _build_runtime_container_stub()
    monkeypatch.setattr(runtime_module, "get_container", lambda: container_stub)

    critical_functions = [
        "get_current_dream_snapshot",  # Called by validator, runtime_workers
        "get_mtf_snapshots",  # Called by analysis_service, runtime_workers
        "generate_price_action_summary",  # Called by analysis_service
        "is_significant_event",  # Called by analysis_service
        "log_thought",  # Called by operations_service
        "detect_market_regime",  # Called by analysis_service
    ]

    for func_name in critical_functions:
        assert hasattr(runtime_module, func_name), (
            f"Runtime module missing critical function: {func_name}\n"
            f"This function is called by legacy code and must be exposed via __getattr__"
        )
        func = getattr(runtime_module, func_name)
        assert callable(func), f"Exposed {func_name} is not callable"


def test_runtime_module_services_accessible(monkeypatch):
    """
    Test that core services are accessible via the runtime module.
    """
    runtime_module = _load_runtime_module()
    container_stub = _build_runtime_container_stub()
    monkeypatch.setattr(runtime_module, "get_container", lambda: container_stub)

    critical_services = [
        "engine",
        "runtime_context",
        "logger",
        "SWARM_SYMBOLS",
        "INSTRUMENT",
    ]

    for service_name in critical_services:
        assert hasattr(runtime_module, service_name), (
            f"Runtime module missing service: {service_name}\nLegacy code depends on this being available."
        )


def test_runtime_module_no_unicode_errors_in_analysis_loop():
    """
    Test that analysis service logging uses safe (non-emoji) output.

    This is a sanity check that emoji characters have been removed from hot paths
    where they can cause UnicodeEncodeError on Windows cp1252 terminals.
    """
    from lumina_core.engine.analysis_service import AnalysisService

    # Read the source to verify emoji has been removed from critical print statements
    import inspect

    source = inspect.getsource(AnalysisService.run_main_loop)

    # These emoji characters should NOT appear in the main loop hot path
    dangerous_emoji = ["💰", "🔥", "⚡", "🟢"]
    for emoji in dangerous_emoji:
        assert emoji not in source, (
            f"Found {emoji} in AnalysisService.run_main_loop\n"
            f"This can cause UnicodeEncodeError on Windows cp1252 terminals.\n"
            f"Use logger.info() with ASCII text instead of print() with emoji."
        )


def test_runtime_workers_no_unicode_errors():
    """
    Test that runtime workers use safe logging output.
    """
    from lumina_core import runtime_workers

    import inspect

    source = inspect.getsource(runtime_workers.run_forever_loop)

    # Check for emoji in hot paths
    dangerous_emoji = ["💰"]
    for emoji in dangerous_emoji:
        assert emoji not in source, (
            f"Found {emoji} in run_forever_loop\nUse logger.info() instead of print() with emoji on Windows."
        )


def test_public_api_completeness():
    """
    Test that the bootstrap's public API includes critical engine functions.
    """
    from lumina_core.bootstrap import create_public_api

    container = _build_runtime_container_stub()
    public_api = create_public_api(cast(Any, container))

    critical_exports = [
        "get_current_dream_snapshot",
        "get_mtf_snapshots",
        "generate_price_action_summary",
        "is_significant_event",
    ]

    for export_name in critical_exports:
        assert export_name in public_api, (
            f"Public API missing export: {export_name}\nThis function is critical for the analysis loop and validators."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
