# CANONICAL IMPLEMENTATION – v50 Living Organism
# Dependency Injection Container: Zero Global State
from __future__ import annotations

import atexit
import logging
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Optional, cast

from dotenv import load_dotenv

from lumina_core.engine import (
    AgentBlackboard,
    AgentDecisionLog,
    AuditLogService,
    DashboardService,
    EngineConfig,
    MetaAgentOrchestrator,
    HumanAnalysisService,
    LocalInferenceEngine,
    MarketDataService,
    MemoryService,
    OperationsService,
    PerformanceValidator,
    ReportingService,
    RegimeDetector,
    ReasoningService,
    SelfEvolutionMetaAgent,
    SwarmManager,
    TradeReconciler,
    VisualizationService,
)
from lumina_core.engine.broker_bridge import BrokerBridge, broker_factory
from lumina_core.engine.portfolio_var_allocator import PortfolioVaRAllocator
from lumina_core.engine.risk_controller import HardRiskController
from lumina_core.engine.valuation_engine import ValuationEngine
from lumina_agents.news_agent import NewsAgent
from lumina_core.engine.emotional_twin_agent import EmotionalTwinAgent
from lumina_core.engine.lumina_engine import LuminaEngine
from lumina_core.engine.self_evolution_meta_agent import load_evolution_config
from lumina_core.infinite_simulator import InfiniteSimulator
from lumina_core.logging_utils import build_logger
from lumina_core.monitoring import ObservabilityService
from lumina_core.ppo_trainer import PPOTrainer
from lumina_core.rl_environment import RLTradingEnvironment
from lumina_core.runtime_context import RuntimeContext


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


