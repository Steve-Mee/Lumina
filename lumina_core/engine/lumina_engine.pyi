from __future__ import annotations

from datetime import datetime
from types import ModuleType
from typing import Any

from lumina_core.monitoring.runtime_counters import RuntimeCounters
from lumina_core.ports.engine_service_ports import EngineServicePorts
from lumina_core.risk.orchestration import RiskOrchestrator
from lumina_core.trading_engine.engine_services import EngineServices
from lumina_core.trading_engine.engine_snapshot import EngineSnapshotService
from lumina_core.trading_engine.engine_state_persistence import EngineStatePersistenceService

from .dream_state import DreamState
from .dream_state_manager import DreamStateManager
from .economic_truth import EconomicTruth
from .engine_config import EngineConfig
from .execution_service import ExecutionService
from .market_data_domain_service import MarketDataDomainService
from .market_data_manager import MarketDataManager
from .runtime_state import EngineAccountState, EngineMemoryState, EnginePerformanceState, EnginePositionState
from .technical_analysis_service import TechnicalAnalysisService
from .valuation_engine import ValuationEngine


class LuminaEngine:
    config: EngineConfig
    app: ModuleType | None
    dream_state: DreamState
    market_data: MarketDataManager
    valuation_engine: ValuationEngine
    memory_state: EngineMemoryState
    performance_state: EnginePerformanceState
    position_state: EnginePositionState
    account_state: EngineAccountState
    runtime_counters: RuntimeCounters
    snapshot_service: EngineSnapshotService
    persistence_service: EngineStatePersistenceService
    services: EngineServices
    services_ports: EngineServicePorts | None
    risk_orchestrator: RiskOrchestrator | None
    execution_service: ExecutionService | None
    dream_state_manager: DreamStateManager | None
    market_domain_service: MarketDataDomainService | None
    technical_analysis_service: TechnicalAnalysisService | None
    economic_truth: EconomicTruth

    # Runtime-proxied attributes installed by engine_state_facade.
    event_bus: Any
    live_data_lock: Any
    ohlc_1min: Any
    live_quotes: list[dict[str, Any]]
    current_candle: dict[str, Any]
    candle_start_ts: float
    sim_position_qty: int
    sim_entry_price: float
    sim_unrealized: float
    sim_peak: float
    live_position_qty: int
    last_entry_price: float
    last_realized_pnl_snapshot: float
    live_trade_signal: str
    pending_trade_reconciliations: list[dict[str, Any]]
    account_balance: float
    account_equity: float
    realized_pnl_today: float
    open_pnl: float
    available_margin: float
    positions_margin_used: float
    equity_snapshot_ok: bool
    equity_snapshot_reason: str
    admission_chain_final_arbitration_approved: bool
    regime_history: list[dict[str, Any]]
    narrative_memory: list[dict[str, Any]]
    memory_buffer: list[dict[str, Any]]
    trade_reflection_history: list[Any]
    pnl_history: list[Any]
    equity_curve: list[Any]
    trade_log: list[Any]
    performance_log: list[Any]
    cost_tracker: dict[str, Any]
    local_engine: Any
    fast_path: Any
    backtester: Any
    advanced_backtester: Any
    ppo_trainer: Any
    rl_env: Any
    risk_controller: Any
    risk_policy: Any
    final_arbitration: Any
    equity_snapshot_provider: Any
    infinite_simulator: Any
    emotional_twin_agent: Any
    swarm: Any
    validator: Any
    observability_service: Any
    session_guard: Any
    portfolio_var_allocator: Any
    decision_log: Any
    audit_log_service: Any
    reasoning_service: Any
    blackboard: Any
    meta_agent_orchestrator: Any
    market_data_service: Any
    memory_service: Any
    operations_service: Any
    analysis_service: Any
    dashboard_service: Any
    visualization_service: Any
    reporting_service: Any
    trade_reconciler: Any
    dynamic_kelly_estimator: Any
    regime_detector: Any
    current_regime_snapshot: dict[str, Any]
    world_model: dict[str, Any]
    AI_DRAWN_FIBS: dict[str, Any]
    blackboard_tokens: list[str]
    last_validation: datetime | None

    def __init__(self, config: EngineConfig, **kwargs: Any) -> None: ...
    def _sync_services_registry(self) -> None: ...
    def hydrate_from_app(self, app: ModuleType) -> None: ...
    def save_state(self) -> None: ...
    def load_state(self) -> None: ...
    def build_state_contexts(self) -> dict[str, Any]: ...
    def serialize_state_snapshot(self) -> dict[str, Any]: ...
    def evolve_bible(self, updates: dict[str, Any]) -> None: ...
    def calculate_adaptive_risk_and_qty(
        self, price: float, regime: str, stop_price: float, confidence: float | None = None
    ) -> int: ...
    def update_performance_log(self, trade_data: dict[str, Any]) -> None: ...
    def detect_candle_patterns(self, df: Any, tf: str = "1min") -> dict[str, str]: ...
    def generate_price_action_summary(self) -> str: ...
    def detect_market_regime(self, df: Any) -> str: ...
    def detect_market_structure(self, df: Any) -> dict[str, Any]: ...
    def calculate_dynamic_confluence(self, regime: str, recent_winrate: float) -> float: ...
    def is_significant_event(self, current_price: float, previous_price: float, regime: str) -> bool: ...
    def update_cost_tracker_from_usage(self, usage: dict[str, Any] | None, channel: str = "reasoning") -> None: ...
    def run_async_safely(self, coro: Any) -> Any: ...
    def parse_json_loose(self, raw_text: str) -> dict[str, Any]: ...
    def build_pa_signature(self, pa_summary: str) -> str: ...
    @property
    def bible(self) -> dict[str, Any]: ...
    @property
    def evolvable_layer(self) -> dict[str, Any]: ...
    def get_current_dream_snapshot(self) -> dict[str, Any]: ...
    def bind_blackboard(self, blackboard: Any) -> None: ...
    def set_current_dream_fields(self, updates: dict[str, Any]) -> None: ...
    def set_current_dream_value(self, key: str, value: Any) -> None: ...
    def bind_app(self, app: ModuleType) -> None: ...
    def set_rl_policy(self, model: Any, confidence_threshold: float = 0.78) -> None: ...
    def clear_rl_policy(self) -> None: ...
    def apply_rl_live_decision(self, action_payload: dict[str, Any], current_price: float, regime: str) -> bool: ...
