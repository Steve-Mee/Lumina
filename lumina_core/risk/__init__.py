"""Bounded context: risk.

This package is the canonical import surface for risk-domain APIs.
Uses lazy attribute resolution to avoid engine bootstrap import cycles.
"""

from typing import TYPE_CHECKING

from lumina_core.risk.risk_allocator import RiskAllocatorMixin
from lumina_core.risk.risk_policy import RiskPolicy, load_risk_policy
from lumina_core.risk.admission_chain import (
    AdmissionChain,
    AdmissionContext,
    AdmissionStepResult,
    AdmissionTrace,
    default_chain_for_mode,
)
from lumina_core.risk.final_arbitration import (
    FinalArbitration,
    build_current_state_from_engine,
    build_order_intent_from_order,
)
from lumina_core.risk.schemas import (
    ArbitrationCheckStep,
    ArbitrationResult,
    ArbitrationState,
    OrderIntent,
    OrderIntentMetadata,
)
from lumina_core.risk.risk_gates import RiskGatesMixin
from lumina_core.risk.dynamic_kelly import DynamicKellyEstimator, get_global_kelly_estimator
from lumina_core.risk.cost_model import CostBreakdown, TradeExecutionCostModel
from lumina_core.risk.orchestration import RiskOrchestrator
from lumina_core.risk.cost_model_calibrator import (
    CalibrationResult,
    DailyCalibrationSummary,
    run_daily_calibration,
)

if TYPE_CHECKING:
    from lumina_core.risk.mode_capabilities import ModeCapabilities, resolve_mode_capabilities
    from lumina_core.risk.policy_engine import PolicyEngine
    from lumina_core.risk.regime_detector import RegimeDetector, RegimeSnapshot
    from lumina_core.risk.risk_controller import HardRiskController, RiskLimits, RiskState, risk_limits_from_config
    from lumina_core.risk.session_guard import SessionGuard
    from lumina_core.engine.margin_snapshot_provider import MarginSnapshotProvider
    from lumina_core.engine.portfolio_var_allocator import PortfolioVaRAllocator

__all__ = [
    "HardRiskController",
    "RiskLimits",
    "RiskState",
    "risk_limits_from_config",
    "MarginSnapshotProvider",
    "PortfolioVaRAllocator",
    "RiskPolicy",
    "load_risk_policy",
    "AdmissionChain",
    "AdmissionContext",
    "AdmissionStepResult",
    "AdmissionTrace",
    "default_chain_for_mode",
    "OrderIntent",
    "OrderIntentMetadata",
    "ArbitrationResult",
    "ArbitrationCheckStep",
    "ArbitrationState",
    "FinalArbitration",
    "build_current_state_from_engine",
    "build_order_intent_from_order",
    "RiskAllocatorMixin",
    "RiskGatesMixin",
    "RiskOrchestrator",
    "ModeCapabilities",
    "resolve_mode_capabilities",
    "RegimeDetector",
    "RegimeSnapshot",
    "SessionGuard",
    "PolicyEngine",
    "DynamicKellyEstimator",
    "get_global_kelly_estimator",
    "CostBreakdown",
    "TradeExecutionCostModel",
    "CalibrationResult",
    "DailyCalibrationSummary",
    "run_daily_calibration",
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
    if name in {"ModeCapabilities", "resolve_mode_capabilities"}:
        from lumina_core.risk.mode_capabilities import ModeCapabilities, resolve_mode_capabilities

        return {
            "ModeCapabilities": ModeCapabilities,
            "resolve_mode_capabilities": resolve_mode_capabilities,
        }[name]
    if name in {"RegimeDetector", "RegimeSnapshot"}:
        from lumina_core.risk.regime_detector import RegimeDetector, RegimeSnapshot

        return {
            "RegimeDetector": RegimeDetector,
            "RegimeSnapshot": RegimeSnapshot,
        }[name]
    if name == "SessionGuard":
        from lumina_core.risk.session_guard import SessionGuard

        return SessionGuard
    if name == "PolicyEngine":
        from lumina_core.risk.policy_engine import PolicyEngine

        return PolicyEngine
    raise AttributeError(name)
