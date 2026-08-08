"""State/payload builders for FinalArbitration (global residual)."""
from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Literal, cast

from lumina_core.engine.errors import ErrorSeverity, LuminaError, log_structured
from lumina_core.risk.risk_policy import RiskPolicy
from lumina_core.risk.schemas import ArbitrationState, OrderIntent, OrderIntentMetadata
from lumina_core.safety.trading_constitution import TRADING_CONSTITUTION

logger = logging.getLogger(__name__)

STRICT_ARBITRATION_MODES = frozenset({"real", "paper", "sim_real_guard"})
_MODES_REQUIRING_EQUITY_SNAPSHOT = frozenset({"real", "paper", "sim_real_guard"})

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
