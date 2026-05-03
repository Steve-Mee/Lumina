from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import FrozenSet, Literal, cast

from lumina_core.engine.errors import ErrorSeverity, LuminaError, log_structured
from lumina_core.risk.risk_policy import RiskPolicy, load_risk_policy
from lumina_core.risk.schemas import (
    ArbitrationState,
    ArbitrationCheckStep,
    ArbitrationResult,
    ArbitrationStatus,
    OrderIntent,
    OrderIntentMetadata,
)
from lumina_core.safety.trading_constitution import TRADING_CONSTITUTION

logger = logging.getLogger(__name__)
STRICT_ARBITRATION_MODES = frozenset({"real", "paper", "sim_real_guard"})
_MODES_REQUIRING_EQUITY_SNAPSHOT = frozenset({"real", "paper", "sim_real_guard"})
_SKIPPABLE_INTERNAL_STEPS = frozenset({"constitution", "risk_policy"})


def is_strict_arbitration_mode(mode: str) -> bool:
    return str(mode or "").strip().lower() in STRICT_ARBITRATION_MODES


def _to_float(value: object, default: float = 0.0) -> float:
    if value is None:
        return float(default)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return float(default)
    try:
        return float(cast(float, value))
    except (TypeError, ValueError):
        return float(default)


def build_constitution_payload(
    *,
    intent: OrderIntent,
    state: ArbitrationState,
    resolved_policy: RiskPolicy,
) -> dict[str, object]:
    intent_payload = intent.model_dump(mode="json", by_alias=True)
    constitution_payload: dict[str, object] = {
        "order_intent": intent_payload,
        "hyperparam_suggestion": {
            "kelly_fraction": float(resolved_policy.kelly_fraction),
            "max_risk_percent": float(
                resolved_policy.max_total_open_risk / max(float(state.account_equity or 1.0), 1.0)
            )
            * 100.0,
            "daily_loss_cap": float(resolved_policy.daily_loss_cap),
        },
    }
    constitution_payload.update(intent_payload)
    return constitution_payload


def evaluate_constitution_for_intent(
    *,
    intent: OrderIntent,
    state: ArbitrationState,
    resolved_policy: RiskPolicy,
) -> tuple[bool, str]:
    mode = str(state.runtime_mode or resolved_policy.runtime_mode).strip().lower()
    try:
        violations = TRADING_CONSTITUTION.audit(
            json.dumps(
                build_constitution_payload(intent=intent, state=state, resolved_policy=resolved_policy),
                ensure_ascii=True,
                sort_keys=True,
            ),
            mode=mode,
            raise_on_fatal=False,
        )
    except Exception:
        logging.exception("Unhandled broad exception fallback in lumina_core/risk/final_arbitration.py:62")
        return False, "constitution_check_error"
    fatals = [v for v in violations if str(getattr(v, "severity", "")).lower() == "fatal"]
    if fatals:
        return False, f"constitution_violation:{fatals[0].principle_name}"
    return True, "ok"


def build_order_intent_from_order(order: object, *, dream_snapshot: Mapping[str, object] | None = None) -> OrderIntent:
    snapshot = dict(dream_snapshot or {})
    metadata = getattr(order, "metadata", {})
    metadata = metadata if isinstance(metadata, dict) else {}
    reference_price = float(metadata.get("reference_price", 0.0) or 0.0)
    stop = float(getattr(order, "stop_loss", 0.0) or 0.0)
    side_text = str(getattr(order, "side", "HOLD") or "HOLD").upper()
    side = cast(Literal["BUY", "SELL"], side_text)
    proposed_risk = abs(reference_price - stop) if reference_price > 0.0 and stop > 0.0 else 0.0
    return OrderIntent(
        instrument=str(getattr(order, "symbol", "") or ""),
        side=side,
        quantity=int(getattr(order, "quantity", 0) or 0),
        order_type=str(getattr(order, "order_type", "MARKET") or "MARKET"),
        stop=stop,
        target=float(getattr(order, "take_profit", 0.0) or 0.0),
        reference_price=reference_price,
        proposed_risk=float(metadata.get("proposed_risk", proposed_risk) or proposed_risk),
        regime=str(snapshot.get("regime", metadata.get("regime", "NEUTRAL")) or "NEUTRAL"),
        confluence_score=_to_float(snapshot.get("confluence_score", metadata.get("confluence_score", 0.0))),
        confidence=_to_float(snapshot.get("confidence", metadata.get("confidence", 0.0))),
        source_agent=str(snapshot.get("source_agent", metadata.get("source_agent", "unknown")) or "unknown"),
        disable_risk_controller=bool(metadata.get("disable_risk_controller", False)),
        metadata=OrderIntentMetadata(reason=str(metadata.get("reason", "") or "")),
    )


