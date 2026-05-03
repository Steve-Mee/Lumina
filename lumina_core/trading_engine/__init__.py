"""Bounded context: trading_engine.

Uses lazy attribute resolution to avoid import cycles with lumina_core.engine.
"""

__all__ = [
    "AgentStateContext",
    "EngineConfig",
    "EngineServices",
    "install_lumina_engine_state_facade",
    "EngineSnapshotService",
    "EngineStatePersistenceService",
    "LuminaEngine",
    "MarketDataManager",
    "MarketStateContext",
    "MarketDataIngestService",
    "OperationsService",
    "PositionStateContext",
    "RiskStateContext",
    "TradeReconciler",
    "ValuationEngine",
]


def __getattr__(name: str):
    if name == "EngineConfig":
        from lumina_core.engine.engine_config import EngineConfig

        return EngineConfig
    if name == "LuminaEngine":
        from lumina_core.engine.lumina_engine import LuminaEngine

        return LuminaEngine
    if name == "MarketDataManager":
        from lumina_core.engine.market_data_manager import MarketDataManager

        return MarketDataManager
    if name == "MarketDataIngestService":
        from lumina_core.engine.market_data_service import MarketDataIngestService

        return MarketDataIngestService
    if name == "OperationsService":
        from lumina_core.engine.operations_service import OperationsService

        return OperationsService
    if name == "TradeReconciler":
        from lumina_core.engine.trade_reconciler import TradeReconciler

        return TradeReconciler
    if name == "ValuationEngine":
        from lumina_core.engine.valuation_engine import ValuationEngine

        return ValuationEngine
    if name == "EngineServices":
        from lumina_core.trading_engine.engine_services import EngineServices

        return EngineServices
    if name == "install_lumina_engine_state_facade":
        from lumina_core.trading_engine.engine_state_facade import install_lumina_engine_state_facade

        return install_lumina_engine_state_facade
    if name in {
        "AgentStateContext",
        "EngineSnapshotService",
        "MarketStateContext",
        "PositionStateContext",
        "RiskStateContext",
    }:
        from lumina_core.trading_engine.engine_snapshot import (
            AgentStateContext,
            EngineSnapshotService,
            MarketStateContext,
            PositionStateContext,
            RiskStateContext,
        )

        return {
            "AgentStateContext": AgentStateContext,
            "EngineSnapshotService": EngineSnapshotService,
            "MarketStateContext": MarketStateContext,
            "PositionStateContext": PositionStateContext,
            "RiskStateContext": RiskStateContext,
        }[name]
    if name == "EngineStatePersistenceService":
        from lumina_core.trading_engine.engine_state_persistence import EngineStatePersistenceService

        return EngineStatePersistenceService
    raise AttributeError(name)
