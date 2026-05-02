from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from lumina_core.risk.risk_policy import RiskPolicy, load_risk_policy
from lumina_core.safety.trading_constitution import TRADING_CONSTITUTION

ArbitrationStatus = Literal["APPROVED", "REJECTED"]


@dataclass(slots=True)
class ArbitrationResult:
    status: ArbitrationStatus
    reason: str
    checks: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def build_order_intent_from_order(order: Any, *, dream_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    snapshot = dict(dream_snapshot or {})
    metadata = getattr(order, "metadata", {})
    metadata = metadata if isinstance(metadata, dict) else {}
    reference_price = float(metadata.get("reference_price", 0.0) or 0.0)
    stop_loss = float(getattr(order, "stop_loss", 0.0) or 0.0)
    side = str(getattr(order, "side", "HOLD") or "HOLD").upper()
    proposed_risk = abs(reference_price - stop_loss) if reference_price > 0.0 and stop_loss > 0.0 else 0.0
    return {
        "symbol": str(getattr(order, "symbol", "") or ""),
        "side": side,
        "quantity": int(getattr(order, "quantity", 0) or 0),
        "order_type": str(getattr(order, "order_type", "MARKET") or "MARKET"),
        "stop_loss": stop_loss,
        "take_profit": float(getattr(order, "take_profit", 0.0) or 0.0),
        "reference_price": reference_price,
        "proposed_risk": float(metadata.get("proposed_risk", proposed_risk) or proposed_risk),
        "regime": str(snapshot.get("regime", metadata.get("regime", "NEUTRAL")) or "NEUTRAL"),
        "confluence_score": float(snapshot.get("confluence_score", metadata.get("confluence_score", 0.0)) or 0.0),
        "metadata": metadata,
    }


def build_current_state_from_engine(engine: Any) -> dict[str, Any]:
    app = getattr(engine, "app", None)
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
    return {
        "runtime_mode": str(getattr(getattr(engine, "config", None), "trade_mode", "paper") or "paper"),
        "daily_pnl": float(realized_pnl or 0.0),
        "account_equity": float(account_equity or 0.0),
        "drawdown_pct": float(getattr(engine, "drawdown_pct", 0.0) or 0.0),
        "drawdown_kill_percent": float(getattr(getattr(engine, "config", None), "drawdown_kill_percent", 25.0) or 25.0),
        "used_margin": float(used_margin or 0.0),
        "free_margin": float(free_margin or 0.0),
        "open_risk_by_symbol": dict(open_risk_by_symbol) if isinstance(open_risk_by_symbol, dict) else {},
        "total_open_risk": total_open_risk,
        "var_95_usd": float(getattr(risk_state, "var_95_usd", 0.0) or 0.0) if risk_state is not None else 0.0,
        "var_99_usd": float(getattr(risk_state, "var_99_usd", 0.0) or 0.0) if risk_state is not None else 0.0,
        "es_95_usd": float(getattr(risk_state, "es_95_usd", 0.0) or 0.0) if risk_state is not None else 0.0,
        "es_99_usd": float(getattr(risk_state, "es_99_usd", 0.0) or 0.0) if risk_state is not None else 0.0,
        "live_position_qty": int(live_position_qty or 0),
    }


class FinalArbitration:
    def __init__(self, policy: RiskPolicy | None = None) -> None:
        self.policy = policy or load_risk_policy()

    def check_order_intent(self, order_intent: dict[str, Any], current_state: dict[str, Any]) -> ArbitrationResult:
        checks: list[dict[str, Any]] = []
        try:
            intent = dict(order_intent or {})
            state = dict(current_state or {})
        except Exception:
            return ArbitrationResult(status="REJECTED", reason="arbitration_invalid_payload", checks=checks)

        valid, reason = self._validate_shape(intent, state)
        checks.append({"check": "shape", "ok": valid, "reason": reason})
        if not valid:
            return ArbitrationResult(status="REJECTED", reason=reason, checks=checks)

        if self._is_eod_risk_reducing_exit(intent, state):
            checks.append({"check": "eod_force_close_exit", "ok": True, "reason": "risk_reducing_exit"})
            return ArbitrationResult(status="APPROVED", reason="approved_eod_force_close_exit", checks=checks)

        c_ok, c_reason = self._check_constitution(intent, state)
        checks.append({"check": "constitution", "ok": c_ok, "reason": c_reason})
        if not c_ok:
            return ArbitrationResult(status="REJECTED", reason=c_reason, checks=checks)

        p_ok, p_reason = self._check_policy(intent, state)
        checks.append({"check": "risk_policy", "ok": p_ok, "reason": p_reason})
        if not p_ok:
            return ArbitrationResult(status="REJECTED", reason=p_reason, checks=checks)

        a_ok, a_reason = self._check_account_state(state)
        checks.append({"check": "account_state", "ok": a_ok, "reason": a_reason})
        if not a_ok:
            return ArbitrationResult(status="REJECTED", reason=a_reason, checks=checks)

        return ArbitrationResult(status="APPROVED", reason="approved", checks=checks)

    def _validate_shape(self, intent: dict[str, Any], state: dict[str, Any]) -> tuple[bool, str]:
        symbol = str(intent.get("symbol", "") or "").strip()
        if not symbol:
            return False, "invalid_order_symbol"
        side = str(intent.get("side", "HOLD") or "HOLD").upper()
        if side not in {"BUY", "SELL"}:
            return False, "invalid_order_side"
        qty = int(intent.get("quantity", 0) or 0)
        if qty <= 0:
            return False, "invalid_order_quantity"
        if not isinstance(state, dict):
            return False, "invalid_current_state"
        return True, "ok"

    def _check_constitution(self, intent: dict[str, Any], state: dict[str, Any]) -> tuple[bool, str]:
        mode = str(state.get("runtime_mode", self.policy.runtime_mode) or self.policy.runtime_mode).strip().lower()
        constitution_payload = {
            "order_intent": intent,
            "hyperparam_suggestion": {
                "kelly_fraction": float(self.policy.kelly_fraction),
                "max_risk_percent": float(self.policy.max_total_open_risk / max(float(state.get("account_equity", 1.0) or 1.0), 1.0)) * 100.0,
                "daily_loss_cap": float(self.policy.daily_loss_cap),
            },
        }
        constitution_payload.update(intent)
        try:
            violations = TRADING_CONSTITUTION.audit(
                json.dumps(constitution_payload, ensure_ascii=True, sort_keys=True),
                mode=mode,
                raise_on_fatal=False,
            )
        except Exception:
            return False, "constitution_check_error"
        fatals = [v for v in violations if str(getattr(v, "severity", "")).lower() == "fatal"]
        if fatals:
            return False, f"constitution_violation:{fatals[0].principle_name}"
        return True, "ok"

    def _check_policy(self, intent: dict[str, Any], state: dict[str, Any]) -> tuple[bool, str]:
        symbol = str(intent.get("symbol", "") or "").strip().upper()
        projected_risk = float(intent.get("proposed_risk", 0.0) or 0.0)
        if projected_risk <= 0.0:
            reference = float(intent.get("reference_price", 0.0) or 0.0)
            stop = float(intent.get("stop_loss", 0.0) or 0.0)
            if reference > 0.0 and stop > 0.0:
                projected_risk = abs(reference - stop)
        if projected_risk > float(self.policy.max_open_risk_per_instrument):
            return False, "risk_limit_per_instrument_exceeded"

        open_risk_by_symbol = state.get("open_risk_by_symbol", {})
        if isinstance(open_risk_by_symbol, dict):
            sym_open = float(open_risk_by_symbol.get(symbol, 0.0) or 0.0)
            if sym_open + projected_risk > float(self.policy.max_open_risk_per_instrument):
                return False, "risk_limit_per_instrument_exceeded"

        total_open_risk = float(state.get("total_open_risk", 0.0) or 0.0)
        if total_open_risk + projected_risk > float(self.policy.max_total_open_risk):
            return False, "risk_limit_total_open_exceeded"

        daily_pnl = float(state.get("daily_pnl", 0.0) or 0.0)
        if daily_pnl <= float(self.policy.daily_loss_cap):
            return False, "daily_loss_cap_breached"

        if float(state.get("var_95_usd", 0.0) or 0.0) > float(self.policy.var_95_limit_usd):
            return False, "var_95_limit_breached"
        if float(state.get("var_99_usd", 0.0) or 0.0) > float(self.policy.var_99_limit_usd):
            return False, "var_99_limit_breached"
        if float(state.get("es_95_usd", 0.0) or 0.0) > float(self.policy.es_95_limit_usd):
            return False, "es_95_limit_breached"
        if float(state.get("es_99_usd", 0.0) or 0.0) > float(self.policy.es_99_limit_usd):
            return False, "es_99_limit_breached"

        return True, "ok"

    def _check_account_state(self, state: dict[str, Any]) -> tuple[bool, str]:
        equity = float(state.get("account_equity", 0.0) or 0.0)
        if equity <= 0.0:
            return False, "account_equity_invalid"

        free_margin = float(state.get("free_margin", 0.0) or 0.0)
        used_margin = float(state.get("used_margin", 0.0) or 0.0)
        if free_margin <= 0.0 and used_margin > 0.0:
            return False, "margin_unavailable"

        drawdown_pct = float(state.get("drawdown_pct", 0.0) or 0.0)
        drawdown_kill_percent = float(state.get("drawdown_kill_percent", 25.0) or 25.0)
        if drawdown_pct >= drawdown_kill_percent:
            return False, "drawdown_kill_threshold_breached"
        return True, "ok"

    @staticmethod
    def _is_eod_risk_reducing_exit(intent: dict[str, Any], state: dict[str, Any]) -> bool:
        metadata = intent.get("metadata", {})
        metadata = metadata if isinstance(metadata, dict) else {}
        if str(metadata.get("reason", "")).strip().lower() == "eod_force_close":
            return True
        live_qty = int(state.get("live_position_qty", 0) or 0)
        side = str(intent.get("side", "")).upper()
        return (live_qty > 0 and side == "SELL") or (live_qty < 0 and side == "BUY")

