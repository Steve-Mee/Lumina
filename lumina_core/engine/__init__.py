from .analysis_service import HumanAnalysisService
from lumina_core.audit.audit_log_service import AuditLogService
from .agent_blackboard import AgentBlackboard, BlackboardEvent
from lumina_core.audit.agent_decision_log import AgentDecisionLog
from lumina_core.reasoning.agent_policy_gateway import AgentPolicyGateway
from .bible_engine import BibleEngine
from lumina_core.broker.broker_bridge import (
    AccountInfo,
    BrokerBridge,
    Fill,
    Order,
    OrderResult,
    PaperBroker,
    Position,
    broker_factory,
)
from .dashboard_service import DashboardService
from .dream_state import DreamState
from .engine_config import EngineConfig
from .lumina_engine import LuminaEngine
from lumina_core.reasoning.local_inference_engine import LocalInferenceEngine
from .market_data_manager import MarketDataManager
from .market_data_service import MarketDataIngestService
# MarketDataDomainService / MarketDataService thin layer removed for radical simplicity (helpers inlined)
from .memory_service import MemoryService
from .operations_service import OperationsService
from .dream_state_manager import DreamStateManager
from .execution_service import ExecutionService
from .technical_analysis_service import TechnicalAnalysisService
from .performance_validator import PerformanceValidator
from .portfolio_var_allocator import PortfolioVaRAllocator
from .provider_normalization import ProviderNormalizationLayer
from lumina_core.audit.replay_validator import DecisionReplayValidator
from .reporting_service import ReportingService
from lumina_core.risk.regime_detector import RegimeDetector, RegimeSnapshot
from lumina_core.reasoning.reasoning_service import ReasoningService
from lumina_core.risk.session_guard import SessionGuard
from lumina_core.evolution.self_evolution_meta_agent import SelfEvolutionMetaAgent
from .meta_agent_orchestrator import MetaAgentOrchestrator
from .rl_guardrails import RLGuardrailLayer
from .evolution_lifecycle import EvolutionLifecycleManager
from .multi_symbol_swarm_manager import MultiSymbolSwarmManager, SymbolNode
from .swarm_manager import SwarmManager
from .trade_reconciler import TradeReconciler
from .visualization_service import VisualizationService
from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus
from lumina_core.risk.orchestration import RiskOrchestrator

__all__ = [
    "HumanAnalysisService",
    "AuditLogService",
    "AgentBlackboard",
    "BlackboardEvent",
    "AgentDecisionLog",
    "AgentPolicyGateway",
    "DashboardService",
    "BrokerBridge",
    "PaperBroker",
    "CrossTradeBroker",
    "Order",
    "OrderResult",
    "AccountInfo",
    "Position",
    "Fill",
    "broker_factory",
    "EngineConfig",
    "DreamState",
    "BibleEngine",
    "MarketDataManager",
    # MarketDataDomainService/MarketDataService removed (simplicity)
    "MarketDataIngestService",
    "DreamStateManager",
    "ExecutionService",
    "RiskOrchestrator",
    "TechnicalAnalysisService",
    "MemoryService",
    "OperationsService",
    "PerformanceValidator",
    "PortfolioVaRAllocator",
    "ProviderNormalizationLayer",
    "DecisionReplayValidator",
    "LuminaEngine",
    "LocalInferenceEngine",
    "ReportingService",
    "RegimeDetector",
    "RegimeSnapshot",
    "ReasoningService",
    "SessionGuard",
    "SelfEvolutionMetaAgent",
    "MetaAgentOrchestrator",
    "RLGuardrailLayer",
    "EvolutionLifecycleManager",
    "SymbolNode",
    "MultiSymbolSwarmManager",
    "SwarmManager",
    "TradeReconciler",
    "VisualizationService",
    "DomainEvent",
    "EventBus",
]


def __getattr__(name: str):  # type: ignore[no-untyped-def]
    """Lazy CrossTradeBroker re-export (ADR-0040 — zero default emergency plugin import)."""
    if name == "CrossTradeBroker":
        from lumina_core.broker.broker_bridge.cross_trade_broker import CrossTradeBroker

        return CrossTradeBroker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
