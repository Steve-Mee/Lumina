"""Extracted trade gating helpers for the runtime supervisor (hard risk, session)."""

from __future__ import annotations

from typing import Any

from lumina_core.order_gatekeeper import enforce_pre_trade_gate
from lumina_core.engine.trade_signal_normalize import canonicalize_trade_signal


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
    """If ``signal`` is BUY/SELL, run canonical admission chain. Returns (signal, ok, reason)."""
    signal = canonicalize_trade_signal(signal)
    if signal not in {"BUY", "SELL"}:
        return signal, True, ""
    raw_stop = float(dream_snapshot.get("stop", price * 0.99 if signal == "BUY" else price * 1.01))
    proposed_risk = abs(float(price) - raw_stop)
    try:
        if engine is None:
            logger.warning("AdmissionChain unavailable without engine; blocking runtime signal")
            return "HOLD", False, "admission_engine_required"
        allowed, reason = enforce_pre_trade_gate(
            engine,
            symbol=str(instrument),
            regime=str(dream_snapshot.get("regime", "NEUTRAL")),
            proposed_risk=float(proposed_risk),
            order_side=str(signal).upper(),
        )
        if not allowed:
            logger.warning("AdmissionChain blocked runtime signal: %s", reason)
            return "HOLD", False, str(reason)
    except Exception as exc:
        logger.warning("AdmissionChain runtime gate error (fail-closed): %s", exc)
        return "HOLD", False, "admission_chain_error"
    return signal, True, ""
