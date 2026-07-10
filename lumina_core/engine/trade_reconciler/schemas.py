"""Trade reconciliation domain models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

@dataclass(slots=True)
class FillEvent:
    fill_id: str
    symbol: str
    side: str
    quantity: int
    price: float
    commission: float
    event_ts: datetime
    raw_payload: dict[str, Any] = field(default_factory=dict)

    # Phase 2 Slice 25: First-class lineage fields for multi-leg netting hash chain
    # (propagated from broker fills and pending closes)
    decision_context_id: str | None = None
    prev_hash: str | None = None
    prev_event_topic: str | None = None  # for full typed spine (Slice 19/ live wiring)


@dataclass(slots=True)
class PendingTradeClose:
    reconciliation_id: str
    symbol: str
    mode: str
    signal: str
    quantity: int
    entry_price: float
    detected_exit_price: float
    expected_pnl: float
    detected_ts: datetime
    status: str = "closing"
    reflection: dict[str, Any] = field(default_factory=dict)
    chart_base64: str | None = None
    expected_close_side: str = "SELL"
    fill_parts: list[dict[str, Any]] = field(default_factory=list)
    matched_qty: int = 0
    weighted_exit_notional: float = 0.0
    commission_total: float = 0.0

    # Phase 2 Slice 25: Support for multi-leg netting hash chain.
    # decision_context_id and prev_hash from the originating decision/fills (propagated for netting).
    decision_context_id: str | None = None
    prev_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["detected_ts"] = self.detected_ts.isoformat()
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PendingTradeClose":
        data = dict(payload)
        detected_ts_raw = data.get("detected_ts")
        if isinstance(detected_ts_raw, str):
            data["detected_ts"] = datetime.fromisoformat(detected_ts_raw)
        return cls(**data)