@dataclass(slots=True)
class ApplicationContainer:
    """
    Dependency Injection Container: manages all services and eliminates global state.

    All dependencies are built in __post_init__ (pure object-graph, no network I/O).
    Call start() to connect the broker and register cleanup handlers.
    Services are typed and accessed via properties, not global variables.

    Usage::

        container = ApplicationContainer()
        container.start()         # connects broker, registers atexit handlers
        engine: LuminaEngine = container.engine
        market_data: MarketDataService = container.market_data_service
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
    market_data_service: MarketDataService = field(init=False)
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
    decision_log: AgentDecisionLog = field(init=False)
    audit_log_service: AuditLogService = field(init=False)
    blackboard: AgentBlackboard = field(init=False)
    self_evolution_meta_agent: SelfEvolutionMetaAgent = field(init=False)
    meta_agent_orchestrator: MetaAgentOrchestrator = field(init=False)

    # Voice/audio components
    voice_recognizer: Optional[Any] = field(default=None, init=False)
    tts_engine: Optional[Any] = field(default=None, init=False)

    # Instrument symbols
    swarm_symbols: list[str] = field(default_factory=list, init=False)
    primary_instrument: str = field(default="", init=False)

    def __post_init__(self) -> None:
        """Initialize all services with explicit dependency ordering."""
        # Load config first so all dependent defaults read finalized env/yaml values.
        self.config = self.config_service.load()

        # Initialize logger first (needed by all other services)
        log_level = os.getenv("LUMINA_LOG_LEVEL", "INFO").upper()
        self.logger = build_logger("lumina", log_level=log_level, file_path="logs/lumina_full_log.csv")

        # Start observability before any services (zero-overhead when disabled)
        self.observability_service = self._init_observability()

        # Build voice config from loaded settings/env.
        self.voice_config = VoiceConfig(input_enabled=self.config.voice_input_enabled)

        # Validate configuration
        self._validate_config()

        # Initialize voice/audio components
        self._init_voice()

        # Initialize instrument symbols
        self._init_instruments()

        # Initialize core engine
        self.engine = cast(Any, LuminaEngine)(self.config)
        self.engine.observability_service = self.observability_service
        self.valuation_engine = self.engine.valuation_engine
        if self.engine.risk_controller is None:
            raise RuntimeError("Engine risk_controller was not initialized")
        self.risk_controller = self.engine.risk_controller
        self.decision_log = AgentDecisionLog()
        self.engine.decision_log = self.decision_log
        self.audit_log_service = AuditLogService(
            path=self.config.trade_decision_audit_log,
            enabled=True,
            fail_closed_real=bool(self.config.trade_decision_audit_fail_closed_real),
        )
        self.engine.audit_log_service = self.audit_log_service
        self.runtime_context = cast(Any, RuntimeContext)(engine=self.engine, app=None, container=self)
        self.regime_detector = RegimeDetector(
            config=getattr(self.config, "regime", {}), valuation_engine=self.engine.valuation_engine
        )
        self.engine.regime_detector = self.regime_detector

        # Initialize inference engine and inject into LuminaEngine
        self.local_inference_engine = LocalInferenceEngine(context=self.runtime_context)
        self.engine.local_engine = self.local_inference_engine

        # Initialize services (order matters due to dependencies)
        self._init_services()

        # Build broker (no network I/O yet — call start() to connect).
        self.broker = broker_factory(config=self.config, engine=self.engine, logger=self.logger)

    def start(self) -> "ApplicationContainer":
        """Connect the broker and register process-exit cleanup handlers.

        Must be called once after __post_init__ completes.  Separating build
        (pure object graph) from start (network I/O) makes unit-testing the
        container possible without live connections.

        Returns self for optional one-liner chaining::

            container = ApplicationContainer().start()
        """
        self.broker.connect()
        self._register_cleanup()
        return self

    def _validate_config(self) -> None:
        """Validate required configuration."""
        # Fase 2.2: centralised env/placeholder/secret check first
        from lumina_core.config_loader import ConfigLoader  # noqa: PLC0415

        ConfigLoader.validate_startup(raise_on_error=True)

        if str(getattr(self.config, "broker_backend", "paper")).strip().lower() == "live" and not (
            self.config.broker_crosstrade_api_key or self.config.crosstrade_token
        ):
            self.logger.error("Config validation failed: CROSSTRADE_TOKEN missing")
            raise ValueError("CROSSTRADE_TOKEN not found in .env or config.yaml")

        configured_symbols = [str(s).strip().upper() for s in self.config.swarm_symbols]
        allowed_roots = set(self.config.supported_swarm_roots)
        invalid_symbols = [sym for sym in configured_symbols if str(sym).split(" ")[0] not in allowed_roots]
        if invalid_symbols:
            msg = f"Invalid SWARM_SYMBOLS: {invalid_symbols}. Allowed roots: {allowed_roots}"
            self.logger.error(f"Config validation failed: {msg}")
            raise ValueError(msg)

    def _init_voice(self) -> None:
        """Initialize voice input/output components with lazy imports."""
        # Lazy import speech_recognition only if voice input is enabled
        if self.voice_config.input_enabled:
            try:
                import speech_recognition as sr  # noqa: PLC0415

                self.voice_recognizer = sr.Recognizer()
                self.logger.info("Voice recognizer initialized")
            except ImportError:
                self.logger.warning("speech_recognition library not available; voice input disabled")
                self.voice_config.input_enabled = False
            except Exception as e:
                self.logger.warning(f"Failed to initialize voice recognizer: {e}")

        # Lazy import pyttsx3 only if voice output is enabled
        if self.voice_config.output_enabled:
            try:
                import pyttsx3  # noqa: PLC0415

                self.tts_engine = pyttsx3.init()
                self.tts_engine.setProperty("rate", self.voice_config.tts_config.rate)
                self.tts_engine.setProperty("volume", self.voice_config.tts_config.volume)
                self.logger.info("TTS engine initialized")
            except ImportError:
                self.logger.warning("pyttsx3 library not available; voice output disabled (headless mode OK)")
                self.voice_config.output_enabled = False
            except Exception as e:
                self.logger.warning(f"Failed to initialize TTS engine: {e} (headless mode OK)")

    def _init_instruments(self) -> None:
        """Initialize instrument symbols from config."""
        self.swarm_symbols = [str(s).strip().upper() for s in self.config.swarm_symbols]
        self.primary_instrument = str(self.config.instrument).strip().upper()

        # Ensure primary instrument is first in swarm list
        if self.primary_instrument not in self.swarm_symbols:
            self.swarm_symbols.insert(0, self.primary_instrument)

        self.logger.info(f"Instruments configured: primary={self.primary_instrument}, swarm={self.swarm_symbols}")

    def _init_services(self) -> None:
        """Initialize all services in dependency order."""
        # Level 1: Services with no service dependencies (only engine)
        blackboard_enabled = os.getenv("LUMINA_BLACKBOARD_ENABLED", "true").strip().lower() == "true"
        blackboard_enforced = os.getenv("LUMINA_BLACKBOARD_ENFORCED", "false").strip().lower() == "true"
        orchestrator_enabled = os.getenv("LUMINA_META_ORCHESTRATOR_ENABLED", "true").strip().lower() == "true"

        if blackboard_enforced and not blackboard_enabled:
            raise RuntimeError("LUMINA_BLACKBOARD_ENFORCED=true requires LUMINA_BLACKBOARD_ENABLED=true")

        if blackboard_enabled:
            self.blackboard = AgentBlackboard(obs_service=self.observability_service)
            self.blackboard.load_recent_from_disk()
            self.engine.bind_blackboard(self.blackboard)
        else:
            self.blackboard = None  # type: ignore[assignment]

        self.market_data_service = MarketDataService(engine=self.engine)
        self.memory_service = MemoryService(engine=self.engine)
        self.operations_service = OperationsService(engine=self.engine, container=self)
        self.analysis_service = HumanAnalysisService(engine=self.engine)
        self.news_agent = NewsAgent(engine=self.engine)
        self.ppo_trainer = PPOTrainer(engine=self.engine)
        self.engine.ppo_trainer = self.ppo_trainer  # Fase 3.1: engine back-reference

        # Level 2: Services that depend on level 1 services
        self.reasoning_service = ReasoningService(
            engine=self.engine,
            inference_engine=self.local_inference_engine,
            regime_detector=self.regime_detector,
            container=self,
        )
        self.engine.reasoning_service = self.reasoning_service
        self.dashboard_service = DashboardService(engine=self.engine)
        self.visualization_service = VisualizationService(engine=self.engine)
        self.reporting_service = ReportingService(engine=self.engine, dashboard_service=self.dashboard_service)

        # Level 3: Agents and simulators
        self.emotional_twin_agent = EmotionalTwinAgent(engine=self.engine)
        self.engine.emotional_twin_agent = self.emotional_twin_agent  # Fase 3.1
        self.infinite_simulator = InfiniteSimulator(
            runtime=self.runtime_context,
            market_data_service=self.market_data_service,
            ppo_trainer=self.ppo_trainer,
        )
        self.engine.infinite_simulator = self.infinite_simulator  # Fase 3.1

        evolution_cfg = load_evolution_config()
        self.self_evolution_meta_agent = SelfEvolutionMetaAgent.from_container(
            container=self,
            enabled=bool(evolution_cfg.get("enabled", True)),
            approval_required=bool(evolution_cfg.get("approval_required", True)),
            mode=str(evolution_cfg.get("mode", getattr(self.config, "trade_mode", "real"))),
            aggressive_evolution=bool(evolution_cfg.get("aggressive_evolution", False)),
            max_mutation_depth=str(evolution_cfg.get("max_mutation_depth", "conservative")),
            obs_service=self.observability_service,
            fine_tuning_cfg=evolution_cfg.get("fine_tuning", {}),
        )
        self.self_evolution_meta_agent.blackboard = self.blackboard
        if orchestrator_enabled and self.blackboard is not None:
            self.meta_agent_orchestrator = MetaAgentOrchestrator(
                blackboard=self.blackboard,
                self_evolution_agent=self.self_evolution_meta_agent,
                ppo_trainer=self.ppo_trainer,
                bible_engine=self.engine.bible_engine,
            )
            self.engine.meta_agent_orchestrator = self.meta_agent_orchestrator
        else:
            self.meta_agent_orchestrator = None  # type: ignore[assignment]
            self.engine.meta_agent_orchestrator = None

        # Level 4: Validators and reconcilers
        self.performance_validator = PerformanceValidator(
            engine=self.engine,
            market_data_service=self.market_data_service,
            ppo_trainer=self.ppo_trainer,
        )
        self.engine.validator = self.performance_validator

        self.trade_reconciler = TradeReconciler(engine=self.engine)

        # Level 5: Swarm manager
        self.swarm_manager = SwarmManager(self.engine)
        self.engine.swarm = self.swarm_manager

        # Promote engine-owned hard risk controller to container surface.
        if self.engine.risk_controller is None:
            raise RuntimeError("Engine risk_controller was not initialized")

        portfolio_var_cfg = getattr(self.config, "portfolio_var", {})
        if not isinstance(portfolio_var_cfg, dict):
            portfolio_var_cfg = {}
        self.portfolio_var_allocator = PortfolioVaRAllocator(
            valuation_engine=self.engine.valuation_engine,
            swarm_manager=self.swarm_manager,
            observability_service=self.observability_service,
            config=portfolio_var_cfg,
        )
        self.engine.portfolio_var_allocator = self.portfolio_var_allocator
        self.engine.risk_controller.portfolio_var_allocator = self.portfolio_var_allocator
        self.risk_controller = self.engine.risk_controller

        # Level 6: Cross-references
        self.dashboard_service.visualization_service = self.visualization_service
        self.visualization_service.dashboard_launcher = self.dashboard_service.start_dashboard

        # RL environment (optional, lazily created if needed)
        # self.rl_environment = RLTradingEnvironment(self.runtime_context)

        # Validate that all required engine attributes are set
        self._validate_engine_attributes()

        self.logger.info("All services initialized successfully")

    def _validate_engine_attributes(self) -> None:
        """Validate that all required engine attributes exist before assignment."""
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

        missing = []
        for attr in required_attributes:
            if not hasattr(self.engine, attr):
                missing.append(attr)

        if missing:
            msg = f"LuminaEngine is missing required attributes: {missing}"
            self.logger.error(msg)
            raise AttributeError(msg)

        self.logger.debug(f"Engine validation passed: all {len(required_attributes)} required attributes present")

    def _init_observability(self) -> ObservabilityService:
        """Load config and start ObservabilityService (no-op if monitoring disabled)."""
        try:
            from lumina_core.config_loader import ConfigLoader

            full_cfg: dict[str, Any] = ConfigLoader.get()
            obs = ObservabilityService.from_config(full_cfg)
            obs.start()
            return obs
        except Exception as exc:
            self.logger.warning("ObservabilityService init failed (continuing): %s", exc)
            return ObservabilityService.from_config({})

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

        atexit.register(cleanup_traded_reconciler)
        atexit.register(cleanup_observability)
        atexit.register(cleanup_tts)
        atexit.register(cleanup_broker)

        self.logger.info("Cleanup handlers registered")

    def get_status(self) -> dict[str, Any]:
        """Get container initialization status."""
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
        return container
    except Exception as e:
        logging.error(f"Failed to initialize application container: {e}", exc_info=True)
        raise
