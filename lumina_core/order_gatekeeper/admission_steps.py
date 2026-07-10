"""Admission chain step handlers for enforce_pre_trade_gate."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Literal, cast

from lumina_core.engine.errors import ErrorSeverity, LuminaError
from lumina_core.order_gatekeeper.engine_helpers import (
    MODES_REQUIRING_EQUITY_SNAPSHOT,
    is_risk_reducing_side,
    safe_log_warning,
)
from lumina_core.order_gatekeeper.lineage_emitters import (
    build_audit_payload,
    domain_event_fingerprint,
)
from lumina_core.order_gatekeeper.regime_session import (
    resolve_regime_snapshot,
    session_guard_allows_trading,
)
from lumina_core.order_gatekeeper.engine_helpers import resolve_event_bus
from lumina_core.risk.admission_chain import AdmissionContext
import lumina_core.order_gatekeeper as _og
from lumina_core.risk.final_arbitration import (
    FinalArbitration,
    build_current_state_from_engine,
    is_strict_arbitration_mode,
)
from lumina_core.risk.risk_policy import load_risk_policy
from lumina_core.risk.schemas import OrderIntent, OrderIntentMetadata


@dataclass
class GateRuntimeContext:
    engine: Any
    symbol: str
    regime: str
    proposed_risk: float
    order_side: str | None
    mode: str
    normalized_order_side: str
    capabilities: Any
    risk_controller: Any


AuditFn = Callable[[dict[str, Any], str], tuple[bool, str]]


def build_admission_step_handlers(
    ctx: GateRuntimeContext,
    *,
    audit_or_fail_closed: AuditFn,
) -> dict[str, Callable[[AdmissionContext], tuple[bool, str]]]:
    engine = ctx.engine
    symbol = ctx.symbol
    regime = ctx.regime
    proposed_risk = ctx.proposed_risk
    order_side = ctx.order_side
    mode = ctx.mode
    normalized_order_side = ctx.normalized_order_side
    capabilities = ctx.capabilities
    risk_controller = ctx.risk_controller

    def _build_admission_intent() -> tuple[OrderIntent | None, str]:
        return (
            OrderIntent(
                instrument=str(symbol),
                side=cast(Literal["BUY", "SELL"], normalized_order_side),
                quantity=1,
                reference_price=0.0,
                proposed_risk=float(abs(float(proposed_risk))),
                stop=0.0,
                target=0.0,
                regime=str(regime or "NEUTRAL"),
                confluence_score=0.0,
                confidence=0.0,
                source_agent="admission_chain",
                metadata=OrderIntentMetadata(reason="admission_chain"),
            ),
            "ok",
        )

    def _constitution_step(_ctx: AdmissionContext) -> tuple[bool, str]:
        intent, intent_reason = _build_admission_intent()
        if intent is None:
            _ctx.metadata["deny_reason_code"] = "admission_intent_missing"
            return False, str(intent_reason)
        state = build_current_state_from_engine(engine)
        try:
            resolved_policy = load_risk_policy(
                mode=mode, instrument=str(symbol).strip().upper() or None, reload_config=True
            )
        except Exception:
            logging.exception(
                "Unhandled broad exception fallback in lumina_core/order_gatekeeper/admission_steps.py"
            )
            resolved_policy = load_risk_policy(mode=mode)
        return _og.evaluate_constitution_for_intent(intent=intent, state=state, resolved_policy=resolved_policy)

    def _emit_risk_allocation_decision(
        _ctx: AdmissionContext,
        approved: bool,
        reason: str,
        var_payload: dict[str, Any],
        mc_payload: dict[str, Any],
    ) -> None:
        try:
            bus = resolve_event_bus(engine)
            if bus is not None and hasattr(bus, "publish_validated"):
                from lumina_core.agent_orchestration.schemas import RiskVerdict

                verdict = RiskVerdict(
                    approved=bool(approved),
                    reason=str(reason)[:300] if reason else None,
                    limit=str(_ctx.metadata.get("deny_reason_code", "")) or "risk_policy",
                    value=float(proposed_risk),
                )
                meta = {
                    "symbol": str(symbol),
                    "mode": str(mode),
                    "decision_context_id": str(_ctx.metadata.get("decision_context_id", "")),
                    "resolved_regime": str(_ctx.metadata.get("resolved_regime", "")),
                    "var_payload": var_payload,
                    "mc_payload": mc_payload,
                }

                pending = getattr(engine, "_pending_lineage_refs", {}).get("gate_entry")
                if pending and pending.get("hash"):
                    meta["prev_hash"] = pending["hash"]
                published = bus.publish_validated(
                    topic="risk.policy.decision",
                    producer="order_gatekeeper.risk_policy_step",
                    payload=verdict.model_dump(mode="json"),
                    metadata=meta,
                )
                seq = getattr(published, "metadata", {}).get("sequence") if published else None
                if seq:
                    _ctx.metadata["risk_policy_decision_ref"] = f"seq:{seq}"
                try:
                    alloc_hash = domain_event_fingerprint(published)
                    _ctx.metadata["risk_policy_decision_hash"] = alloc_hash
                except Exception:
                    pass
                _ctx.metadata["risk_policy_decision_emitted"] = True
        except Exception:
            pass

    def _risk_policy_step(_ctx: AdmissionContext) -> tuple[bool, str]:
        snapshot = resolve_regime_snapshot(engine, regime)
        adaptive = snapshot.get("adaptive_policy", {}) if isinstance(snapshot, dict) else {}
        resolved_regime = str(snapshot.get("label", regime or "NEUTRAL"))
        _ctx.metadata["resolved_regime"] = resolved_regime
        risk_controller.apply_regime_override(
            regime=resolved_regime,
            risk_state=str(snapshot.get("risk_state", "NORMAL")),
            risk_multiplier=float(adaptive.get("risk_multiplier", 1.0) or 1.0),
            cooldown_after_streak=int(adaptive.get("cooldown_minutes", 30) or 30),
        )
        if hasattr(risk_controller, "record_regime_snapshot"):
            risk_controller.record_regime_snapshot(snapshot)
        if hasattr(risk_controller, "record_regime_detector_history"):
            reasoning_service = getattr(engine, "reasoning_service", None)
            regime_detector = getattr(reasoning_service, "regime_detector", None)
            market_df = getattr(engine, "ohlc_1min", None)
            instrument = str(getattr(getattr(engine, "config", None), "instrument", symbol) or symbol)
            risk_controller.record_regime_detector_history(
                detector=regime_detector,
                market_df=market_df,
                instrument=instrument,
            )

        if hasattr(risk_controller, "check_var_es_pre_trade"):
            var_result = risk_controller.check_var_es_pre_trade(float(proposed_risk))
            if not isinstance(var_result, tuple) or len(var_result) < 2:
                raise LuminaError(
                    severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                    code="VAR_GATE_RESULT_INVALID",
                    message="check_var_es_pre_trade must return tuple(bool, reason, payload?).",
                )
            var_ok = bool(var_result[0])
            var_reason = str(var_result[1])
            var_payload: dict[str, Any] = (
                dict(var_result[2]) if len(var_result) >= 3 and isinstance(var_result[2], dict) else {}
            )

            mc_ok = True
            mc_reason = "mc_gate_not_configured"
            mc_payload: dict[str, Any] = {}
            if hasattr(risk_controller, "check_monte_carlo_drawdown_pre_trade"):
                mc_result = risk_controller.check_monte_carlo_drawdown_pre_trade(float(proposed_risk))
                if not isinstance(mc_result, tuple) or len(mc_result) < 2:
                    raise LuminaError(
                        severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                        code="MC_GATE_RESULT_INVALID",
                        message="check_monte_carlo_drawdown_pre_trade must return tuple(bool, reason, payload?).",
                    )
                mc_ok = bool(mc_result[0])
                mc_reason = str(mc_result[1])
                if len(mc_result) >= 3 and isinstance(mc_result[2], dict):
                    mc_payload = dict(mc_result[2])
            _ctx.metadata["var_payload"] = var_payload
            _ctx.metadata["mc_payload"] = mc_payload

            if capabilities.risk_enforced and not bool(var_ok):
                _ctx.metadata["deny_reason_code"] = "risk_var_es"
                _emit_risk_allocation_decision(_ctx, False, var_reason, var_payload, mc_payload)
                return False, str(var_reason)
            if capabilities.risk_enforced and not bool(mc_ok):
                _ctx.metadata["deny_reason_code"] = "risk_mc_drawdown"
                _emit_risk_allocation_decision(_ctx, False, mc_reason, var_payload, mc_payload)
                return False, str(mc_reason)
            if not capabilities.risk_enforced and not bool(var_ok):
                safe_log_warning(
                    engine,
                    f"RISK_VAR_ES_ADVISORY,mode={mode},symbol={symbol},reason={var_reason}",
                )
            if not capabilities.risk_enforced and not bool(mc_ok):
                safe_log_warning(
                    engine,
                    f"RISK_MC_DRAWDOWN_ADVISORY,mode={mode},symbol={symbol},reason={mc_reason}",
                )

        risk_ok, risk_reason = risk_controller.check_can_trade(symbol, resolved_regime, proposed_risk)
        _ctx.metadata["risk_reason"] = str(risk_reason)
        if capabilities.risk_enforced:
            if not bool(risk_ok):
                _ctx.metadata["deny_reason_code"] = f"risk_{risk_reason}"
                _emit_risk_allocation_decision(
                    _ctx, False, risk_reason, _ctx.metadata.get("var_payload", {}), _ctx.metadata.get("mc_payload", {})
                )
                return False, str(risk_reason)
            _emit_risk_allocation_decision(
                _ctx, True, risk_reason, _ctx.metadata.get("var_payload", {}), _ctx.metadata.get("mc_payload", {})
            )
            return True, str(risk_reason)

        if not bool(risk_ok):
            safe_log_warning(
                engine,
                f"RISK_ADVISORY,mode={mode},symbol={symbol},reason={risk_reason}",
            )
        _emit_risk_allocation_decision(
            _ctx, bool(risk_ok), risk_reason, _ctx.metadata.get("var_payload", {}), _ctx.metadata.get("mc_payload", {})
        )
        return True, str(risk_reason)

    def _equity_snapshot_step(_ctx: AdmissionContext) -> tuple[bool, str]:
        if mode not in MODES_REQUIRING_EQUITY_SNAPSHOT:
            setattr(engine, "equity_snapshot_ok", True)
            setattr(engine, "equity_snapshot_reason", "not_required_non_real")
            return True, "not_required_non_real"

        snapshot_ok = False
        snapshot_reason = f"{mode}_equity_snapshot_required"
        snapshot_source = ""
        provider = getattr(engine, "equity_snapshot_provider", None)
        if provider is not None and callable(getattr(provider, "get_snapshot", None)):
            try:
                snapshot = provider.get_snapshot()
                snapshot_source = str(getattr(snapshot, "source", "") or "")
                snapshot_fresh = bool(getattr(snapshot, "is_fresh", False))
                snapshot_ok = bool(getattr(snapshot, "ok", False)) and snapshot_fresh
                snapshot_reason = str(getattr(snapshot, "reason_code", "real_equity_snapshot_required"))
                if bool(getattr(snapshot, "ok", False)) and not snapshot_fresh:
                    snapshot_reason = "equity_snapshot_stale"
                if snapshot_ok:
                    engine.account_equity = float(
                        getattr(snapshot, "equity_usd", engine.account_equity) or engine.account_equity
                    )
                    engine.available_margin = float(getattr(snapshot, "available_margin_usd", 0.0) or 0.0)
                    engine.positions_margin_used = float(getattr(snapshot, "used_margin_usd", 0.0) or 0.0)
                    margin_tracker = getattr(getattr(risk_controller, "state", None), "margin_tracker", None)
                    if margin_tracker is not None:
                        margin_tracker.account_equity = float(engine.account_equity)
                setattr(engine, "equity_snapshot_ok", bool(snapshot_ok))
                setattr(engine, "equity_snapshot_reason", snapshot_reason)
            except Exception:
                logging.exception(
                    "Unhandled broad exception fallback in lumina_core/order_gatekeeper/admission_steps.py"
                )
                snapshot_ok = False
                snapshot_reason = "equity_snapshot_provider_error"
                setattr(engine, "equity_snapshot_ok", False)
                setattr(engine, "equity_snapshot_reason", snapshot_reason)
        if mode == "real" and not snapshot_ok:
            snapshot_reason = "real_equity_snapshot_required"
            setattr(engine, "equity_snapshot_reason", snapshot_reason)
        if snapshot_ok:
            return True, str(snapshot_reason)
        if mode == "real" and is_risk_reducing_side(engine=engine, order_side=order_side):
            return True, "real_snapshot_bypassed_for_risk_reducing_exit"
        return (
            False,
            (
                "REAL mode requires fresh equity snapshot "
                f"({snapshot_reason}, source={snapshot_source or 'unknown'})"
                if mode == "real"
                else (
                    f"{mode.upper()} mode requires fresh equity snapshot "
                    f"({snapshot_reason}, source={snapshot_source or 'unknown'})"
                )
            ),
        )

    def _final_arbitration_step(_ctx: AdmissionContext) -> tuple[bool, str]:
        from lumina_core.logging_utils import get_logger

        log = get_logger("lumina.trading.gate")
        intent, intent_reason = _build_admission_intent()
        if intent is None:
            _ctx.metadata["deny_reason_code"] = "admission_intent_missing"
            _ctx.metadata["final_arbitration_approved"] = False
            return False, str(intent_reason)

        state = build_current_state_from_engine(engine)
        arbitration = getattr(engine, "final_arbitration", None)
        if arbitration is None and is_strict_arbitration_mode(mode):
            _ctx.metadata["final_arbitration_approved"] = False
            _ctx.metadata["deny_reason_code"] = "final_arbitration_unavailable"
            return False, f"FinalArbitration blocked order: final_arbitration_unavailable [mode={str(mode).upper()}]"
        if arbitration is None:
            arbitration = FinalArbitration(load_risk_policy(mode=mode))
        result = arbitration.check_order_intent(
            intent,
            state,
            skip_internal_steps=frozenset(
                {
                    "real_equity_snapshot",
                    "constitution",
                    "risk_policy",
                }
            ),
        )
        _ctx.metadata["final_arbitration_approved"] = bool(result.status == "APPROVED")

        event_bus = getattr(engine, "event_bus", None)
        if event_bus is not None:
            try:
                decision_context_id = str(_ctx.metadata.get("decision_context_id", "")) or "unknown"
                if hasattr(result, "model_dump"):
                    payload = result.model_dump(mode="json")
                else:
                    payload = {
                        k: getattr(result, k)
                        for k in ("status", "reason", "violated_principle", "checks")
                        if hasattr(result, k)
                    }

                policy_ref = _ctx.metadata.get("risk_policy_decision_ref") or _ctx.metadata.get("policy_decision_ref")
                alloc_hash = _ctx.metadata.get("risk_policy_decision_hash")

                meta = {
                    "decision_context_id": decision_context_id,
                    "symbol": str(symbol),
                    "mode": str(mode),
                }
                if policy_ref:
                    meta["policy_decision_ref"] = policy_ref
                if alloc_hash:
                    meta["prev_hash"] = alloc_hash

                published_arb = event_bus.publish_validated(
                    topic="risk.final_arbitration.result",
                    producer="order_gatekeeper",
                    payload=payload,
                    metadata=meta,
                )
                seq = getattr(published_arb, "metadata", {}).get("sequence") if published_arb else None
                if seq:
                    _ctx.metadata["final_arbitration_ref"] = f"seq:{seq}"
            except Exception:
                log.exception("Failed to publish risk.final_arbitration.result (non-fatal)")

        if result.status != "APPROVED":
            _ctx.metadata["deny_reason_code"] = "final_arbitration_reject"
            return False, str(result.reason)
        return True, str(result.reason)

    def _session_equity_sync_step(_ctx: AdmissionContext) -> tuple[bool, str]:
        session_ok, session_reason = session_guard_allows_trading(engine)
        if not session_ok:
            session_guard = getattr(engine, "session_guard", None)
            next_open = (
                session_guard.next_open()
                if (session_guard is not None and hasattr(session_guard, "next_open"))
                else None
            )
            suffix = f" | next_open={next_open.isoformat()}" if next_open is not None else ""
            return False, f"Session guard blocked order: {session_reason}{suffix}"
        return _equity_snapshot_step(_ctx)

    def _audit_write_step(_ctx: AdmissionContext) -> tuple[bool, str]:
        resolved_regime = str(_ctx.metadata.get("resolved_regime", regime or "NEUTRAL"))
        audit_ok, audit_reason = audit_or_fail_closed(
            build_audit_payload(
                engine,
                symbol=symbol,
                regime=resolved_regime,
                proposed_risk=float(proposed_risk),
                mode=mode,
                stage="admission_chain",
                final_decision="allow",
                reason=str(_ctx.metadata.get("risk_reason", "approved")),
                var_payload=cast(dict[str, Any], _ctx.metadata.get("var_payload", {})),
                mc_payload=cast(dict[str, Any], _ctx.metadata.get("mc_payload", {})),
            ),
        )
        if not audit_ok:
            _ctx.metadata["deny_reason_code"] = "audit_fail_closed"
            return False, str(audit_reason)
        return True, str(_ctx.metadata.get("risk_reason", "OK"))

    from lumina_core.risk.admission_chain import (
        ADMISSION_STEP_AUDIT_WRITE,
        ADMISSION_STEP_CONSTITUTION,
        ADMISSION_STEP_FINAL_ARBITRATION,
        ADMISSION_STEP_RISK_POLICY,
        ADMISSION_STEP_SESSION_EQUITY_SYNC,
    )

    return {
        ADMISSION_STEP_SESSION_EQUITY_SYNC: _session_equity_sync_step,
        ADMISSION_STEP_RISK_POLICY: _risk_policy_step,
        ADMISSION_STEP_FINAL_ARBITRATION: _final_arbitration_step,
        ADMISSION_STEP_CONSTITUTION: _constitution_step,
        ADMISSION_STEP_AUDIT_WRITE: _audit_write_step,
    }