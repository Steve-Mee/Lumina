"""Tape+bundle replay harness — same events must yield the same fill digest (K7)."""

from __future__ import annotations

from typing import Any

from lumina_core.evolution.challenger_venue.fills import fill_price, trade_pnl
from lumina_core.evolution.challenger_venue.journal import replay_digest


def simulate_fills(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic paper fills from recorded tape+intent events (no disk, no NT)."""
    open_qty = 0.0
    open_side = ""
    open_px = 0.0
    rows: list[dict[str, Any]] = []
    last_quote: dict[str, Any] = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        quote_raw = event.get("quote")
        quote: dict[str, Any] = dict(quote_raw) if isinstance(quote_raw, dict) else dict(event)
        if "last" in quote or "bid" in quote:
            last_quote = quote
        intent_raw = event.get("intent")
        intent = dict(intent_raw) if isinstance(intent_raw, dict) else None
        if intent is None:
            continue
        side = str(intent.get("side") or "").strip().upper()
        qty = float(intent.get("qty") or intent.get("quantity") or 0.0)
        if side not in {"BUY", "SELL", "LONG", "SHORT"} or qty <= 0.0:
            continue
        bid = float(last_quote.get("bid") or 0.0)
        ask = float(last_quote.get("ask") or 0.0)
        last = float(last_quote.get("last") or 0.0)
        mid = last if last else ((bid + ask) / 2.0 if (bid or ask) else 0.0)
        spread = max(0.0, ask - bid) if ask and bid else 0.0
        closing = open_qty > 0.0 and side != open_side
        latency = float(last_quote.get("latency_ms") or 0.0)
        px = fill_price(
            side=side,
            mid=mid,
            spread=spread,
            fantasy=False,
            closing=closing,
            latency_ms=latency,
        )
        pnl = 0.0
        if closing and open_qty > 0.0:
            pnl = trade_pnl(side=open_side, qty=min(qty, open_qty), entry=open_px, exit=px)
            open_qty = 0.0
            open_side = ""
            open_px = 0.0
        else:
            open_qty = qty
            open_side = side
            open_px = px
        rows.append(
            {
                "intent_id": str(intent.get("intent_id") or ""),
                "side": side,
                "qty": qty,
                "fill_price": px,
                "pnl": pnl,
                "overlay_id": str(event.get("overlay_id") or ""),
                "dna_hash": str(event.get("dna_hash") or ""),
                "reason": "fill",
            }
        )
    return rows


def replay_tape_digest(events: list[dict[str, Any]]) -> str:
    return replay_digest(simulate_fills(events))
