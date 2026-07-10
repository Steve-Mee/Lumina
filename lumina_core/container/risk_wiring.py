"""Risk, reconciliation, and portfolio allocation wiring."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lumina_core.engine import PerformanceValidator
from lumina_core.engine.portfolio_var_allocator import PortfolioVaRAllocator
from lumina_core.engine.trade_reconciler import TradeReconciler

if TYPE_CHECKING:
    from lumina_core.container import ApplicationContainer


def wire_risk_services(container: "ApplicationContainer") -> None:
    container.performance_validator = PerformanceValidator(
        engine=container.engine,
        market_data_service=container.market_data_service,
        ppo_trainer=container.ppo_trainer,
    )
    container.engine.validator = container.performance_validator
    container.trade_reconciler = TradeReconciler(engine=container.engine)

    if container.engine.risk_controller is None:
        raise RuntimeError("Engine risk_controller was not initialized")

    portfolio_var_cfg = getattr(container.config, "portfolio_var", {})
    if not isinstance(portfolio_var_cfg, dict):
        portfolio_var_cfg = {}
    container.portfolio_var_allocator = PortfolioVaRAllocator(
        valuation_engine=container.engine.valuation_engine,
        swarm_manager=container.swarm_manager,
        observability_service=container.observability_service,
        config=portfolio_var_cfg,
    )
    container.engine.portfolio_var_allocator = container.portfolio_var_allocator
    container.engine.risk_controller.portfolio_var_allocator = container.portfolio_var_allocator
    container.risk_controller = container.engine.risk_controller