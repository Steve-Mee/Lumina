"""Thin orchestrator for the canonical pre-trade admission gate."""

from __future__ import annotations

import os
import uuid
from typing import Any, cast

from lumina_core.engine.errors import ErrorSeverity, LuminaError
from lumina_core.logging_utils import get_logger, log_gate_rejection, record_gate_rejection_monitoring
from lumina_core.order_gatekeeper.admission_steps import GateRuntimeContext, build_admission_step_handlers
import lumina_core.order_gatekeeper as _og
from lumina_core.order_gatekeeper.engine_helpers import (
    audit_trade_decision,
    record_mode_guard_block,
    resolve_blackboard,
    resolve_event_bus,
)
from lumina_core.order_gatekeeper.lineage_emitters import build_audit_payload, domain_event_fingerprint

from lumina_core.risk.admission_chain import AdmissionContext, default_chain_for_mode
from lumina_core.risk.mode_capabilities import resolve_mode_capabilities

_LOG = get_logger("lumina.trading.gate")








def enforce_pre_trade_gate(
    engine: Any,
    *,
    symbol: str,
    regime: str,
    proposed_risk: float,
    order_side: str | None = None,
) -> tuple[bool, str]:
    """Canonical pre-trade admission chain for risk-bearing order intents."""
    mode = str(getattr(getattr(engine, "config", None), "trade_mode", "paper") or "paper").strip().lower()
    decision_context_id = _resolve_decision_context_id(engine)
    _emit_gate_entry_lineage(
        engine,
        decision_context_id=decision_context_id,
        symbol=symbol,
        proposed_risk=proposed_risk,
        mode=mode,
        order_side=order_side,
    )

    capabilities = resolve_mode_capabilities(mode)
    blackboard = resolve_blackboard(engine)
    if (
        blackboard is not None
        and hasattr(blackboard, "is_proposal_approved_by_policy")
        and not bool(blackboard.is_proposal_approved_by_policy())
    ):
        raise LuminaError(
            severity=ErrorSeverity.FATAL_MODE_VIOLATION,
            code="CONTROL_PLANE_VIOLATION",
            message="Order blocked: proposal is not approved by control plane policy",
            context={"mode": mode, "symbol": symbol},
        )

    normalized_order_side = ""

    def _audit_or_fail_closed(payload: dict[str, Any], *, reason_code: str = "audit_fail_closed") -> tuple[bool, str]:
        ok = audit_trade_decision(engine, payload, mode=mode)
        if mode == "real" and not ok:
            record_mode_guard_block(engine, mode=mode, reason=reason_code)
            return False, "AUDIT FAIL-CLOSED: trade decision log write failed"
        return True, ""

    def _deny(
        reason_code: str,
        user_reason: str,
        *,
        var_payload: dict[str, Any] | None = None,
        mc_payload: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        try:
            log_gate_rejection(
                _LOG,
                gate_name=reason_code,
                reason=user_reason,
                current_value=proposed_risk,
                limit=None,
                symbol=str(symbol),
                side=normalized_order_side if normalized_order_side else str(order_side or ""),
                mode=mode,
                decision_context_id=decision_context_id,
                context={"var_payload": dict(var_payload or {}), "mc_payload": dict(mc_payload or {})},
            )
            record_gate_rejection_monitoring(
                gate_name=str(reason_code),
                reason=str(user_reason),
                mode=str(mode),
                symbol=str(symbol),
                side=str(normalized_order_side if normalized_order_side else str(order_side or "")),
                decision_context_id=str(decision_context_id),
            )
        except Exception:
            pass
        record_mode_guard_block(engine, mode=mode, reason=reason_code)
        audit_ok, audit_reason = _audit_or_fail_closed(
            build_audit_payload(
                engine,
                symbol=symbol,
                regime=str(regime),
                proposed_risk=float(proposed_risk),
                mode=mode,
                stage="policy_gate",
                final_decision="block",
                reason=str(user_reason),
                var_payload=var_payload,
                mc_payload=mc_payload,
            ),
        )
        if not audit_ok:
            return False, f"{user_reason} | {audit_reason}"
        return False, user_reason

    allow_stale = os.getenv("LUMINA_ALLOW_STALE_CONTRACTS", "false").strip().lower() == "true"
    if capabilities.requires_live_broker:
        stale_contract = _og.is_stale_contract_symbol(symbol)
        if stale_contract and not allow_stale:
            return _deny("stale_contract", f"Contract symbol stale/expired by calendar check: {symbol}")
        if stale_contract and allow_stale:
            _og.audit_stale_override(engine, symbol, mode)

        broker_ok, broker_reason = _og.broker_metadata_contract_allowed(engine, symbol)
        if not broker_ok:
            return _deny("broker_metadata_block", f"Contract blocked by broker metadata: {symbol} ({broker_reason})")

    risk_controller = getattr(engine, "risk_controller", None)
    if not risk_controller:
        return _deny("risk_controller_unavailable", "Risk controller not available")

    normalized_order_side = str(order_side or "").strip().upper()
    if normalized_order_side not in {"BUY", "SELL"}:
        return _deny("order_side_required", "Order side required for admission chain")

    gate_ctx = GateRuntimeContext(
        engine=engine,
        symbol=symbol,
        regime=regime,
        proposed_risk=proposed_risk,
        order_side=order_side,
        mode=mode,
        normalized_order_side=normalized_order_side,
        capabilities=capabilities,
        risk_controller=risk_controller,
    )

    def _audit_for_steps(payload: dict[str, Any], _reason_code: str = "audit_fail_closed") -> tuple[bool, str]:
        return _audit_or_fail_closed(payload)

    admission_context = AdmissionContext(
        engine=engine,
        mode=mode,
        symbol=str(symbol),
        regime=str(regime),
        proposed_risk=float(proposed_risk),
        order_side=order_side,
        step_handlers=build_admission_step_handlers(gate_ctx, audit_or_fail_closed=_audit_for_steps),
    )
    admission_context.metadata.setdefault("decision_context_id", decision_context_id)

    allowed, reason, trace = default_chain_for_mode(mode).run(admission_context)

    setattr(
        engine,
        "admission_chain_trace",
        [
            {
                "step_id": item.step_id,
                "ok": item.ok,
                "reason": item.reason,
                "bypassed": item.bypassed,
            }
            for item in trace.results
        ],
    )

    _emit_final_risk_verdict(
        engine,
        allowed=allowed,
        reason=reason,
        symbol=symbol,
        mode=mode,
        decision_context_id=decision_context_id,
        proposed_risk=proposed_risk,
        admission_context=admission_context,
        trace=trace,
    )

    if not allowed:
        reason_code = str(admission_context.metadata.get("deny_reason_code", f"admission_{trace.last_step_id}"))
        return _deny(
            reason_code,
            str(reason),
            var_payload=cast(dict[str, Any], admission_context.metadata.get("var_payload", {})),
            mc_payload=cast(dict[str, Any], admission_context.metadata.get("mc_payload", {})),
        )
    try:
        _LOG.info(
            "gate.passed",
            extra={
                "event_data": {
                    "event": "gate.passed",
                    "symbol": str(symbol),
                    "side": normalized_order_side,
                    "mode": mode,
                    "proposed_risk": float(proposed_risk),
                    "decision_context_id": decision_context_id,
                    "risk_reason": str(admission_context.metadata.get("risk_reason", reason or "OK")),
                }
            },
        )
    except Exception:
        pass
    return True, str(admission_context.metadata.get("risk_reason", reason or "OK"))

from lumina_core.order_gatekeeper.gate_lineage import _emit_final_risk_verdict, _emit_gate_entry_lineage, _resolve_decision_context_id  # noqa: F401

