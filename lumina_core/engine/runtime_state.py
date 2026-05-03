from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class EngineMemoryState:
    regime_history: deque = field(default_factory=lambda: deque(maxlen=10))
    narrative_memory: deque = field(default_factory=lambda: deque(maxlen=8))
    memory_buffer: deque = field(default_factory=lambda: deque(maxlen=5))
    trade_reflection_history: deque = field(default_factory=lambda: deque(maxlen=20))


@dataclass(slots=True)
class EnginePerformanceState:
    pnl_history: list[float] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=lambda: [50000.0])
    trade_log: list[dict[str, Any]] = field(default_factory=list)
    performance_log: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class EnginePositionState:
    sim_position_qty: int = 0
    sim_entry_price: float = 0.0
    sim_unrealized: float = 0.0
    sim_peak: float = 50000.0
    live_position_qty: int = 0
    last_entry_price: float = 0.0
    last_realized_pnl_snapshot: float = 0.0
    live_trade_signal: str = "HOLD"
    pending_trade_reconciliations: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class EngineAccountState:
    account_balance: float = 50000.0
    account_equity: float = 50000.0
    available_margin: float = 0.0
    positions_margin_used: float = 0.0
    realized_pnl_today: float = 0.0
    open_pnl: float = 0.0
    equity_snapshot_ok: bool = False
    equity_snapshot_reason: str = "unknown"
    admission_chain_final_arbitration_approved: bool = False
