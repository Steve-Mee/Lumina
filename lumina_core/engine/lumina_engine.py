# CANONICAL IMPLEMENTATION – v50 Living Organism
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from types import ModuleType
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    pass

from lumina_bible import BibleEngine
from lumina_core.agent_orchestration.engine_bindings import bind_engine_blackboard
from lumina_core.monitoring.runtime_counters import RuntimeCounters
from lumina_core.ports.engine_service_ports import EngineServicePorts
from lumina_core.risk.final_arbitration import is_strict_arbitration_mode
from lumina_core.trading_engine.engine_services import EngineServices
from lumina_core.trading_engine.engine_snapshot import (
    AgentStateContext,
    EngineSnapshotService,
    MarketStateContext,
    PositionStateContext,
    RiskStateContext,
)
from lumina_core.trading_engine.engine_state_persistence import EngineStatePersistenceService
from lumina_core.trading_engine.engine_state_facade import SERVICE_PROXY_FIELDS, install_lumina_engine_state_facade

from .dream_state_manager import DreamStateManager
from .dream_state import DreamState
from .engine_config import EngineConfig
from .economic_truth import EconomicTruth
from .execution_service import ExecutionService
from .market_data_manager import MarketDataManager
from .market_data_domain_service import MarketDataDomainService
from .runtime_state import EngineAccountState, EngineMemoryState, EnginePerformanceState, EnginePositionState
from .technical_analysis_service import TechnicalAnalysisService
from .valuation_engine import ValuationEngine
from lumina_core.risk.orchestration import RiskOrchestrator

__all__ = [
    "AgentStateContext",
    "LuminaEngine",
    "MarketStateContext",
    "PositionStateContext",
    "RiskStateContext",
]

MIGRATED_SERVICE_PROXY_FIELDS: frozenset[str] = frozenset(
    {
        "audit_log_service",
        "decision_log",
        "reasoning_service",
        "session_guard",
        "regime_detector",
    }
)


