"""Admission chain step handlers for enforce_pre_trade_gate."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, cast

from lumina_core.order_gatekeeper.admission_risk_steps import (
    make_constitution_step,
    make_final_arbitration_step,
    make_risk_policy_step,
)
from lumina_core.order_gatekeeper.engine_helpers import (
    MODES_REQUIRING_EQUITY_SNAPSHOT,
    is_risk_reducing_side,
)
from lumina_core.order_gatekeeper.lineage_emitters import build_audit_payload
from lumina_core.order_gatekeeper.regime_session import session_guard_allows_trading
from lumina_core.risk.admission_chain import AdmissionContext


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
    risk_controller = ctx.risk_controller

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
        ADMISSION_STEP_RISK_POLICY: make_risk_policy_step(ctx),
        ADMISSION_STEP_FINAL_ARBITRATION: make_final_arbitration_step(ctx),
        ADMISSION_STEP_CONSTITUTION: make_constitution_step(ctx),
        ADMISSION_STEP_AUDIT_WRITE: _audit_write_step,
    }
