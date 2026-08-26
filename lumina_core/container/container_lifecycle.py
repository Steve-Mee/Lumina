"""ApplicationContainerLifecycleMixin (M5 extract)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, cast

from lumina_core.adaptive_intelligence import AdaptiveIntelligenceManager
from lumina_core.agent_orchestration import EventBus
from lumina_core.audit import register_default_streams
from lumina_core.audit.agent_decision_log import AgentDecisionLog
from lumina_core.audit.audit_log_service import AuditLogService
from lumina_core.broker.broker_bridge import broker_factory
from lumina_core.container.config_types import VoiceConfig
from lumina_core.logging_utils import build_logger, flush_logger_handlers, get_logger
from lumina_core.monitoring.adaptive_intelligence_tracker import AdaptiveIntelligenceTracker
from lumina_core.ports import EngineServicePorts
from lumina_core.reasoning.local_inference_engine import LocalInferenceEngine
from lumina_core.risk.equity_snapshot import EquitySnapshotProvider
from lumina_core.risk.regime_detector import RegimeDetector
from lumina_core.runtime_context import RuntimeContext
from lumina_core.trading_engine import LuminaEngine

logger = get_logger("lumina.container")


class ApplicationContainerLifecycleMixin:
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

        # Always-on Fabric link when native NT is the live provider (24/7 keep-alive).
        try:
            from lumina_core.broker.ninjatrader.fabric_link_supervisor import (
                ensure_fabric_link_supervisor,
            )

            ensure_fabric_link_supervisor(self.config, mode_context="sim")
        except Exception:
            logger.debug("fabric.supervisor.bootstrap_skipped", exc_info=True)

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

    def start(self) -> "ApplicationContainer":  # noqa: F821
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
            live_provider = str(
                getattr(self.config, "broker_live_provider", "ninjatrader") or "ninjatrader"
            ).strip().lower()
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


