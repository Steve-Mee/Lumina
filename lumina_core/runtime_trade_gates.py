"""Extracted trade gating helpers for the runtime supervisor (hard risk, session)."""

from __future__ import annotations

from typing import Any

from lumina_core.risk.final_arbitration import FinalArbitration, build_current_state_from_engine, is_strict_arbitration_mode
from lumina_core.risk.risk_policy import load_risk_policy
from lumina_core.risk.schemas import ArbitrationState, OrderIntent, OrderIntentMetadata


def apply_hard_risk_controller_to_signal(
    *,
    signal: str,
    price: float,
    dream_snapshot: dict[str, Any],
    instrument: str,
    risk_controller: Any,
    logger: Any,
    mode: str = "paper",
    engine: Any | None = None,
) -> tuple[str, bool, str]:
    """If ``signal`` is BUY/SELL, run ``HardRiskController.check_can_trade``. Returns (signal, ok, reason)."""
    if signal not in {"BUY", "SELL"}:
        return signal, True, ""
    raw_stop = float(dream_snapshot.get("stop", price * 0.99 if signal == "BUY" else price * 1.01))
    proposed_risk = abs(float(price) - raw_stop)
    try:
        intent = OrderIntent(
            instrument=str(instrument),
            side=str(signal).upper(),
            quantity=int(dream_snapshot.get("qty", 1) or 1),
            reference_price=float(price),
            stop=float(dream_snapshot.get("stop", price * 0.99 if str(signal).upper() == "BUY" else price * 1.01)),
            proposed_risk=float(abs(float(price) - float(dream_snapshot.get("stop", price)))),
            regime=str(dream_snapshot.get("regime", "NEUTRAL")),
            confluence_score=float(dream_snapshot.get("confluence_score", 0.0) or 0.0),
            confidence=float(dream_snapshot.get("confidence", 0.0) or 0.0),
            source_agent=str(dream_snapshot.get("source_agent", "runtime_trade_gates") or "runtime_trade_gates"),
            metadata=OrderIntentMetadata(reason=str(dream_snapshot.get("reason", "") or "")),
        )
        current_state = (
            build_current_state_from_engine(engine)
            if engine is not None
            else ArbitrationState(runtime_mode=str(mode).strip().lower())
        )
        policy = getattr(engine, "risk_policy", None) if engine is not None else None
        arb = getattr(engine, "final_arbitration", None) if engine is not None else None
        if arb is None:
            if is_strict_arbitration_mode(mode):
                logger.warning("FinalArbitration unavailable in strict mode; blocking runtime signal")
                return "HOLD", False, "final_arbitration_unavailable"
            arb = FinalArbitration(policy or load_risk_policy(mode=str(mode)))
        arb_result = arb.check_order_intent(intent, current_state)
        if arb_result.status != "APPROVED":
            logger.warning("FinalArbitration blocked runtime signal: %s", arb_result.reason)
            return "HOLD", False, str(arb_result.reason)
        if risk_controller is None:
            logger.warning("HardRiskController unavailable – trade blocked (fail-closed)")
            return "HOLD", False, "no_risk_controller"
        margin_tracker = getattr(getattr(risk_controller, "state", None), "margin_tracker", None)
        if margin_tracker is not None:
            margin_tracker.account_equity = float(current_state.account_equity or 0.0)
        ok, reason = risk_controller.check_can_trade(
            str(instrument),
            str(dream_snapshot.get("regime", "NEUTRAL")),
            float(proposed_risk),
        )
        if not ok:
            logger.warning("HardRiskController blocked trade: %s", reason)
            return "HOLD", False, str(reason)
    except Exception as exc:
        logger.warning("FinalArbitration runtime gate error (fail-closed): %s", exc)
        return "HOLD", False, "final_arbitration_error"
    return signal, True, ""
