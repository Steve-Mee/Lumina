from __future__ import annotations

import logging
from typing import FrozenSet

from lumina_core.risk.risk_policy import RiskPolicy, load_risk_policy
from lumina_core.risk.schemas import (
    ArbitrationState,
    ArbitrationCheckStep,
    ArbitrationResult,
    ArbitrationStatus,
    OrderIntent,
)
from lumina_core.risk.final_arbitration_state import (
    _MODES_REQUIRING_EQUITY_SNAPSHOT,
    build_constitution_payload as build_constitution_payload,
    build_current_state_from_engine as build_current_state_from_engine,
    build_order_intent_from_order as build_order_intent_from_order,
    evaluate_constitution_for_intent as evaluate_constitution_for_intent,
    is_strict_arbitration_mode as is_strict_arbitration_mode,
)

logger = logging.getLogger(__name__)

# Re-export for backward compatibility (tests/importers depend on these being here)
__all__ = [
    "FinalArbitration",
    "build_current_state_from_engine",
    "build_order_intent_from_order",
    "build_constitution_payload",
    "evaluate_constitution_for_intent",
    "is_strict_arbitration_mode",
]

_SKIPPABLE_INTERNAL_STEPS = frozenset({"constitution", "risk_policy"})














class FinalArbitration:
    def __init__(self, policy: RiskPolicy | None = None) -> None:
        self._explicit_policy = policy is not None
        self.policy = policy or load_risk_policy()

    def check(
        self,
        order_intent: OrderIntent,
        current_state: ArbitrationState,
        *,
        skip_internal_steps: FrozenSet[str] | None = None,
    ) -> ArbitrationResult:
        checks: list[ArbitrationCheckStep] = []
        if not isinstance(order_intent, OrderIntent) or not isinstance(current_state, ArbitrationState):
            return self._build_result(status="REJECTED", reason="arbitration_invalid_payload", checks=checks)
        state = current_state
        skipped = frozenset(skip_internal_steps or frozenset()).intersection(_SKIPPABLE_INTERNAL_STEPS)

        valid, reason = self._validate_shape(order_intent, state)
        checks.append(ArbitrationCheckStep(name="shape", ok=valid, reason=reason))
        if not valid:
            return self._build_result(status="REJECTED", reason=reason, checks=checks)

        if self._is_eod_risk_reducing_exit(order_intent, state):
            checks.append(ArbitrationCheckStep(name="eod_force_close_exit", ok=True, reason="risk_reducing_exit"))
            return self._build_result(status="APPROVED", reason="approved_eod_force_close_exit", checks=checks)

        if "real_equity_snapshot" in skipped:
            checks.append(
                ArbitrationCheckStep(name="real_equity_snapshot", ok=True, reason="skipped_by_admission_chain")
            )
        else:
            snapshot_ok, snapshot_reason = self._check_equity_snapshot_requirements(order_intent, state)
            checks.append(ArbitrationCheckStep(name="real_equity_snapshot", ok=snapshot_ok, reason=snapshot_reason))
            if not snapshot_ok:
                return self._build_result(status="REJECTED", reason=snapshot_reason, checks=checks)

        if "constitution" in skipped:
            checks.append(ArbitrationCheckStep(name="constitution", ok=True, reason="skipped_by_admission_chain"))
        else:
            c_ok, c_reason = self._check_constitution(order_intent, state)
            checks.append(ArbitrationCheckStep(name="constitution", ok=c_ok, reason=c_reason))
            if not c_ok:
                return self._build_result(status="REJECTED", reason=c_reason, checks=checks)

        if "risk_policy" in skipped:
            checks.append(ArbitrationCheckStep(name="risk_policy", ok=True, reason="skipped_by_admission_chain"))
        else:
            p_ok, p_reason = self._check_policy(order_intent, state)
            checks.append(ArbitrationCheckStep(name="risk_policy", ok=p_ok, reason=p_reason))
            if not p_ok:
                return self._build_result(status="REJECTED", reason=p_reason, checks=checks)

        a_ok, a_reason = self._check_account_state(state, order_intent)
        checks.append(ArbitrationCheckStep(name="account_state", ok=a_ok, reason=a_reason))
        if not a_ok:
            return self._build_result(status="REJECTED", reason=a_reason, checks=checks)

        return self._build_result(status="APPROVED", reason="approved", checks=checks)

    def check_order_intent(
        self,
        order_intent: OrderIntent,
        current_state: ArbitrationState,
        *,
        skip_internal_steps: FrozenSet[str] | None = None,
    ) -> ArbitrationResult:
        return self.check(
            order_intent=order_intent,
            current_state=current_state,
            skip_internal_steps=skip_internal_steps,
        )

    def _build_result(
        self,
        *,
        status: ArbitrationStatus,
        reason: str,
        checks: list[ArbitrationCheckStep],
    ) -> ArbitrationResult:
        violated_principle: str | None = None
        if reason.startswith("constitution_violation:"):
            violated_principle = reason.split(":", 1)[1] or None
        return ArbitrationResult(status=status, reason=reason, violated_principle=violated_principle, checks=checks)

    def _validate_shape(self, intent: OrderIntent, state: ArbitrationState) -> tuple[bool, str]:
        symbol = str(intent.instrument or "").strip()
        if not symbol:
            return False, "invalid_order_symbol"
        side = str(intent.side or "HOLD").upper()
        if side not in {"BUY", "SELL"}:
            return False, "invalid_order_side"
        qty = int(intent.quantity or 0)
        if qty <= 0:
            return False, "invalid_order_quantity"
        if not isinstance(state, ArbitrationState):
            return False, "invalid_current_state"
        return True, "ok"

    def _check_constitution(self, intent: OrderIntent, state: ArbitrationState) -> tuple[bool, str]:
        symbol = str(intent.instrument or "").strip().upper()
        resolved_policy = self._resolve_policy_for_intent(state=state, symbol=symbol)
        return evaluate_constitution_for_intent(intent=intent, state=state, resolved_policy=resolved_policy)

    def _check_policy(self, intent: OrderIntent, state: ArbitrationState) -> tuple[bool, str]:
        symbol = str(intent.instrument or "").strip().upper()
        resolved_policy = self._resolve_policy_for_intent(state=state, symbol=symbol)
        projected_risk = float(intent.proposed_risk or 0.0)
        if projected_risk <= 0.0:
            reference = float(intent.reference_price or 0.0)
            stop = float(intent.stop or 0.0)
            if reference > 0.0 and stop > 0.0:
                projected_risk = abs(reference - stop)
        if projected_risk > float(resolved_policy.max_open_risk_per_instrument):
            return False, "risk_limit_per_instrument_exceeded"

        sym_open = float(state.open_risk_by_symbol.get(symbol, 0.0) or 0.0)
        if sym_open + projected_risk > float(resolved_policy.max_open_risk_per_instrument):
            return False, "risk_limit_per_instrument_exceeded"

        total_open_risk = float(state.total_open_risk or 0.0)
        if total_open_risk + projected_risk > float(resolved_policy.max_total_open_risk):
            return False, "risk_limit_total_open_exceeded"

        daily_pnl = float(state.daily_pnl or 0.0)
        if daily_pnl <= float(resolved_policy.daily_loss_cap):
            return False, "daily_loss_cap_breached"

        if float(state.var_95_usd or 0.0) > float(resolved_policy.var_95_limit_usd):
            return False, "var_95_limit_breached"
        if float(state.var_99_usd or 0.0) > float(resolved_policy.var_99_limit_usd):
            return False, "var_99_limit_breached"
        if float(state.es_95_usd or 0.0) > float(resolved_policy.es_95_limit_usd):
            return False, "es_95_limit_breached"
        if float(state.es_99_usd or 0.0) > float(resolved_policy.es_99_limit_usd):
            return False, "es_99_limit_breached"

        return True, "ok"

    def _resolve_policy_for_intent(self, *, state: ArbitrationState, symbol: str) -> RiskPolicy:
        if self._explicit_policy:
            return self.policy
        mode = str(state.runtime_mode or self.policy.runtime_mode).strip().lower()
        normalized_symbol = str(symbol or "").strip().upper() or None
        try:
            return load_risk_policy(mode=mode, instrument=normalized_symbol, reload_config=True)
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/risk/final_arbitration.py:339")
            return self.policy

    def _check_account_state(self, state: ArbitrationState, intent: OrderIntent) -> tuple[bool, str]:
        mode = str(state.runtime_mode or self.policy.runtime_mode).strip().lower()
        if mode in _MODES_REQUIRING_EQUITY_SNAPSHOT and not bool(state.equity_snapshot_ok):
            if mode == "real" and self._is_risk_reducing_exit(intent=intent, state=state):
                return True, "ok_risk_reducing_exit"
            return False, str(state.equity_snapshot_reason or f"{mode}_equity_snapshot_required")
        equity = float(state.account_equity or 0.0)
        if equity <= 0.0:
            if is_strict_arbitration_mode(mode):
                return False, str(state.equity_snapshot_reason or "account_context_missing")
            return False, "account_equity_invalid"

        free_margin = float(state.free_margin or 0.0)
        used_margin = float(state.used_margin or 0.0)
        if free_margin <= 0.0 and used_margin > 0.0:
            return False, "margin_unavailable"
        margin_confidence = state.margin_confidence
        if margin_confidence is None:
            total_margin = free_margin + used_margin
            if total_margin > 0.0:
                margin_confidence = free_margin / total_margin
            else:
                margin_confidence = 1.0
        margin_confidence_value = float(margin_confidence or 0.0)
        if margin_confidence_value < float(self.policy.margin_min_confidence):
            return False, "margin_confidence_below_policy"

        drawdown_pct = float(state.drawdown_pct or 0.0)
        drawdown_kill_percent = float(state.drawdown_kill_percent or 25.0)
        if drawdown_pct >= drawdown_kill_percent:
            return False, "drawdown_kill_threshold_breached"
        return True, "ok"

    def _check_equity_snapshot_requirements(self, intent: OrderIntent, state: ArbitrationState) -> tuple[bool, str]:
        mode = str(state.runtime_mode or self.policy.runtime_mode).strip().lower()
        if mode not in _MODES_REQUIRING_EQUITY_SNAPSHOT:
            return True, "ok_non_real"
        if mode == "real" and self._is_risk_reducing_exit(intent=intent, state=state):
            return True, "ok_risk_reducing_exit"
        if bool(state.equity_snapshot_ok):
            return True, "ok"
        if mode == "real":
            return False, "real_equity_snapshot_required"
        return False, str(state.equity_snapshot_reason or f"{mode}_equity_snapshot_required")

    @staticmethod
    def _is_eod_risk_reducing_exit(intent: OrderIntent, state: ArbitrationState) -> bool:
        if str(intent.metadata.reason or "").strip().lower() == "eod_force_close":
            return True
        return FinalArbitration._is_risk_reducing_exit(intent=intent, state=state)

    @staticmethod
    def _is_risk_reducing_exit(intent: OrderIntent, state: ArbitrationState) -> bool:
        live_qty = int(state.live_position_qty or 0)
        side = str(intent.side or "").upper()
        return (live_qty > 0 and side == "SELL") or (live_qty < 0 and side == "BUY")


