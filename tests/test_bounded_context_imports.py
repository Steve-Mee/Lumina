from __future__ import annotations

import pytest

from lumina_core.agent_orchestration import AgentBlackboard, EventBus
from lumina_core.engine.agent_blackboard import AgentBlackboard as EngineAgentBlackboard
from lumina_core.engine.lumina_engine import LuminaEngine as EngineLuminaEngine
from lumina_core.engine.risk_orchestrator import RiskOrchestrator as EngineRiskOrchestrator
from lumina_core.risk import HardRiskController, RiskLimits, RiskState, risk_limits_from_config
from lumina_core.risk.orchestration import RiskOrchestrator
from lumina_core.risk.risk_allocator import RiskAllocatorMixin
from lumina_core.risk.risk_gates import RiskGatesMixin
from lumina_core.risk.risk_controller import HardRiskController as ContextHardRiskController
from lumina_core.trading_engine import LuminaEngine


@pytest.mark.unit
def test_trading_engine_context_reexports_lumina_engine() -> None:
    assert LuminaEngine is EngineLuminaEngine


@pytest.mark.unit
def test_risk_context_exports_core_types() -> None:
    assert HardRiskController is ContextHardRiskController
    assert RiskLimits is not None
    assert RiskState is not None
    assert risk_limits_from_config is not None


@pytest.mark.unit
def test_risk_context_exports_mixins() -> None:
    assert RiskAllocatorMixin is not None
    assert RiskGatesMixin is not None


@pytest.mark.unit
def test_risk_context_orchestrator_is_canonical_and_engine_module_reexports() -> None:
    assert RiskOrchestrator is EngineRiskOrchestrator


@pytest.mark.unit
def test_agent_orchestration_context_reexports_blackboard_and_event_bus() -> None:
    assert AgentBlackboard is EngineAgentBlackboard
    assert EventBus is not None
