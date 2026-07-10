"""Pre-submit admission chain wiring for broker order submission."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from lumina_core.engine.errors import ErrorSeverity, LuminaError, log_structured

import lumina_core.broker.broker_bridge as _bb

if TYPE_CHECKING:
    from lumina_core.broker.broker_bridge.schemas import Order

logger = logging.getLogger(__name__)

def _resolve_trade_mode(engine: object | None) -> str:
    mode = str(getattr(getattr(engine, "config", None), "trade_mode", "paper") or "paper").strip().lower()
    return mode or "paper"


def audit_final_arbitration_reject(
    engine: object | None,
    *,
    mode: str,
    reason: str,
    order: Order | None = None,
) -> None:
    context = {
        "mode": str(mode),
        "reason": str(reason),
        "symbol": str(getattr(order, "symbol", "") or ""),
        "side": str(getattr(order, "side", "") or ""),
        "quantity": int(getattr(order, "quantity", 0) or 0),
    }
    log_structured(
        LuminaError(
            severity=ErrorSeverity.FATAL_MODE_VIOLATION,
            code="FINAL_ARBITRATION_GATE_REJECT",
            message=f"FinalArbitration rejected execution order: {reason}",
            context=context,
        )
    )
    service = getattr(engine, "audit_log_service", None) if engine is not None else None
    if service is None or not hasattr(service, "log_decision"):
        return
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision_id": f"final-arbitration-{uuid.uuid4().hex[:8]}",
        "stage": "final_arbitration",
        "mode": str(mode),
        "symbol": str(getattr(order, "symbol", "") or ""),
        "proposed_risk": float(
            getattr(getattr(order, "metadata", {}), "get", lambda *_: 0.0)("proposed_risk", 0.0) or 0.0
        ),
        "final_decision": "rejected",
        "reason": str(reason),
        "probability": 0.0,
        "expected_value": 0.0,
        "agents_involved": [{"agent_id": "final_arbitration_gate", "confidence": 1.0}],
        "var_impact": {},
        "monte_carlo": {},
    }
    try:
        service.log_decision(payload, is_real_mode=str(mode).lower() == "real")
    except Exception:
        logging.exception("Unhandled broad exception fallback in lumina_core/engine/broker_bridge.py:121")
        return


def run_final_arbitration(engine: object | None, order: "Order") -> tuple[bool, str]:
    mode = _resolve_trade_mode(engine)
    if engine is None:
        reason = "admission_engine_required"
        audit_final_arbitration_reject(engine, mode=mode, reason=reason, order=order)
        return False, reason
    try:
        metadata = order.metadata if isinstance(order.metadata, dict) else {}
        if bool(metadata.get("skip_admission_chain_recheck", False)):
            # Defensive deprecation trap (post 1.3.4 zero-trace hygiene).
            # The skip_admission_chain_recheck key is a pre-1.3.3 legacy bypass remnant (B-004).
            # It has had no functional effect since 1.3.3. The authoritative gate always runs.
            # Any code still emitting this key must be located and cleaned.
            logger.error(
                "LEGACY_BYPASS_FLAG_DETECTED: skip_admission_chain_recheck=True was set. "
                "This flag has had no effect since Phase 1.3.3. Remove the source that still emits this metadata key."
            )
            # Always fall through — no short-circuit remains in any mode.
        reference_price = float(metadata.get("reference_price", 0.0) or 0.0)
        stop_loss = float(order.stop_loss or 0.0)
        fallback_risk = abs(reference_price - stop_loss) if reference_price > 0 and stop_loss > 0 else 0.0
        proposed_risk = float(metadata.get("proposed_risk", fallback_risk) or fallback_risk)
        allowed, reason = _bb.enforce_pre_trade_gate(
            engine,
            symbol=str(order.symbol),
            regime=str(metadata.get("regime", "NEUTRAL") or "NEUTRAL"),
            proposed_risk=float(proposed_risk),
            order_side=str(order.side).upper(),
        )
        if not allowed:
            audit_final_arbitration_reject(engine, mode=mode, reason=str(reason), order=order)
        return bool(allowed), str(reason)
    except Exception as exc:
        logging.exception("Unhandled broad exception fallback in lumina_core/engine/broker_bridge.py:153")
        reason = f"admission_chain_error:{exc}"
        audit_final_arbitration_reject(engine, mode=mode, reason=reason, order=order)
        return False, reason