@dataclass(slots=True)
class LuminaEngine:
    """Lightweight composition root that orchestrates delegated runtime services."""

    config: EngineConfig
    app: ModuleType | None = None
    dream_state: DreamState = field(default_factory=DreamState)
    bible_engine: BibleEngine | None = None
    market_data: MarketDataManager = field(default_factory=MarketDataManager)
    valuation_engine: ValuationEngine = field(default_factory=ValuationEngine)

    # Runtime mutable state grouped into explicit aggregates.
    memory_state: EngineMemoryState = field(default_factory=EngineMemoryState)
    performance_state: EnginePerformanceState = field(default_factory=EnginePerformanceState)
    position_state: EnginePositionState = field(default_factory=EnginePositionState)
    account_state: EngineAccountState = field(default_factory=EngineAccountState)
    trade_reconciler_status: dict[str, Any] = field(default_factory=dict)
    runtime_counters: RuntimeCounters = field(default_factory=RuntimeCounters)
    snapshot_service: EngineSnapshotService = field(default_factory=EngineSnapshotService)
    persistence_service: EngineStatePersistenceService = field(default_factory=EngineStatePersistenceService)
    services: EngineServices = field(default_factory=EngineServices)
    services_ports: EngineServicePorts | None = None

    world_model: dict[str, Any] = field(default_factory=dict)
    AI_DRAWN_FIBS: dict[str, Any] = field(default_factory=dict)
    rl_policy_model: Any | None = None
    rl_policy_enabled: bool = False
    rl_confidence_threshold: float = 0.78
    current_regime_snapshot: dict[str, Any] = field(default_factory=dict)
    logger: Any = field(default_factory=lambda: logging.getLogger("lumina"))
    fast_path: Any | None = None
    backtester: Any | None = None
    advanced_backtester: Any | None = None
    session_guard: Any | None = None
    risk_controller: Any | None = None
    risk_policy: Any | None = None
    final_arbitration: Any | None = None
    dynamic_kelly_estimator: Any | None = None
    blackboard: Any | None = None
    infinite_sim_last_run_date: str | None = None
    emotional_twin_last_train_date: str | None = None
    last_validation: datetime | None = None
    blackboard_tokens: list[str] = field(default_factory=list)
    economic_truth: EconomicTruth = field(default_factory=EconomicTruth)
    mode_risk_profile: dict[str, float] = field(default_factory=dict)
    dream_state_manager: DreamStateManager | None = None
    market_domain_service: MarketDataDomainService | None = None
    technical_analysis_service: TechnicalAnalysisService | None = None
    risk_orchestrator: RiskOrchestrator | None = None
    execution_service: ExecutionService | None = None

    def __post_init__(self) -> None:
        if self.bible_engine is None:
            from pathlib import Path  # noqa: PLC0415

            self.bible_engine = BibleEngine(Path(self.config.bible_file))
            if callable(getattr(self.bible_engine, "load", None)):
                self.bible_engine.bible = self.bible_engine.load()

        # FastPathEngine wordt hier lazy geladen om circulaire imports te vermijden
        if self.fast_path is None:
            from .fast_path_engine import FastPathEngine  # noqa: PLC0415

            self.fast_path = FastPathEngine(engine=cast(Any, self))

        # RealisticBacktesterEngine lazy init
        if self.backtester is None:
            from lumina_core.runtime_context import RuntimeContext  # noqa: PLC0415
            from .realistic_backtester_engine import RealisticBacktesterEngine  # noqa: PLC0415

            self.backtester = RealisticBacktesterEngine(context=RuntimeContext(engine=cast(Any, self)))

        # AdvancedBacktesterEngine lazy init
        if self.advanced_backtester is None:
            from lumina_core.runtime_context import RuntimeContext  # noqa: PLC0415
            from .advanced_backtester_engine import AdvancedBacktesterEngine  # noqa: PLC0415

            self.advanced_backtester = AdvancedBacktesterEngine(context=RuntimeContext(engine=cast(Any, self)))

        # RLTradingEnvironment, PPOTrainer, InfiniteSimulator, EmotionalTwinAgent,
        # SwarmManager and PerformanceValidator are built exclusively by
        # ApplicationContainer._init_services() which then assigns them back via
        # engine.ppo_trainer, engine.emotional_twin_agent, engine.infinite_simulator,
        # engine.swarm, engine.validator.  Constructing them here was dead-weight
        # double construction (Fase 3.1 clean-up).

        if self.config.trade_mode not in {"paper", "sim", "sim_real_guard", "real"}:
            raise ValueError("TRADE_MODE must be one of: paper, sim, sim_real_guard, real")

        if self.config.max_risk_percent <= 0:
            raise ValueError("MAX_RISK_PERCENT must be > 0")
        if self.config.drawdown_kill_percent <= 0:
            raise ValueError("DRAWDOWN_KILL_PERCENT must be > 0")

        # Compose engine responsibilities into narrow services.
        if self.dream_state_manager is None:
            self.dream_state_manager = DreamStateManager(engine=cast(Any, self), dream_state=self.dream_state)
        if self.market_domain_service is None:
            self.market_domain_service = MarketDataDomainService(engine=cast(Any, self))
        if self.technical_analysis_service is None:
            self.technical_analysis_service = TechnicalAnalysisService(engine=cast(Any, self))
        if self.risk_orchestrator is None:
            self.risk_orchestrator = RiskOrchestrator(
                engine=cast(Any, self),
                session_guard=self.session_guard,
                risk_controller=self.risk_controller,
                risk_policy=self.risk_policy,
                final_arbitration=self.final_arbitration,
                mode_risk_profile=dict(self.mode_risk_profile),
                dynamic_kelly_estimator=self.dynamic_kelly_estimator,
            )
        self.risk_orchestrator.initialize()
        self.session_guard = self.risk_orchestrator.session_guard
        self.risk_controller = self.risk_orchestrator.risk_controller
        self.risk_policy = self.risk_orchestrator.risk_policy
        self.final_arbitration = self.risk_orchestrator.final_arbitration
        trade_mode = str(getattr(self.config, "trade_mode", "paper") or "paper").strip().lower()
        if is_strict_arbitration_mode(trade_mode) and self.final_arbitration is None:
            raise RuntimeError(
                f"FinalArbitration is mandatory in {trade_mode.upper()} mode; engine initialization aborted."
            )
        self.mode_risk_profile = dict(self.risk_orchestrator.mode_risk_profile)
        self.dynamic_kelly_estimator = self.risk_orchestrator.dynamic_kelly_estimator
        if self.execution_service is None:
            self.execution_service = ExecutionService(engine=self)
        self._sync_services_registry()

    def _sync_services_registry(self) -> None:
        for field_name in SERVICE_PROXY_FIELDS:
            if field_name in MIGRATED_SERVICE_PROXY_FIELDS and self.services_ports is not None:
                continue
            setattr(self.services, field_name, getattr(self, field_name))

    def _load_mode_risk_profile(self) -> dict[str, float]:
        if self.risk_orchestrator is None:
            return {}
        return self.risk_orchestrator._load_mode_risk_profile()

    def _build_dynamic_kelly_estimator(self):
        if self.risk_orchestrator is None:
            return None
        return self.risk_orchestrator._build_dynamic_kelly_estimator()

    def hydrate_from_app(self, app: ModuleType) -> None:
        """Import runtime module state into engine-managed fields."""
        self.persistence_service.hydrate_from_app(cast(Any, self), app)

    def save_state(self) -> None:
        self.persistence_service.save_state(cast(Any, self))

    def load_state(self) -> None:
        self.persistence_service.load_state(cast(Any, self))

    def build_state_contexts(self) -> dict[str, Any]:
        return self.snapshot_service.build_state_contexts(cast(Any, self))

    def serialize_state_snapshot(self) -> dict[str, Any]:
        return self.snapshot_service.serialize_state_snapshot(cast(Any, self))

    def evolve_bible(self, updates: dict[str, Any]) -> None:
        assert self.bible_engine is not None
        self.bible_engine.evolve(updates)

    def calculate_adaptive_risk_and_qty(
        self,
        price: float,
        regime: str,
        stop_price: float,
        confidence: float | None = None,
    ) -> int:
        if self.risk_orchestrator is None:
            return 0
        return self.risk_orchestrator.calculate_adaptive_risk_and_qty(price, regime, stop_price, confidence)

    def update_performance_log(self, trade_data: dict[str, Any]) -> None:
        if self.execution_service is None:
            return
        self.execution_service.update_performance_log(
            cast(list[dict[str, Any]], getattr(self, "performance_log", [])),
            trade_data,
        )

    def detect_candle_patterns(self, df, tf: str = "1min") -> dict[str, str]:
        if self.market_domain_service is None:
            return {}
        return self.market_domain_service.detect_candle_patterns(df, tf)

    def generate_price_action_summary(self) -> str:
        if self.market_domain_service is None:
            return ""
        return self.market_domain_service.generate_price_action_summary()

    def detect_market_regime(self, df) -> str:
        if self.technical_analysis_service is None:
            return "NEUTRAL"
        return self.technical_analysis_service.detect_market_regime(df)

    def detect_market_structure(self, df) -> dict[str, Any]:
        if self.technical_analysis_service is None:
            return {}
        return self.technical_analysis_service.detect_market_structure(df)

    def calculate_dynamic_confluence(self, regime: str, recent_winrate: float) -> float:
        if self.technical_analysis_service is None:
            return 0.0
        return self.technical_analysis_service.calculate_dynamic_confluence(regime, recent_winrate)

    def is_significant_event(self, current_price: float, previous_price: float, regime: str) -> bool:
        if self.technical_analysis_service is None:
            return False
        return self.technical_analysis_service.is_significant_event(current_price, previous_price, regime)

    def update_cost_tracker_from_usage(self, usage: dict[str, Any] | None, channel: str = "reasoning") -> None:
        if self.technical_analysis_service is None:
            return
        self.technical_analysis_service.update_cost_tracker_from_usage(usage, channel)

    def run_async_safely(self, coro):
        if self.technical_analysis_service is None:
            return None
        return self.technical_analysis_service.run_async_safely(coro)

    def parse_json_loose(self, raw_text: str) -> dict[str, Any]:
        if self.technical_analysis_service is None:
            return {}
        return self.technical_analysis_service.parse_json_loose(raw_text)

    def build_pa_signature(self, pa_summary: str) -> str:
        if self.technical_analysis_service is None:
            return ""
        return self.technical_analysis_service.build_pa_signature(pa_summary)

    @property
    def bible(self) -> dict[str, Any]:
        assert self.bible_engine is not None
        assert self.bible_engine.bible is not None
        return self.bible_engine.bible

    @property
    def evolvable_layer(self) -> dict[str, Any]:
        assert self.bible_engine is not None
        return self.bible_engine.evolvable_layer

    def get_current_dream_snapshot(self) -> dict[str, Any]:
        if self.dream_state_manager is None:
            return self.dream_state.snapshot()
        return self.dream_state_manager.snapshot()

    def bind_blackboard(self, blackboard: Any) -> None:
        """Bind engine consumers to blackboard topics and enforce REAL safety gates."""
        self.blackboard = blackboard
        self.blackboard_tokens = bind_engine_blackboard(self, blackboard)

    def set_current_dream_fields(self, updates: dict[str, Any]) -> None:
        if self.dream_state_manager is None:
            self.dream_state.update(updates)
            return
        self.dream_state_manager.set_fields(updates)

    def set_current_dream_value(self, key: str, value: Any) -> None:
        if self.dream_state_manager is None:
            self.dream_state.set_value(key, value)
            return
        self.dream_state_manager.set_value(key, value)

    def bind_app(self, app: ModuleType) -> None:
        self.app = app

    def set_rl_policy(self, model: Any, confidence_threshold: float = 0.78) -> None:
        self.rl_policy_model = model
        self.rl_policy_enabled = model is not None
        self.rl_confidence_threshold = float(confidence_threshold)

    def clear_rl_policy(self) -> None:
        self.rl_policy_model = None
        self.rl_policy_enabled = False

    def apply_rl_live_decision(
        self,
        action_payload: dict[str, Any],
        current_price: float,
        regime: str,
    ) -> bool:
        if self.execution_service is None:
            return False
        return self.execution_service.apply_rl_live_decision(
            action_payload=action_payload,
            current_price=current_price,
            regime=regime,
            confidence_threshold=self.rl_confidence_threshold,
        )


install_lumina_engine_state_facade(LuminaEngine)
