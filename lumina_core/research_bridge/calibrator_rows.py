"""FillEvent → live-calibrator JSONL row. Hypothetical fills never become a row."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from lumina_core.engine.trade_reconciler.schemas import FillEvent
from lumina_core.market.nt_fees import CostCardError, contract_root, spec_for

BROKER_SOURCE: Literal["broker"] = "broker"
HYPOTHETICAL_SOURCE: Literal["hypothetical_adr0055"] = "hypothetical_adr0055"
LIVE_CALIBRATION_EVENT: str = "reconciled"
LEGAL_SOURCES: frozenset[str] = frozenset({BROKER_SOURCE, HYPOTHETICAL_SOURCE})


class CalibratorRowRefused(ValueError):
    """Row cannot enter the live calibrator without inventing costs."""


def normalize_fill_source(value: object) -> str:
    text = str(value or "").strip().lower()
    if text == HYPOTHETICAL_SOURCE:
        return HYPOTHETICAL_SOURCE
    if text == BROKER_SOURCE or text == "":
        return BROKER_SOURCE
    raise CalibratorRowRefused(f"unknown_fill_source:{text}")


def is_hypothetical_source(value: object) -> bool:
    try:
        return normalize_fill_source(value) == HYPOTHETICAL_SOURCE
    except CalibratorRowRefused:
        return False


def is_broker_source(value: object) -> bool:
    try:
        return normalize_fill_source(value) == BROKER_SOURCE
    except CalibratorRowRefused:
        return False


def root_of_symbol(symbol: object) -> str:
    try:
        return contract_root(str(symbol or ""))
    except CostCardError as exc:
        raise CalibratorRowRefused(f"root_not_on_card:{symbol}") from exc


def live_calibrator_row(fill: FillEvent) -> dict[str, Any] | None:
    """Broker FillEvent → reconciled row. Hypothetical returns ``None`` (not a skip-log)."""
    source = normalize_fill_source(fill.source)
    if source == HYPOTHETICAL_SOURCE:
        return None
    if source != BROKER_SOURCE:
        raise CalibratorRowRefused("unknown_fill_source")
    root = root_of_symbol(fill.symbol)
    qty = int(fill.qty)
    if qty < 1:
        raise CalibratorRowRefused("qty_invalid")
    quote = spec_for(root)
    ts = fill.event_ts
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    payload: dict[str, Any] = {
        "event": LIVE_CALIBRATION_EVENT,
        "ts": ts.isoformat(),
        "symbol": str(fill.symbol),
        "root": root,
        "quantity": qty,
        "qty": qty,
        "fill_price": float(fill.fill_price),
        "price": float(fill.price),
        "commission": float(fill.commission),
        "commission_ticks": float(fill.commission_ticks),
        "slippage_ticks": float(fill.slippage_ticks),
        "slippage_usd": float(fill.slippage_usd),
        "slippage_points": float(fill.slippage_ticks) * float(quote.tick_size),
        "strategy_id": str(fill.strategy_id or ""),
        "source": BROKER_SOURCE,
        "fill_id": str(fill.fill_id),
        "side": str(fill.side),
    }
    return payload


def event_ts_now() -> datetime:
    return datetime.now(timezone.utc)
