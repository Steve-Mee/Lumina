"""Engine-tier ingest, analysis, and reporting service wiring."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lumina_core.engine import (
    DashboardService,
    HumanAnalysisService,
    MarketDataIngestService,
    MemoryService,
    OperationsService,
    ReportingService,
    VisualizationService,
)
from lumina_core.reasoning.reasoning_service import ReasoningService

if TYPE_CHECKING:
    from lumina_core.container import ApplicationContainer


def wire_platform_services(container: "ApplicationContainer") -> None:
    """Market data through reporting (depends on engine + local inference)."""
    container.market_data_service = MarketDataIngestService(engine=container.engine)
    container.memory_service = MemoryService(engine=container.engine)
    container.operations_service = OperationsService(engine=container.engine, container=container)
    container.analysis_service = HumanAnalysisService(engine=container.engine)
    container.engine.market_data_service = container.market_data_service
    container.engine.memory_service = container.memory_service
    container.engine.operations_service = container.operations_service
    container.engine.analysis_service = container.analysis_service

    container.reasoning_service = ReasoningService(
        engine=container.engine,
        inference_engine=container.local_inference_engine,
        regime_detector=container.regime_detector,
        container=container,
    )
    container.engine.reasoning_service = container.reasoning_service
    container.dashboard_service = DashboardService(engine=container.engine)
    container.visualization_service = VisualizationService(engine=container.engine)
    container.reporting_service = ReportingService(
        engine=container.engine,
        dashboard_service=container.dashboard_service,
    )


def wire_dashboard_cross_refs(container: "ApplicationContainer") -> None:
    container.dashboard_service.visualization_service = container.visualization_service
    container.visualization_service.dashboard_launcher = container.dashboard_service.start_dashboard


def validate_engine_attributes(container: "ApplicationContainer") -> None:
    required_attributes = [
        "config",
        "dream_state",
        "bible_engine",
        "market_data",
        "valuation_engine",
        "regime_history",
        "narrative_memory",
        "memory_buffer",
        "trade_reflection_history",
        "pnl_history",
        "equity_curve",
        "trade_log",
        "performance_log",
        "world_model",
        "AI_DRAWN_FIBS",
        "cost_tracker",
        "current_regime_snapshot",
        "logger",
        "risk_controller",
        "decision_log",
        "observability_service",
        "regime_detector",
        "local_engine",
        "reasoning_service",
        "emotional_twin_agent",
        "infinite_simulator",
        "validator",
        "swarm",
        "portfolio_var_allocator",
    ]

    missing = [attr for attr in required_attributes if not hasattr(container.engine, attr)]
    if missing:
        msg = f"LuminaEngine is missing required attributes: {missing}"
        container.logger.error(msg)
        raise AttributeError(msg)

    container.logger.debug(
        "Engine validation passed: all %d required attributes present",
        len(required_attributes),
    )