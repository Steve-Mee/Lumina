# CANONICAL IMPLEMENTATION – v50 Living Organism
import sys
from pathlib import Path

from lumina_core.runtime_context import RuntimeContext
from lumina_core.engine.broker_bridge import Order, OrderResult

from lumina_bible.workflows import dna_rewrite_daemon as _dna_rewrite_daemon
from lumina_bible.workflows import process_user_feedback as _process_user_feedback
from lumina_bible.workflows import reflect_on_trade as _reflect_on_trade


def _refresh_regime_snapshot(app: RuntimeContext, regime: str | None = None) -> dict:
    reasoning_service = getattr(app.engine, "reasoning_service", None)
    if reasoning_service is not None and hasattr(reasoning_service, "refresh_regime_snapshot"):
        snapshot = reasoning_service.refresh_regime_snapshot()
        return snapshot.to_dict() if hasattr(snapshot, "to_dict") else dict(snapshot)

    existing = getattr(app.engine, "current_regime_snapshot", {})
    if isinstance(existing, dict) and existing:
        return existing

    label = str(regime or getattr(app, "market_regime", "NEUTRAL") or "NEUTRAL")
    fallback = {
        "label": label,
        "risk_state": "NORMAL",
        "adaptive_policy": {
            "risk_multiplier": 1.0,
            "cooldown_minutes": 30,
            "high_risk": False,
        },
    }
    app.engine.current_regime_snapshot = fallback
    return fallback


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

    snapshot = _refresh_regime_snapshot(app, regime)
    adaptive = snapshot.get("adaptive_policy", {}) if isinstance(snapshot, dict) else {}
    app.engine.risk_controller.apply_regime_override(
        regime=str(snapshot.get("label", regime or "NEUTRAL")),
        risk_state=str(snapshot.get("risk_state", "NORMAL")),
        risk_multiplier=float(adaptive.get("risk_multiplier", 1.0) or 1.0),
        cooldown_after_streak=int(adaptive.get("cooldown_minutes", 30) or 30),
    )

    return app.engine.risk_controller.health_check_market_open(symbol, str(snapshot.get("label", regime)))


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

    snapshot = _refresh_regime_snapshot(app, regime)
    adaptive = snapshot.get("adaptive_policy", {}) if isinstance(snapshot, dict) else {}
    app.engine.risk_controller.apply_regime_override(
        regime=str(snapshot.get("label", regime or "NEUTRAL")),
        risk_state=str(snapshot.get("risk_state", "NORMAL")),
        risk_multiplier=float(adaptive.get("risk_multiplier", 1.0) or 1.0),
        cooldown_after_streak=int(adaptive.get("cooldown_minutes", 30) or 30),
    )
    return app.engine.risk_controller.check_can_trade(symbol, str(snapshot.get("label", regime)), proposed_risk)


def submit_order_with_risk_check(
    app: RuntimeContext,
    symbol: str,
    regime: str,
    proposed_risk: float,
    order: Order,
) -> OrderResult | None:
    """
    Submit order ONLY after passing Hard Risk Controller.
    
    This wrapper ensures risk check is the LAST gate before order submission.
    
    Args:
        app: RuntimeContext
        symbol: Instrument
        regime: Market regime
        proposed_risk: Risk amount (USD)
        order: BrokerBridge order payload
    
    Returns:
        OrderResult if check passes, None if blocked
    """
    allowed, reason = check_pre_trade_risk(app, symbol, regime, proposed_risk)
    
    if not allowed:
        app.logger.warning(f"Order blocked by risk controller: {reason}")
        return None

    container = getattr(app, "container", None)
    if container is None or getattr(container, "broker", None) is None:
        raise RuntimeError("RuntimeContext.container.broker is not configured")

    # Risk check passed; proceed with broker bridge.
    return container.broker.submit_order(order)


def reflect_on_trade(app: RuntimeContext, pnl_dollars: float, entry_price: float, exit_price: float, position_qty: int) -> None:
    _reflect_on_trade(app, pnl_dollars, entry_price, exit_price, position_qty)
    
    # Record trade in risk controller
    if app.engine.risk_controller:
        symbol = getattr(app.engine.swarm, 'current_symbol', 'UNKNOWN')
        snapshot = _refresh_regime_snapshot(app, getattr(app, "market_regime", "NEUTRAL"))
        regime = str(snapshot.get("label", getattr(app, "market_regime", "NEUTRAL")))
        risk_taken = abs(position_qty * (exit_price - entry_price))
        app.engine.risk_controller.record_trade_result(symbol, regime, pnl_dollars, risk_taken)


def process_user_feedback(app: RuntimeContext, feedback_text: str, trade_data: dict | None = None) -> None:
    _process_user_feedback(app, feedback_text, trade_data)


def dna_rewrite_daemon(app: RuntimeContext) -> None:
    _dna_rewrite_daemon(app)
