"""SupervisorTickCtx — shared per-tick state (SSOT)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable


@dataclass
class SupervisorTickCtx:
    """Mutable per-tick state shared across phase blocks."""

    price: float
    dream_snapshot: dict[str, Any] | None
    now: datetime
    gate_result: dict[str, Any] = field(default_factory=dict)
    rl_action: Any = None
    eod_force_hold: bool = False
    min_confluence: float = 0.0
    signal: str = "HOLD"
    trade_mode: str = "paper"
    qty_multiplier: float = 1.0
    stop_widen_multiplier: float = 1.0
    hold_until_ts: float = 0.0
    swarm_manager: Any = None
    cfg: Any = None
    push_trader_league_trade: Callable[..., Any] | None = None
    compute_session_kpis: Callable[..., Any] | None = None
    publish_runtime_monitoring_snapshot: Callable[..., Any] | None = None


__all__ = ["SupervisorTickCtx"]
