# CANONICAL IMPLEMENTATION – v50 Living Organism
import sys
from pathlib import Path

from lumina_core.runtime_context import RuntimeContext
from lumina_core.engine.agent_contracts import apply_agent_policy_gateway
from lumina_core.engine.broker_bridge import Order, OrderResult
from lumina_core.order_gatekeeper import enforce_pre_trade_gate, resolve_regime_snapshot

from lumina_bible.workflows import dna_rewrite_daemon as _dna_rewrite_daemon
from lumina_bible.workflows import process_user_feedback as _process_user_feedback
from lumina_bible.workflows import reflect_on_trade as _reflect_on_trade


def _refresh_regime_snapshot(app: RuntimeContext, regime: str | None = None) -> dict:
    return resolve_regime_snapshot(app.engine, regime)


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
    return enforce_pre_trade_gate(
        app.engine,
        symbol=symbol,
        regime=regime,
        proposed_risk=proposed_risk,
    )


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

    mode = str(getattr(getattr(app.engine, "config", None), "trade_mode", "paper")).strip().lower()
    gateway_result = apply_agent_policy_gateway(
        signal=str(getattr(order, "side", "HOLD")).upper(),
        confluence_score=float(getattr(order, "metadata", {}).get("confluence_score", 1.0) if isinstance(getattr(order, "metadata", {}), dict) else 1.0),
        min_confluence=float(getattr(getattr(app.engine, "config", None), "min_confluence", 0.0) or 0.0),
        hold_until_ts=0.0,
        mode=mode,
        session_allowed=True,
        risk_allowed=True,
        lineage={
            "model_identifier": "trade-workers-wrapper",
            "prompt_version": "trade-workers-v1",
            "prompt_hash": "trade-workers",
            "policy_version": "agent-policy-gateway-v1",
            "provider_route": ["direct-wrapper"],
            "calibration_factor": 1.0,
        },
    )
    if str(gateway_result.get("signal", "HOLD")) == "HOLD" and str(getattr(order, "side", "HOLD")).upper() in {"BUY", "SELL"}:
        app.logger.warning(f"Order blocked by policy gateway: {gateway_result.get('reason')}")
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
