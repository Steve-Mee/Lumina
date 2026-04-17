# CANONICAL IMPLEMENTATION – v50 Living Organism
# Refactored: Zero Global State via Dependency Injection Container
from __future__ import annotations

import threading
import sys
from functools import lru_cache

from lumina_core.container import ApplicationContainer, create_application_container
from lumina_core.bootstrap import bootstrap_runtime, create_public_api

@lru_cache(maxsize=1)
def get_container() -> ApplicationContainer:
    """
    Get the process-wide application container.
    
    The container is created on first access and cached by the function.
    It manages all services and avoids module-level mutable singleton state.
    
    Returns:
        The initialized ApplicationContainer.
    
    Raises:
        RuntimeError: If initialization fails.
    """
    return create_application_container()


# ===== CONVENIENCE PROPERTIES =====
# These allow code that was written for the old global variables
# to work with minimal changes. They access the container behind the scenes.

def __getattr__(name: str):
    """
    Module-level __getattr__ for backward compatibility.
    
    Allows old code that does `from lumina_v45.1.1 import ENGINE` or similar
    to work by accessing the container.
    
    This is a temporary bridge; new code should use container directly.
    """
    container = get_container()
    
    # Map old global names to container attributes
    attr_map = {
        "CONFIG": "config",
        "ENGINE": "engine",
        "engine": "engine",
        "RUNTIME_CONTEXT": "runtime_context",
        "runtime_context": "runtime_context",
        "logger": "logger",
        "SWARM_SYMBOLS": "swarm_symbols",
        "INSTRUMENT": "primary_instrument",
        "LOCAL_INFERENCE_ENGINE": "local_inference_engine",
        "ANALYSIS_SERVICE": "analysis_service",
        "DASHBOARD_SERVICE": "dashboard_service",
        "REPORTING_SERVICE": "reporting_service",
        "VISUALIZATION_SERVICE": "visualization_service",
        "MARKET_DATA_SERVICE": "market_data_service",
        "MEMORY_SERVICE": "memory_service",
        "REASONING_SERVICE": "reasoning_service",
        "NEWS_AGENT": "news_agent",
        "OPERATIONS_SERVICE": "operations_service",
        "PPO_TRAINER": "ppo_trainer",
        "EMOTIONAL_TWIN_AGENT": "emotional_twin_agent",
        "INFINITE_SIMULATOR": "infinite_simulator",
        "TRADE_RECONCILER": "trade_reconciler",
        "SWARM_MANAGER": "swarm_manager",
        "PERFORMANCE_VALIDATOR": "performance_validator",
    }
    
    if name in attr_map:
        return getattr(container, attr_map[name])

    if name == "log_thought":
        return container.operations_service.log_thought
    if name == "detect_market_regime":
        return container.engine.detect_market_regime
    if name == "generate_multi_tf_chart":
        return container.visualization_service.generate_multi_tf_chart
    if name == "tk":
        import tkinter as tk

        return tk

    raise AttributeError(f"module 'lumina_v45.1.1' has no attribute '{name}'")


# ===== PUBLIC API =====
# Dynamically generated from container services
# Allows external code to access all needed functionality

def get_public_api() -> dict:
    """Get the public API dictionary (dynamically from container)."""
    return create_public_api(get_container())


# ===== MAIN BOOTSTRAP FUNCTION =====

def main() -> None:
    """
    Main entry point for the Lumina trading bot.
    
    Initializes the application container, configures all services,
    and starts the trading loop.
    """
    container = get_container()
    runtime_app = sys.modules[__name__]
    container.engine.bind_app(runtime_app)
    container.runtime_context.app = runtime_app

    # Publish the compatibility API onto the runtime module for legacy workers.
    for exported_name, exported_fn in create_public_api(container).items():
        setattr(runtime_app, exported_name, exported_fn)
    setattr(runtime_app, "engine", container.engine)
    setattr(runtime_app, "runtime_context", container.runtime_context)
    setattr(runtime_app, "logger", container.logger)
    setattr(runtime_app, "INSTRUMENT", container.primary_instrument)
    setattr(runtime_app, "SWARM_SYMBOLS", list(container.swarm_symbols))
    
    print(f"🚀 LUMINA OOP runtime started (Mode: {container.config.trade_mode.upper()})")
    print(f"🕸️ Swarm active on symbols: {', '.join(container.swarm_symbols)}")
    
    # Bootstrap all services and daemons
    bootstrap_runtime(container)
    
    # Start the main trading loop
    if container.config.use_human_main_loop:
        print("✨ Human-like main loop starting...")
        threading.Thread(target=container.analysis_service.run_main_loop, daemon=True).start()
    else:
        print("ℹ️ USE_HUMAN_MAIN_LOOP=False -> human-like loop not started")
    
    # Run the forever loop (blocking)
    container.operations_service.run_forever_loop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Shutdown signal received")
    except Exception as e:
        get_container().logger.error(f"Fatal error: {e}", exc_info=True)
        raise
