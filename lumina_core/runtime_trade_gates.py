"""Extracted trade gating helpers for the runtime supervisor (hard risk, session)."""

from __future__ import annotations

from typing import Any

from lumina_core.risk.final_arbitration import FinalArbitration, build_current_state_from_engine
from lumina_core.risk.risk_policy import load_risk_policy


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
    if risk_controller is None:
        logger.warning("HardRiskController unavailable – trade blocked (fail-closed)")
        return "HOLD", False, "no_risk_controller"
    raw_stop = float(
        dream_snapshot.get("stop", price * 0.99 if signal == "BUY" else price * 1.01)
    )
    proposed_risk = abs(float(price) - raw_stop)
    ok, reason = risk_controller.check_can_trade(
        str(instrument),
        str(dream_snapshot.get("regime", "NEUTRAL")),
        float(proposed_risk),
    )
    if not ok:
        logger.warning("HardRiskController blocked trade: %s", reason)
        return "HOLD", False, str(reason)
    try:
        intent = {
            "symbol": str(instrument),
            "side": str(signal).upper(),
            "quantity": int(dream_snapshot.get("qty", 1) or 1),
            "reference_price": float(price),
            "stop_loss": float(
                dream_snapshot.get("stop", price * 0.99 if str(signal).upper() == "BUY" else price * 1.01)
            ),
            "proposed_risk": float(abs(float(price) - float(dream_snapshot.get("stop", price)))),
            "regime": str(dream_snapshot.get("regime", "NEUTRAL")),
            "metadata": {
                "reason": str(dream_snapshot.get("reason", "") or ""),
                "confluence_score": float(dream_snapshot.get("confluence_score", 0.0) or 0.0),
            },
        }
        current_state = (
            build_current_state_from_engine(engine) if engine is not None else {"runtime_mode": str(mode).strip().lower()}
        )
        policy = getattr(engine, "risk_policy", None) if engine is not None else None
        arb = getattr(engine, "final_arbitration", None) if engine is not None else None
        if arb is None:
            arb = FinalArbitration(policy or load_risk_policy(mode=str(mode)))
        arb_result = arb.check_order_intent(intent, current_state)
        if arb_result.status != "APPROVED":
            logger.warning("FinalArbitration blocked runtime signal: %s", arb_result.reason)
            return "HOLD", False, str(arb_result.reason)
    except Exception as exc:
        logger.warning("FinalArbitration runtime gate error (fail-closed): %s", exc)
        return "HOLD", False, "final_arbitration_error"
    return signal, True, ""
