"""Heavy risk / arbitration admission-step bodies (wired by admission_steps façade)."""

from __future__ import annotations

import logging
from typing import Any, Callable, Literal, cast

from lumina_core.order_gatekeeper.engine_helpers import resolve_event_bus, safe_log_warning
from lumina_core.order_gatekeeper.lineage_emitters import domain_event_fingerprint
from lumina_core.order_gatekeeper.regime_session import resolve_regime_snapshot
from lumina_core.risk.admission_chain import AdmissionContext
from lumina_core.risk.final_arbitration import (
    FinalArbitration,
    build_current_state_from_engine,
    is_strict_arbitration_mode,
)
from lumina_core.risk.risk_policy import load_risk_policy
from lumina_core.risk.schemas import OrderIntent, OrderIntentMetadata
from lumina_core.engine.errors import ErrorSeverity, LuminaError
import lumina_core.order_gatekeeper as _og


def _build_admission_intent(
    *,
    symbol: str,
    normalized_order_side: str,
    proposed_risk: float,
    regime: str,
) -> tuple[OrderIntent | None, str]:
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


def make_constitution_step(ctx: Any) -> Callable[[AdmissionContext], tuple[bool, str]]:
    engine = ctx.engine
    symbol = ctx.symbol
    regime = ctx.regime
    proposed_risk = ctx.proposed_risk
    mode = ctx.mode
    normalized_order_side = ctx.normalized_order_side

    def _constitution_step(_ctx: AdmissionContext) -> tuple[bool, str]:
        intent, intent_reason = _build_admission_intent(
            symbol=symbol,
            normalized_order_side=normalized_order_side,
            proposed_risk=proposed_risk,
            regime=regime,
        )
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
                "Unhandled broad exception fallback in lumina_core/order_gatekeeper/admission_risk_steps.py"
            )
            resolved_policy = load_risk_policy(mode=mode)
        return _og.evaluate_constitution_for_intent(intent=intent, state=state, resolved_policy=resolved_policy)

    return _constitution_step


def make_risk_policy_step(ctx: Any) -> Callable[[AdmissionContext], tuple[bool, str]]:
    engine = ctx.engine
    symbol = ctx.symbol
    regime = ctx.regime
    proposed_risk = ctx.proposed_risk
    mode = ctx.mode
    capabilities = ctx.capabilities
    risk_controller = ctx.risk_controller

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

    return _risk_policy_step


def make_final_arbitration_step(ctx: Any) -> Callable[[AdmissionContext], tuple[bool, str]]:
    engine = ctx.engine
    symbol = ctx.symbol
    regime = ctx.regime
    proposed_risk = ctx.proposed_risk
    mode = ctx.mode
    normalized_order_side = ctx.normalized_order_side

    def _final_arbitration_step(_ctx: AdmissionContext) -> tuple[bool, str]:
        from lumina_core.logging_utils import get_logger

        log = get_logger("lumina.trading.gate")
        intent, intent_reason = _build_admission_intent(
            symbol=symbol,
            normalized_order_side=normalized_order_side,
            proposed_risk=proposed_risk,
            regime=regime,
        )
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

    return _final_arbitration_step
