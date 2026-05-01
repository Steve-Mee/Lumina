"""Bounded context: risk.

This package is the canonical import surface for risk-domain APIs.
Uses lazy attribute resolution to avoid engine bootstrap import cycles.
"""

from lumina_core.risk.risk_allocator import RiskAllocatorMixin
from lumina_core.risk.risk_gates import RiskGatesMixin
from lumina_core.risk.dynamic_kelly import DynamicKellyEstimator, get_global_kelly_estimator
from lumina_core.risk.cost_model import CostBreakdown, TradeExecutionCostModel

__all__ = [
    "HardRiskController",
    "RiskLimits",
    "RiskState",
    "risk_limits_from_config",
    "MarginSnapshotProvider",
    "PortfolioVaRAllocator",
    "RiskAllocatorMixin",
    "RiskGatesMixin",
    "DynamicKellyEstimator",
    "get_global_kelly_estimator",
    "CostBreakdown",
    "TradeExecutionCostModel",
]


def __getattr__(name: str):
    if name in {"HardRiskController", "RiskLimits", "RiskState", "risk_limits_from_config"}:
        from lumina_core.risk.risk_controller import (
            HardRiskController,
            RiskLimits,
            RiskState,
            risk_limits_from_config,
        )

        return {
            "HardRiskController": HardRiskController,
            "RiskLimits": RiskLimits,
            "RiskState": RiskState,
            "risk_limits_from_config": risk_limits_from_config,
        }[name]
    if name == "MarginSnapshotProvider":
        from lumina_core.engine.margin_snapshot_provider import MarginSnapshotProvider

        return MarginSnapshotProvider
    if name == "PortfolioVaRAllocator":
        from lumina_core.engine.portfolio_var_allocator import PortfolioVaRAllocator

        return PortfolioVaRAllocator
    raise AttributeError(name)
