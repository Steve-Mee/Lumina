# CANONICAL IMPLEMENTATION – v50 Living Organism
# Dependency Injection Container: Zero Global State
from __future__ import annotations

import atexit
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Optional, cast

from dotenv import load_dotenv

from lumina_core.audit import register_default_streams
from lumina_core.adaptive_intelligence import AdaptiveIntelligenceManager, build_status_signature
from lumina_core.audit.agent_decision_log import AgentDecisionLog
from lumina_core.audit.audit_log_service import AuditLogService
from lumina_core.engine import (
    DashboardService,
    EngineConfig,
    HumanAnalysisService,
    MarketDataIngestService,
    MemoryService,
    OperationsService,
    PerformanceValidator,
    ReportingService,
    VisualizationService,
)
from lumina_core.agent_orchestration import (
    AgentBlackboard,
    EventBus,
    MetaAgentOrchestrator,
    SelfEvolutionMetaAgent,
    SwarmManager,
)
from lumina_core.agent_orchestration.schemas import AdaptiveIntelligenceState
from lumina_core.broker.broker_bridge import BrokerBridge, broker_factory
from lumina_core.ports import EngineServicePorts
from lumina_core.risk.equity_snapshot import EquitySnapshotProvider
from lumina_core.risk.regime_detector import RegimeDetector
from lumina_core.risk import HardRiskController
from lumina_core.reasoning.local_inference_engine import LocalInferenceEngine
from lumina_core.reasoning.reasoning_service import ReasoningService
from lumina_core.trading_engine import LuminaEngine
from lumina_core.engine.trade_reconciler import TradeReconciler
from lumina_core.engine.portfolio_var_allocator import PortfolioVaRAllocator
from lumina_core.engine.valuation_engine import ValuationEngine
from lumina_agents.news_agent import NewsAgent
from lumina_core.engine.emotional_twin_agent import EmotionalTwinAgent
from lumina_core.evolution.meta_agent_config import load_evolution_config as load_evolution_config
from lumina_core.engine.canonical_training import InfiniteSimulator, PPOTrainer
from lumina_core.logging_utils import build_logger, flush_logger_handlers
from lumina_core.monitoring import ObservabilityService
from lumina_core.monitoring.adaptive_intelligence_tracker import AdaptiveIntelligenceTracker
from lumina_core.rl import RLTradingEnvironment
from lumina_core.runtime_context import RuntimeContext

from lumina_core.container.config_hot_reload import ConfigHotReloadSupport


@dataclass(slots=True)
class TTSConfig:
    """Text-to-speech configuration."""

    enabled: bool = field(default_factory=lambda: os.getenv("VOICE_ENABLED", "True").lower() == "true")
    rate: int = 172
    volume: float = 0.95

    def __post_init__(self) -> None:
        """Validate TTS config."""
        if not (0 <= self.volume <= 1.0):
            raise ValueError(f"TTS volume must be 0-1, got {self.volume}")
        if self.rate < 50 or self.rate > 300:
            raise ValueError(f"TTS rate must be 50-300, got {self.rate}")


@dataclass(slots=True)
class VoiceConfig:
    """Voice input/output configuration."""

    input_enabled: bool = field(default_factory=lambda: False)
    output_enabled: bool = field(default_factory=lambda: os.getenv("VOICE_ENABLED", "True").lower() == "true")
    wake_word: str = field(default_factory=lambda: os.getenv("VOICE_WAKE_WORD", "lumina").strip().lower())
    tts_config: TTSConfig = field(default_factory=TTSConfig)

    def __post_init__(self) -> None:
        """Validate voice config."""
        if not self.wake_word:
            raise ValueError("Wake word cannot be empty")
        if len(self.wake_word) < 2:
            raise ValueError(f"Wake word must be at least 2 characters, got {self.wake_word}")


