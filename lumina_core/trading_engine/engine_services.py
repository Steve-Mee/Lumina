from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class EngineServices:
    """Typed registry for optional runtime services attached to LuminaEngine."""

    local_engine: Any | None = None
    fast_path: Any | None = None
    backtester: Any | None = None
    advanced_backtester: Any | None = None
    rl_env: Any | None = None
    ppo_trainer: Any | None = None
    risk_controller: Any | None = None
    risk_policy: Any | None = None
    final_arbitration: Any | None = None
    equity_snapshot_provider: Any | None = None
    infinite_simulator: Any | None = None
    emotional_twin: Any | None = None
    emotional_twin_agent: Any | None = None
    swarm: Any | None = None
    validator: Any | None = None
    observability_service: Any | None = None
    session_guard: Any | None = None
    portfolio_var_allocator: Any | None = None
    decision_log: Any | None = None
    audit_log_service: Any | None = None
    reasoning_service: Any | None = None
    blackboard: Any | None = None
    event_bus: Any | None = None
    meta_agent_orchestrator: Any | None = None
    market_data_service: Any | None = None
    memory_service: Any | None = None
    operations_service: Any | None = None
    analysis_service: Any | None = None
    dashboard_service: Any | None = None
    visualization_service: Any | None = None
    reporting_service: Any | None = None
    trade_reconciler: Any | None = None
    dynamic_kelly_estimator: Any | None = None
    regime_detector: Any | None = None
