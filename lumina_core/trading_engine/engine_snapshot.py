from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(slots=True)
class MarketStateContext:
    quote_count: int
    has_current_candle: bool
    last_candle_start_ts: float


@dataclass(slots=True)
class PositionStateContext:
    sim_position_qty: int
    live_position_qty: int
    last_entry_price: float
    live_trade_signal: str


@dataclass(slots=True)
class RiskStateContext:
    account_equity: float
    realized_pnl_today: float
    open_pnl: float
    pending_reconciliations: int


@dataclass(slots=True)
class AgentStateContext:
    regime: str
    confidence: float
    chosen_strategy: str
    memory_size: int


class SupportsEngineSnapshot(Protocol):
    live_quotes: Any
    current_candle: Any
    candle_start_ts: Any
    sim_position_qty: int
    live_position_qty: int
    last_entry_price: float
    live_trade_signal: str
    account_equity: float
    realized_pnl_today: float
    open_pnl: float
    pending_trade_reconciliations: list[dict[str, Any]]
    memory_buffer: Any

    def get_current_dream_snapshot(self) -> dict[str, Any]: ...


class EngineSnapshotService:
    """Build and serialize deterministic engine runtime snapshots."""

    def build_state_contexts(self, engine: SupportsEngineSnapshot) -> dict[str, Any]:
        dream = engine.get_current_dream_snapshot()
        candle_ts = engine.candle_start_ts
        if isinstance(candle_ts, datetime):
            candle_ts = candle_ts.timestamp()
        else:
            candle_ts = float(candle_ts or 0.0)
        market = MarketStateContext(
            quote_count=int(len(engine.live_quotes) if engine.live_quotes is not None else 0),
            has_current_candle=bool(engine.current_candle),
            last_candle_start_ts=candle_ts,
        )
        position = PositionStateContext(
            sim_position_qty=int(engine.sim_position_qty),
            live_position_qty=int(engine.live_position_qty),
            last_entry_price=float(engine.last_entry_price),
            live_trade_signal=str(engine.live_trade_signal),
        )
        risk = RiskStateContext(
            account_equity=float(engine.account_equity),
            realized_pnl_today=float(engine.realized_pnl_today),
            open_pnl=float(engine.open_pnl),
            pending_reconciliations=int(len(engine.pending_trade_reconciliations)),
        )
        agent = AgentStateContext(
            regime=str(dream.get("regime", "NEUTRAL")),
            confidence=float(dream.get("confidence", 0.0) or 0.0),
            chosen_strategy=str(dream.get("chosen_strategy", "unknown")),
            memory_size=int(len(engine.memory_buffer)),
        )
        return {
            "market": market,
            "position": position,
            "risk": risk,
            "agent": agent,
        }

    def serialize_state_snapshot(self, engine: SupportsEngineSnapshot) -> dict[str, Any]:
        contexts = self.build_state_contexts(engine)
        serialized = {
            "market": {
                "quote_count": contexts["market"].quote_count,
                "has_current_candle": contexts["market"].has_current_candle,
                "last_candle_start_ts": round(contexts["market"].last_candle_start_ts, 3),
            },
            "position": {
                "sim_position_qty": contexts["position"].sim_position_qty,
                "live_position_qty": contexts["position"].live_position_qty,
                "last_entry_price": round(contexts["position"].last_entry_price, 4),
                "live_trade_signal": contexts["position"].live_trade_signal,
            },
            "risk": {
                "account_equity": round(contexts["risk"].account_equity, 2),
                "realized_pnl_today": round(contexts["risk"].realized_pnl_today, 2),
                "open_pnl": round(contexts["risk"].open_pnl, 2),
                "pending_reconciliations": contexts["risk"].pending_reconciliations,
            },
            "agent": {
                "regime": contexts["agent"].regime,
                "confidence": round(contexts["agent"].confidence, 4),
                "chosen_strategy": contexts["agent"].chosen_strategy,
                "memory_size": contexts["agent"].memory_size,
            },
        }
        # Normalize key order to keep snapshots deterministic across runs.
        return json.loads(json.dumps(serialized, sort_keys=True, ensure_ascii=True))
