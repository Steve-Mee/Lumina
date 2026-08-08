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
    # Track E / H1: durable reject row for reconstructability (even without audit service).
    if order is not None:
        try:
            _publish_admission_lineage_event(
                engine, order=order, mode=mode, reason=f"rejected:{reason}"
            )
        except Exception:
            logger.debug("admission.reject_lineage_publish_failed", exc_info=True)

    service = getattr(engine, "audit_log_service", None) if engine is not None else None
    if service is None or not hasattr(service, "log_decision"):
        return
    # Prefer lineage ctx on the order when present
    meta = getattr(order, "metadata", None) if order is not None else None
    ctx_id = ""
    if isinstance(meta, dict):
        ctx_id = str(meta.get("decision_context_id") or "")
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision_id": f"final-arbitration-{uuid.uuid4().hex[:8]}",
        "decision_context_id": ctx_id or None,
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
        # H1: single capital aperture — lineage contract before risk gate
        from lumina_core.risk.capital_aperture_lineage import ensure_order_lineage

        lineage_ok, lineage_reason = ensure_order_lineage(order, mode=mode)
        if not lineage_ok:
            audit_final_arbitration_reject(
                engine, mode=mode, reason=str(lineage_reason), order=order
            )
            return False, str(lineage_reason)

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
            # H1: also strip so the key cannot reappear downstream
            try:
                metadata.pop("skip_admission_chain_recheck", None)
            except Exception:
                pass
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

        # Best-effort typed bus emission + durable decision_log row (H1 coverage)
        _publish_admission_lineage_event(engine, order=order, mode=mode, reason="admitted")
        return True, str(reason)
    except Exception as exc:
        logging.exception("Unhandled broad exception fallback in lumina_core/engine/broker_bridge.py:153")
        reason = f"admission_chain_error:{exc}"
        audit_final_arbitration_reject(engine, mode=mode, reason=reason, order=order)
        return False, reason


def _publish_admission_lineage_event(
    engine: object | None,
    *,
    order: "Order",
    mode: str,
    reason: str,
) -> None:
    """Best-effort Event Bus publish — never raises, never blocks capital path."""
    if engine is None:
        return
    bus = getattr(engine, "event_bus", None) or getattr(engine, "bus", None)
    if bus is None or not hasattr(bus, "publish"):
        return
    try:
        from lumina_core.risk.capital_aperture_lineage import extract_order_lineage

        lin = extract_order_lineage(order)
        payload = {
            "mode": str(mode),
            "symbol": str(getattr(order, "symbol", "") or ""),
            "side": str(getattr(order, "side", "") or ""),
            "quantity": int(getattr(order, "quantity", 0) or 0),
            "decision_context_id": lin.get("decision_context_id"),
            "prev_hash": lin.get("prev_hash"),
            "reason": str(reason),
            "stage": "capital_aperture_admission",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        # Prefer typed validated publish (T10 capital bus lineage)
        if hasattr(bus, "publish_validated"):
            try:
                bus.publish_validated(
                    topic="risk.admission.lineage_checked",
                    producer="broker.admission",
                    payload=payload,
                    metadata={
                        "decision_context_id": payload.get("decision_context_id") or "",
                    },
                )
            except Exception:
                try:
                    bus.publish("risk.admission.lineage_checked", payload)
                except Exception:
                    pass
        else:
            bus.publish("risk.admission.lineage_checked", payload)

        # Durable audit row for aperture integrity / coverage measurement
        try:
            from lumina_core.risk.capital_aperture_lineage import append_lineage_audit_record

            root = None
            cfg = getattr(engine, "config", None)
            for attr in ("workspace_root", "state_dir", "project_root"):
                val = getattr(engine, attr, None) or getattr(cfg, attr, None)
                if val:
                    root = val
                    break
            append_lineage_audit_record(
                root,
                {
                    **payload,
                    "topic": "risk.admission.lineage_checked",
                    "event": "admission_lineage_checked",
                },
            )
        except Exception:
            pass
    except Exception:
        logger.debug("admission.lineage_publish_failed", exc_info=True)
