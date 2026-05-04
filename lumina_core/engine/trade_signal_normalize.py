"""Normalize arbitrary strategy/LLM signal labels to BUY | SELL | HOLD for supervisors and policy gateway."""

from __future__ import annotations

from typing import Any


def canonicalize_trade_signal(raw: Any) -> str:
    """Map messy dream / fast-path / JSON outputs to BUY, SELL, or HOLD.

    Fail-closed: anything unrecognized becomes HOLD so ``AgentPolicyGateway`` never sees ``invalid_signal``.
    """
    if raw is None:
        return "HOLD"
    s = str(raw).strip().upper()
    if not s:
        return "HOLD"

    synonyms: dict[str, str] = {
        "LONG": "BUY",
        "SHORT": "SELL",
        "NO_TRADE": "HOLD",
        "NO TRADE": "HOLD",
        "NOTHING": "HOLD",
        "WAIT": "HOLD",
        "FLAT": "HOLD",
        "NEUTRAL": "HOLD",
        "EXIT": "HOLD",
        "CLOSE": "HOLD",
        "NONE": "HOLD",
        "NULL": "HOLD",
    }
    s = synonyms.get(s, s)

    if s in {"BUY", "SELL", "HOLD"}:
        return s
    return "HOLD"
