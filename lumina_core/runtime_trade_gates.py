"""Extracted trade gating helpers for the runtime supervisor (hard risk, session)."""

from __future__ import annotations

from typing import Any


def apply_hard_risk_controller_to_signal(
    *,
    signal: str,
    price: float,
    dream_snapshot: dict[str, Any],
    instrument: str,
    risk_controller: Any,
    logger: Any,
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
    return signal, True, ""
