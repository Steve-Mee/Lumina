"""In-process challenger venue loop — admit, fill, journal (Wave 2)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.evolution.challenger_venue.admission import admit_challenger_intent
from lumina_core.evolution.challenger_venue.fills import fill_price, gap_gate, trade_pnl
from lumina_core.evolution.challenger_venue.journal import append_journal


class VenueRuntime:
    """Internal paper venue. Never talks to NinjaTrader."""

    def __init__(
        self,
        workspace: Path | str,
        *,
        overlay_id: str = "",
        dna_hash: str = "",
        engine: Any = None,
    ) -> None:
        self.workspace = workspace
        self.overlay_id = overlay_id
        self.dna_hash = dna_hash
        self.engine = engine
        self.last_quote: dict[str, Any] = {}
        self.open_qty = 0.0
        self.open_side = ""
        self.open_px = 0.0
        self.fantasy_pnl = 0.0
        self.realistic_pnl = 0.0

    def on_tick(self, tick: dict[str, Any]) -> dict[str, Any] | None:
        quote = dict(tick or {})
        if "last" in quote or "bid" in quote:
            self.last_quote = quote
        intent = quote.get("intent") if isinstance(quote.get("intent"), dict) else None
        if intent is None:
            return None
        return self.submit_intent(intent)

    def submit_intent(self, intent: dict[str, Any]) -> dict[str, Any]:
        admitted = admit_challenger_intent(intent, engine=self.engine)
        if not admitted.get("admitted"):
            append_journal(
                self.workspace,
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "intent_id": str(intent.get("intent_id") or ""),
                    "reason": str(admitted.get("reason") or "rejected"),
                    "overlay_id": self.overlay_id,
                    "dna_hash": self.dna_hash,
                },
            )
            return admitted
        bid = float(self.last_quote.get("bid") or 0.0)
        ask = float(self.last_quote.get("ask") or 0.0)
        last = float(self.last_quote.get("last") or 0.0)
        mid = last if last else ((bid + ask) / 2.0 if (bid or ask) else 0.0)
        spread = max(0.0, ask - bid) if ask and bid else 0.0
        side = str(intent.get("side") or "").strip().upper()
        qty = float(intent.get("qty") or intent.get("quantity") or 0.0)
        closing = self.open_qty > 0.0 and side != self.open_side
        latency = float(self.last_quote.get("latency_ms") or 0.0)
        real_px = fill_price(
            side=side, mid=mid, spread=spread, fantasy=False, closing=closing, latency_ms=latency
        )
        fan_px = fill_price(side=side, mid=mid, spread=spread, fantasy=True, closing=closing)
        pnl = 0.0
        fan_pnl = 0.0
        if closing and self.open_qty > 0.0:
            traded = min(qty, self.open_qty)
            pnl = trade_pnl(side=self.open_side, qty=traded, entry=self.open_px, exit=real_px)
            fan_pnl = trade_pnl(side=self.open_side, qty=traded, entry=self.open_px, exit=fan_px)
            self.realistic_pnl += pnl
            self.fantasy_pnl += fan_pnl
            self.open_qty = 0.0
            self.open_side = ""
            self.open_px = 0.0
        else:
            self.open_qty = qty
            self.open_side = side
            self.open_px = real_px
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "intent_id": str(intent.get("intent_id") or ""),
            "side": side,
            "qty": qty,
            "fill_price": real_px,
            "pnl": pnl,
            "overlay_id": self.overlay_id,
            "dna_hash": self.dna_hash,
            "reason": "fill",
        }
        append_journal(self.workspace, record)
        return {"admitted": True, "fill": record, "gap": self.gap()}

    def gap(self) -> dict[str, Any]:
        return gap_gate(fantasy_pnl=self.fantasy_pnl, realistic_pnl=self.realistic_pnl)

    def has_open_position(self) -> bool:
        return abs(self.open_qty) > 1e-12