def build_current_state_from_engine(engine: object) -> ArbitrationState:
    app = getattr(engine, "app", None)
    runtime_mode = str(getattr(getattr(engine, "config", None), "trade_mode", "paper") or "paper").strip().lower()
    risk_controller = getattr(engine, "risk_controller", None)
    risk_state = getattr(risk_controller, "state", None)
    open_risk_by_symbol = getattr(risk_state, "open_risk_by_symbol", {}) if risk_state is not None else {}
    total_open_risk = float(sum(float(v or 0.0) for v in dict(open_risk_by_symbol).values()))
    realized_pnl = getattr(engine, "realized_pnl_today", None)
    if realized_pnl is None and app is not None:
        realized_pnl = getattr(app, "realized_pnl_today", 0.0)
    account_equity = getattr(engine, "account_equity", None)
    if account_equity is None and app is not None:
        account_equity = getattr(app, "account_equity", 0.0)
    if account_equity is None:
        if is_strict_arbitration_mode(runtime_mode):
            account_equity = 0.0
        else:
            account_equity = 50_000.0
    free_margin = getattr(engine, "available_margin", None)
    if free_margin is None and app is not None:
        free_margin = getattr(app, "available_margin", 0.0)
    used_margin = getattr(engine, "positions_margin_used", None)
    if used_margin is None and app is not None:
        used_margin = getattr(app, "positions_margin_used", 0.0)
    live_position_qty = getattr(engine, "live_position_qty", None)
    if live_position_qty is None and app is not None:
        live_position_qty = getattr(app, "sim_position_qty", 0)
    equity_snapshot_ok = True
    equity_snapshot_reason = "not_required_non_real"
    equity_snapshot_source = ""
    equity_snapshot_age_sec = 0.0
    if runtime_mode in _MODES_REQUIRING_EQUITY_SNAPSHOT:
        equity_snapshot_ok = False
        equity_snapshot_reason = "provider_unavailable"
        provider = getattr(engine, "equity_snapshot_provider", None)
        if provider is not None and callable(getattr(provider, "get_snapshot", None)):
            try:
                snapshot = provider.get_snapshot()
                equity_snapshot_source = str(getattr(snapshot, "source", "") or "")
                equity_snapshot_age_sec = float(getattr(snapshot, "age_seconds", 0.0) or 0.0)
                snapshot_fresh = bool(getattr(snapshot, "is_fresh", False))
                snapshot_ok = bool(getattr(snapshot, "ok", False))
                snapshot_reason = str(
                    getattr(snapshot, "reason_code", "snapshot_unavailable") or "snapshot_unavailable"
                )
                if snapshot_ok and snapshot_fresh:
                    account_equity = float(getattr(snapshot, "equity_usd", 0.0) or 0.0)
                    free_margin = float(getattr(snapshot, "available_margin_usd", 0.0) or 0.0)
                    used_margin = float(getattr(snapshot, "used_margin_usd", 0.0) or 0.0)
                    equity_snapshot_ok = True
                    equity_snapshot_reason = "ok"
                    margin_tracker = getattr(risk_state, "margin_tracker", None)
                    if margin_tracker is not None:
                        margin_tracker.account_equity = float(account_equity)
                else:
                    account_equity = 0.0
                    free_margin = 0.0
                    used_margin = 0.0
                    equity_snapshot_reason = (
                        "equity_snapshot_stale" if snapshot_ok and not snapshot_fresh else snapshot_reason
                    )
            except Exception:
                logging.exception("Unhandled broad exception fallback in lumina_core/risk/final_arbitration.py:153")
                account_equity = 0.0
                free_margin = 0.0
                used_margin = 0.0
                equity_snapshot_reason = "provider_error"
        if not equity_snapshot_ok:
            reason_text = f"{runtime_mode.upper()}_EQUITY_SNAPSHOT_FAIL: {equity_snapshot_reason}"
            if runtime_mode == "real":
                logger.critical(reason_text)
                log_structured(
                    LuminaError(
                        severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                        code="REAL_EQUITY_SNAPSHOT_FAIL",
                        message=reason_text,
                        context={"source": equity_snapshot_source, "age_seconds": round(equity_snapshot_age_sec, 3)},
                    )
                )
            else:
                logger.error(reason_text)
    elif is_strict_arbitration_mode(runtime_mode) and float(account_equity or 0.0) <= 0.0:
        equity_snapshot_ok = False
        equity_snapshot_reason = f"{runtime_mode}_account_context_missing"
    open_risk = dict(open_risk_by_symbol) if isinstance(open_risk_by_symbol, dict) else {}
    return ArbitrationState(
        runtime_mode=runtime_mode,
        daily_pnl=float(realized_pnl or 0.0),
        account_equity=float(account_equity or 0.0),
        drawdown_pct=float(getattr(engine, "drawdown_pct", 0.0) or 0.0),
        drawdown_kill_percent=float(getattr(getattr(engine, "config", None), "drawdown_kill_percent", 25.0) or 25.0),
        used_margin=float(used_margin or 0.0),
        free_margin=float(free_margin or 0.0),
        equity_snapshot_ok=bool(equity_snapshot_ok),
        equity_snapshot_reason=equity_snapshot_reason,
        equity_snapshot_source=equity_snapshot_source,
        equity_snapshot_age_sec=float(equity_snapshot_age_sec),
        open_risk_by_symbol={str(symbol): float(value or 0.0) for symbol, value in open_risk.items()},
        total_open_risk=total_open_risk,
        var_95_usd=float(getattr(risk_state, "var_95_usd", 0.0) or 0.0) if risk_state is not None else 0.0,
        var_99_usd=float(getattr(risk_state, "var_99_usd", 0.0) or 0.0) if risk_state is not None else 0.0,
        es_95_usd=float(getattr(risk_state, "es_95_usd", 0.0) or 0.0) if risk_state is not None else 0.0,
        es_99_usd=float(getattr(risk_state, "es_99_usd", 0.0) or 0.0) if risk_state is not None else 0.0,
        live_position_qty=int(live_position_qty or 0),
    )


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