@dataclass(slots=True)
class ConfigService:
    """Loads and validates runtime configuration sources."""

    def load(self) -> EngineConfig:
        """Load env/yaml-backed runtime config after dotenv is available."""
        # Avoid python-dotenv fallback introspection on __main__, which can recurse
        # when module-level __getattr__ is present in runtime entrypoints.
        load_dotenv(dotenv_path=Path.cwd() / ".env")
        return EngineConfig()


from lumina_core.container.container_lifecycle import ApplicationContainerLifecycleMixin
from lumina_core.container.container_instruments import ApplicationContainerInstrumentsMixin
from lumina_core.container.container_services import ApplicationContainerServicesMixin
from lumina_core.container.container_status import ContainerStatusMixin


@dataclass(slots=True)
class ApplicationContainer(
    ApplicationContainerLifecycleMixin,
    ApplicationContainerInstrumentsMixin,
    ApplicationContainerServicesMixin,
    ContainerStatusMixin,
    ConfigHotReloadSupport,
):
    """
    Dependency Injection Container: manages all services and eliminates global state.

    All dependencies are built in __post_init__ (pure object-graph, no network I/O).
    Call start() to connect the broker and register cleanup handlers.
    Services are typed and accessed via properties, not global variables.

    Usage::

        container = ApplicationContainer()
        container.start()         # connects broker, registers atexit handlers
        engine: LuminaEngine = container.engine
        market_data: MarketDataIngestService = container.market_data_service
    """

    # Core infrastructure
    config_service: ConfigService = field(default_factory=ConfigService)
    config: EngineConfig = field(init=False)
    logger: logging.Logger = field(init=False)
    voice_config: VoiceConfig = field(init=False)
    broker: BrokerBridge = field(init=False)  # built in __post_init__, connected in start()

    # Services (lazily initialized in __post_init__)
    engine: LuminaEngine = field(init=False)
    runtime_context: RuntimeContext = field(init=False)
    local_inference_engine: LocalInferenceEngine = field(init=False)
    adaptive_intelligence_manager: AdaptiveIntelligenceManager = field(init=False)
    market_data_service: MarketDataIngestService = field(init=False)
    memory_service: MemoryService = field(init=False)
    reasoning_service: ReasoningService = field(init=False)
    regime_detector: RegimeDetector = field(init=False)
    operations_service: OperationsService = field(init=False)
    analysis_service: HumanAnalysisService = field(init=False)
    dashboard_service: DashboardService = field(init=False)
    visualization_service: VisualizationService = field(init=False)
    reporting_service: ReportingService = field(init=False)
    valuation_engine: ValuationEngine = field(init=False)
    risk_controller: HardRiskController = field(init=False)
    portfolio_var_allocator: PortfolioVaRAllocator = field(init=False)
    news_agent: NewsAgent = field(init=False)
    ppo_trainer: PPOTrainer = field(init=False)
    emotional_twin_agent: EmotionalTwinAgent = field(init=False)
    infinite_simulator: InfiniteSimulator = field(init=False)
    trade_reconciler: TradeReconciler = field(init=False)
    swarm_manager: SwarmManager = field(init=False)
    performance_validator: PerformanceValidator = field(init=False)
    rl_environment: RLTradingEnvironment | None = field(default=None, init=False)
    observability_service: ObservabilityService = field(init=False)
    adaptive_intelligence_tracker: AdaptiveIntelligenceTracker = field(init=False)
    decision_log: AgentDecisionLog = field(init=False)
    audit_log_service: AuditLogService = field(init=False)
    blackboard: AgentBlackboard = field(init=False)
    event_bus: EventBus = field(init=False)
    self_evolution_meta_agent: SelfEvolutionMetaAgent = field(init=False)
    meta_agent_orchestrator: MetaAgentOrchestrator = field(init=False)

    # Voice/audio components
    voice_recognizer: Optional[Any] = field(default=None, init=False)
    tts_engine: Optional[Any] = field(default=None, init=False)

    # Instrument symbols
    swarm_symbols: list[str] = field(default_factory=list, init=False)
    primary_instrument: str = field(default="", init=False)
    _adaptive_intelligence_last_published_signature: tuple[Any, ...] | None = field(default=None, init=False)
    _smart_setup_service: Any = field(default=None, init=False)
    _config_reloader: Any = field(default=None, init=False)
    _birth_reload_host: Any = field(default=None, init=False)

    def _register_cleanup(self) -> None:
        """Register cleanup handlers for graceful shutdown."""

        def cleanup_traded_reconciler() -> None:
            try:
                if self.trade_reconciler:
                    self.trade_reconciler.stop()
            except Exception as e:
                self.logger.error(f"Error stopping trade reconciler: {e}")

        def cleanup_observability() -> None:
            try:
                self.observability_service.stop()
            except Exception as e:
                self.logger.error(f"Error stopping observability service: {e}")

        def cleanup_tts() -> None:
            try:
                if self.tts_engine:
                    self.tts_engine.stop()
            except Exception as e:
                self.logger.error(f"Error stopping TTS engine: {e}")

        def cleanup_broker() -> None:
            try:
                self.broker.disconnect()
            except Exception as e:
                self.logger.error(f"Error disconnecting broker: {e}")

        def cleanup_maturation_autopilot() -> None:
            try:
                from lumina_core.maturity.autopilot import stop_maturation_autopilot

                stop_maturation_autopilot()
            except Exception as e:
                self.logger.error(f"Error stopping maturation autopilot: {e}")

        atexit.register(cleanup_traded_reconciler)
        atexit.register(cleanup_observability)
        atexit.register(cleanup_tts)
        atexit.register(cleanup_broker)
        atexit.register(cleanup_maturation_autopilot)

        self.logger.info("Cleanup handlers registered")

    def get_status(self) -> dict[str, Any]:
        """Get container initialization status."""
        current_adaptive_intelligence = self._refresh_adaptive_intelligence(
            source="container_status_poll",
            refresh_hardware=False,
        )
        launcher_setup: dict[str, Any] = {}
        try:
            from lumina_launcher.core.setup_gate import launcher_setup_status_payload

            launcher_setup = launcher_setup_status_payload(
                Path.cwd(),
                smart_setup_service=self.smart_setup_service,
            )
        except Exception as exc:
            self.logger.warning("container.launcher_setup_status_failed detail=%s", exc)
        return {
            "engine_initialized": self.engine is not None,
            "services_count": sum(
                [
                    1
                    for attr in [
                        self.market_data_service,
                        self.memory_service,
                        self.reasoning_service,
                        self.operations_service,
                        self.analysis_service,
                        self.dashboard_service,
                        self.visualization_service,
                        self.reporting_service,
                        self.news_agent,
                        self.ppo_trainer,
                        self.emotional_twin_agent,
                        self.infinite_simulator,
                        self.trade_reconciler,
                        self.swarm_manager,
                        self.performance_validator,
                    ]
                    if attr is not None
                ]
            ),
            "voice_input_enabled": self.voice_recognizer is not None,
            "tts_enabled": self.tts_engine is not None,
            "swarm_symbols": self.swarm_symbols,
            "primary_instrument": self.primary_instrument,
            "adaptive_intelligence": current_adaptive_intelligence,
            "launcher_setup": launcher_setup,
        }


def create_application_container() -> ApplicationContainer:
    """
    Factory function to create and initialize the application container.

    This is the single entry point for bootstrapping the entire application.

    Returns:
        Fully initialized ApplicationContainer with all services ready.

    Raises:
        ValueError: If configuration is invalid or initialization fails.
    """
    try:
        container = ApplicationContainer()
        container.start()
        container.logger.info("✅ Application container initialized successfully")
        flush_logger_handlers(container.logger)
        return container
    except Exception as e:
        logging.error(f"Failed to initialize application container: {e}", exc_info=True)
        raise
