"""
Regression test for runtime module API contracts.

Ensures that critical functions exposed on lumina_v45.1.1 remain available
for legacy workers and validator code.

This catches attribute errors early and prevents them from surfacing in production logs.
"""

import sys
from pathlib import Path

import pytest

# Ensure module path is accessible
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_runtime_module_critical_functions_exposed():
    """
    Test that all critical functions are exposed on the runtime module.
    
    These functions are called by legacy workers, validators, and the main analysis loop.
    Missing exports cause AttributeError and degrade bot performance.
    """
    import lumina_v45.1.1 as runtime_module
    
    critical_functions = [
        "get_current_dream_snapshot",    # Called by validator, runtime_workers
        "get_mtf_snapshots",              # Called by analysis_service, runtime_workers
        "generate_price_action_summary",  # Called by analysis_service
        "is_significant_event",           # Called by analysis_service
        "log_thought",                    # Called by operations_service
        "detect_market_regime",           # Called by analysis_service
    ]
    
    for func_name in critical_functions:
        assert hasattr(runtime_module, func_name), (
            f"Runtime module missing critical function: {func_name}\n"
            f"This function is called by legacy code and must be exposed via __getattr__"
        )
        func = getattr(runtime_module, func_name)
        assert callable(func), f"Exposed {func_name} is not callable"


def test_runtime_module_services_accessible():
    """
    Test that core services are accessible via the runtime module.
    """
    import lumina_v45.1.1 as runtime_module
    
    critical_services = [
        "engine",
        "runtime_context",
        "logger",
        "SWARM_SYMBOLS",
        "INSTRUMENT",
    ]
    
    for service_name in critical_services:
        assert hasattr(runtime_module, service_name), (
            f"Runtime module missing service: {service_name}\n"
            f"Legacy code depends on this being available."
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
            f"Found {emoji} in run_forever_loop\n"
            f"Use logger.info() instead of print() with emoji on Windows."
        )


def test_public_api_completeness():
    """
    Test that the bootstrap's public API includes critical engine functions.
    """
    from lumina_core.bootstrap import create_public_api
    from lumina_core.container import create_application_container
    
    container = create_application_container()
    public_api = create_public_api(container)
    
    critical_exports = [
        "get_current_dream_snapshot",
        "get_mtf_snapshots",
        "generate_price_action_summary",
        "is_significant_event",
    ]
    
    for export_name in critical_exports:
        assert export_name in public_api, (
            f"Public API missing export: {export_name}\n"
            f"This function is critical for the analysis loop and validators."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
