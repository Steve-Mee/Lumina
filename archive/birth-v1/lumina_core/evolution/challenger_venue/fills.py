"""Internal paper fills with spread friction + reality-gap gate (K6)."""

from __future__ import annotations

from typing import Any


def fill_price(
    *,
    side: str,
    mid: float,
    spread: float,
    fantasy: bool,
    closing: bool = False,
    latency_ms: float = 0.0,
) -> float:
    px = float(mid)
    if fantasy:
        return px
    half = max(0.0, float(spread)) / 2.0
    side_u = str(side or "").strip().upper()
    is_buy = side_u in {"BUY", "LONG"}
    if closing:
        is_buy = not is_buy
    if is_buy:
        px = px + half
    else:
        px = px - half
    if not fantasy and float(latency_ms) > 0.0:
        extra = half * 0.25
        px = px + extra if is_buy else px - extra
    return px


def trade_pnl(*, side: str, qty: float, entry: float, exit: float) -> float:
    q = float(qty)
    side_u = str(side or "").strip().upper()
    if side_u in {"BUY", "LONG"}:
        return (float(exit) - float(entry)) * q
    if side_u in {"SELL", "SHORT"}:
        return (float(entry) - float(exit)) * q
    return 0.0


def gap_gate(
    *,
    fantasy_pnl: float,
    realistic_pnl: float,
    max_gap_ratio: float = 0.30,
) -> dict[str, Any]:
    """Block Steve notify when fantasy mid-price PnL is materially better (K6)."""
    fan = float(fantasy_pnl)
    real = float(realistic_pnl)
    denom = max(abs(fan), 1e-9)
    gap_ratio = (fan - real) / denom
    passed = gap_ratio <= float(max_gap_ratio) + 1e-12
    return {
        "passed": passed,
        "gap_ratio": gap_ratio,
        "fantasy_pnl": fan,
        "realistic_pnl": real,
        "notify_allowed": passed,
        "reason": "ok" if passed else "reality_gap_exceeded",
    }
