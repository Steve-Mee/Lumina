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


@dataclass(slots=True)
class ApplicationContainer(ConfigHotReloadSupport):
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

    @property
    def smart_setup_service(self) -> Any:
        if self._smart_setup_service is None:
            from lumina_launcher.services.smart_setup_service import SmartSetupService

            self._smart_setup_service = SmartSetupService(Path.cwd())
        return self._smart_setup_service

    def __post_init__(self) -> None:
        """Initialize all services with explicit dependency ordering."""
        # Load config first so all dependent defaults read finalized env/yaml values.
        self.config = self.config_service.load()
        self._ensure_runtime_paths()
        self._configure_audit_streams()

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
        self.event_bus = EventBus()
        self.engine.event_bus = self.event_bus
        self.engine.bind_event_bus(self.event_bus)
        self.adaptive_intelligence_tracker = AdaptiveIntelligenceTracker(Path.cwd())
        self.adaptive_intelligence_tracker.bind(self.event_bus)
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
        self.adaptive_intelligence_manager = AdaptiveIntelligenceManager(Path.cwd())
        intelligence_status = self._refresh_adaptive_intelligence(
            source="container_bootstrap",
            refresh_hardware=False,
        )
        self.engine.local_engine = self.local_inference_engine

        # Initialize services (order matters due to dependencies)
        self._init_services()

        # Build broker (no network I/O yet — call start() to connect).
        self.broker = broker_factory(config=self.config, engine=self.engine, logger=self.logger)
        self.engine.equity_snapshot_provider = EquitySnapshotProvider(get_broker=lambda: self.broker, ttl_seconds=30.0)
        self.engine.services_ports = EngineServicePorts(
            risk=cast(Any, self.engine.risk_orchestrator),
            audit=self.audit_log_service,
            orchestration=self.event_bus,
            broker=self.broker,
            market_data=self.market_data_service,
            execution=cast(Any, self.engine.execution_service),
            dream=self.engine,
            evolution=None,
            reasoning=self.reasoning_service,
            experimental={"adaptive_intelligence": intelligence_status},
        )
        self.engine._sync_services_registry()

    def _ensure_runtime_paths(self) -> None:
        file_paths = [
            Path(self.config.state_file),
            Path(self.config.thought_log),
            Path(self.config.bible_file),
            Path(self.config.live_jsonl),
            Path(self.config.trade_reconciler_status_file),
            Path(self.config.trade_reconciler_audit_log),
            Path(self.config.trade_decision_audit_log),
        ]
        dir_paths = [
            Path(self.config.audit_streams_root),
            Path(self.config.journal_dir),
            Path(self.config.journal_pdf_dir),
            Path("state"),
            Path("logs"),
        ]
        for file_path in file_paths:
            file_path.parent.mkdir(parents=True, exist_ok=True)
        for dir_path in dir_paths:
            dir_path.mkdir(parents=True, exist_ok=True)

    def _configure_audit_streams(self) -> None:
        audit_root = Path(self.config.audit_streams_root)
        register_default_streams(
            trade_decision=self.config.trade_decision_audit_log,
            agent_decision=Path("state/agent_decision_log.jsonl"),
            evolution_meta=Path("state/evolution_log.jsonl"),
            security=audit_root / "security_audit.jsonl",
            governance_real_promotion=Path("state/real_promotion_approval_audit.jsonl"),
            evolution_decisions=Path("state/evolution_decisions.jsonl"),
            agent_thought=audit_root / "thought_log.jsonl",
            safety_constitution=audit_root / "constitutional_audit.jsonl",
            trade_reconciler=self.config.trade_reconciler_audit_log,
            lumina_bible=Path("state/lumina_bible_generated_strategies.jsonl"),
        )

    def start(self) -> "ApplicationContainer":
        """Connect the broker and register process-exit cleanup handlers.

        Must be called once after __post_init__ completes.  Separating build
        (pure object graph) from start (network I/O) makes unit-testing the
        container possible without live connections.

        Returns self for optional one-liner chaining::

            container = ApplicationContainer().start()
        """
        _bk = str(getattr(self.config, "broker_backend", "paper") or "paper").strip().lower()
        _tm = str(getattr(self.config, "trade_mode", "paper") or "paper").strip().lower()
        _cls = type(self.broker).__name__
        self.logger.info(f"BROKER_CONNECT_START,backend={_bk},trade_mode={_tm},broker_class={_cls}")
        flush_logger_handlers(self.logger)
        self.broker.connect()
        self.logger.info(f"BROKER_CONNECT_OK,broker_class={_cls}")
        flush_logger_handlers(self.logger)
        self._register_cleanup()
        flush_logger_handlers(self.logger)
        return self

    def _validate_config(self) -> None:
        """Validate required configuration."""
        # Fase 2.2: centralised env/placeholder/secret check first
        from lumina_core.config_loader import ConfigLoader  # noqa: PLC0415

        ConfigLoader.validate_startup(raise_on_error=True)

        if str(getattr(self.config, "broker_backend", "paper")).strip().lower() == "live":
            live_provider = str(getattr(self.config, "broker_live_provider", "crosstrade") or "crosstrade").strip().lower()
            if live_provider == "crosstrade" and not (
                self.config.broker_crosstrade_api_key or self.config.crosstrade_token
            ):
                self.logger.error("Config validation failed: CROSSTRADE_TOKEN missing")
                raise ValueError("CROSSTRADE_TOKEN not found in .env or config.yaml")
            if live_provider == "ninjatrader" and not bool(getattr(self.config, "ninjatrader_enabled", False)):
                self.logger.error("Config validation failed: ninjatrader bridge not enabled")
                raise ValueError("broker.ninjatrader.enabled must be true when broker.live_provider=ninjatrader")

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
                if self.tts_engine is not None:
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
        from lumina_core.container.agent_wiring import (
            bind_evolution_promotion_event_bus,
            prepare_blackboard,
            wire_intelligence_agents,
            wire_swarm,
        )
        from lumina_core.container.engine_wiring import (
            validate_engine_attributes,
            wire_dashboard_cross_refs,
            wire_platform_services,
        )
        from lumina_core.container.risk_wiring import wire_risk_services

        prepare_blackboard(self)
        wire_platform_services(self)
        wire_intelligence_agents(self)
        wire_swarm(self)
        wire_risk_services(self)
        wire_dashboard_cross_refs(self)
        validate_engine_attributes(self)
        bind_evolution_promotion_event_bus(self)
        self.engine._sync_services_registry()
        self.logger.info("All services initialized successfully")

    def _bind_evolution_promotion_event_bus(self) -> None:
        from lumina_core.container.agent_wiring import bind_evolution_promotion_event_bus

        bind_evolution_promotion_event_bus(self)

    def bind_runtime_module(self, runtime_module: Any) -> None:
        """Bind the process entry module (__main__) as engine.app; attach legacy lumina_runtime API."""
        from lumina_core.bootstrap import attach_runtime_app_to_module

        attach_runtime_app_to_module(self, runtime_module)
        self.engine.bind_app(runtime_module)
        self.runtime_context.app = runtime_module

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

    def _refresh_adaptive_intelligence(self, *, source: str, refresh_hardware: bool) -> dict[str, Any]:
        status_obj = self.adaptive_intelligence_manager.refresh(refresh_hardware=refresh_hardware)
        intelligence_status = status_obj.to_dict()
        self.local_inference_engine.apply_adaptive_intelligence(intelligence_status)
        self.engine.adaptive_intelligence = intelligence_status
        self._publish_adaptive_intelligence_state(intelligence_status, source=source)
        return intelligence_status

    def _publish_adaptive_intelligence_state(self, status: dict[str, Any], *, source: str) -> bool:
        signature = build_status_signature(status)
        previous = self._adaptive_intelligence_last_published_signature
        if previous == signature:
            return False
        transition = previous is not None
        transition_reason = "initial_publish" if previous is None else "status_signature_changed"
        self.event_bus.publish(
            topic="inference.adaptive_intelligence.state",
            producer="application_container",
            payload={
                **status,
                "source": source,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            metadata={
                "transition": transition,
                "transition_reason": transition_reason,
            },
            payload_model=AdaptiveIntelligenceState,
        )
        self._adaptive_intelligence_last_published_signature = signature
        return True

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
