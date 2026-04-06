# CANONICAL IMPLEMENTATION – v50 Living Organism
import sys
from pathlib import Path

from lumina_core.runtime_context import RuntimeContext

from lumina_bible.workflows import dna_rewrite_daemon as _dna_rewrite_daemon
from lumina_bible.workflows import process_user_feedback as _process_user_feedback
from lumina_bible.workflows import reflect_on_trade as _reflect_on_trade


def health_check_market_open(app: RuntimeContext, symbol: str, regime: str) -> tuple[bool, str]:
    """
    FIRST CHECK: immediately after market open.
    Verify risk state is healthy before trading begins.
    
    Call this once at startup/market open to ensure system is ready for trading.
    
    Args:
        app: RuntimeContext
        symbol: Primary trading symbol (e.g., "MES")
        regime: Market regime (e.g., "trending_up")
    
    Returns:
        (healthy: bool, status_message: str)
    """
    if not app.engine.risk_controller:
        return False, "Risk controller not available"
    
    return app.engine.risk_controller.health_check_market_open(symbol, regime)


def check_pre_trade_risk(
    app: RuntimeContext,
    symbol: str,
    regime: str,
    proposed_risk: float,
) -> tuple[bool, str]:
    """
    Hard Risk Controller: LAST pre-trade check (fail-closed).
    
    Call this BEFORE any order submission to ensure:
    - Daily loss cap not breached
    - No consecutive loss streak
    - Per-instrument risk limits respected
    - Per-regime exposure limits respected
    - Kill-switch not engaged
    
    Args:
        app: RuntimeContext
        symbol: Instrument to trade (e.g., "MES")
        regime: Market regime (e.g., "trending_up")
        proposed_risk: Risk amount for trade (USD)
    
    Returns:
        (allowed: bool, reason: str)
    """
    if not app.engine.risk_controller:
        # Risk controller not initialized; fail closed
        return False, "Risk controller not available"
    
    return app.engine.risk_controller.check_can_trade(symbol, regime, proposed_risk)


def submit_order_with_risk_check(
    app: RuntimeContext,
    symbol: str,
    regime: str,
    proposed_risk: float,
    order_callback,
) -> bool | None:
    """
    Submit order ONLY after passing Hard Risk Controller.
    
    This wrapper ensures risk check is the LAST gate before order submission.
    
    Args:
        app: RuntimeContext
        symbol: Instrument
        regime: Market regime
        proposed_risk: Risk amount (USD)
        order_callback: Function to call if risk check passes
    
    Returns:
        Result of order_callback if check passes, None if blocked
    """
    allowed, reason = check_pre_trade_risk(app, symbol, regime, proposed_risk)
    
    if not allowed:
        app.logger.warning(f"Order blocked by risk controller: {reason}")
        return None
    
    # Risk check passed; proceed with order
    return order_callback()


def reflect_on_trade(app: RuntimeContext, pnl_dollars: float, entry_price: float, exit_price: float, position_qty: int) -> None:
    _reflect_on_trade(app, pnl_dollars, entry_price, exit_price, position_qty)
    
    # Record trade in risk controller
    if app.engine.risk_controller and app.engine.swarm:
        symbol = getattr(app.engine.swarm, 'current_symbol', 'UNKNOWN')
        regime = app.market_regime
        risk_taken = abs(position_qty * (exit_price - entry_price))
        app.engine.risk_controller.record_trade_result(symbol, regime, pnl_dollars, risk_taken)


def process_user_feedback(app: RuntimeContext, feedback_text: str, trade_data: dict | None = None) -> None:
    _process_user_feedback(app, feedback_text, trade_data)


def dna_rewrite_daemon(app: RuntimeContext) -> None:
    _dna_rewrite_daemon(app)
