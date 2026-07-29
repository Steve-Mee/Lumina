from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from lumina_core.engine.margin_snapshot_provider import MarginSnapshot, MarginSnapshotProvider


@dataclass
class MarginTracker:
    """Track CME futures margin requirements per instrument."""

    snapshot: MarginSnapshot = field(default_factory=MarginSnapshotProvider.from_config)
    account_equity: float = 50000.0

    def get_margin_requirement(self, symbol: str) -> float:
        symbol_upper = str(symbol).strip().upper()
        return self.snapshot.margins.get(symbol_upper, self.account_equity * 0.03)

    def is_snapshot_stale(self) -> bool:
        return bool(self.snapshot.stale)

    def snapshot_status(self) -> dict[str, Any]:
        return {
            "source": self.snapshot.source,
            "as_of": self.snapshot.as_of.isoformat(),
            "confidence": float(self.snapshot.confidence),
            "stale_after_hours": int(self.snapshot.stale_after_hours),
            "age_hours": float(round(self.snapshot.age_hours, 3)),
            "stale": bool(self.snapshot.stale),
        }

    def available_margin(self, positions_margin_used: float) -> float:
        return max(0.0, self.account_equity - positions_margin_used)

    def can_open_position(self, symbol: str, positions_margin_used: float, safety_buffer_pct: float = 0.2) -> bool:
        required_margin = self.get_margin_requirement(symbol)
        available = self.available_margin(positions_margin_used)
        margin_with_buffer = required_margin * (1.0 + safety_buffer_pct)
        return available >= margin_with_buffer

    def margin_utilization_pct(self, positions_margin_used: float) -> float:
        if self.account_equity <= 0:
            return 100.0
        return (positions_margin_used / self.account_equity) * 100.0


@dataclass
class RiskState:
    daily_pnl: float = 0.0
    consecutive_losses: int = 0
    last_loss_time: Optional[datetime] = None
    open_risk_by_symbol: dict[str, float] = field(default_factory=dict)
    symbol_regime_map: dict[str, str] = field(default_factory=dict)
    open_risk_all_regimes: dict[str, float] = field(default_factory=dict)
    kill_switch_engaged: bool = False
    kill_switch_reason: str = ""
    kill_switch_time: Optional[datetime] = None
    trade_history: deque = field(default_factory=lambda: deque(maxlen=100))
    active_regime: str = "NEUTRAL"
    active_risk_state: str = "NORMAL"
    portfolio_var_usd: float = 0.0
    portfolio_var_limit_usd: float = 1200.0
    portfolio_var_breached: bool = False
    portfolio_var_reason: str = ""
    var_95_usd: float = 0.0
    var_99_usd: float = 0.0
    es_95_usd: float = 0.0
    es_99_usd: float = 0.0
    var_es_breached: bool = False
    var_es_reason: str = ""
    mc_drawdown_p50_pct: float = 0.0
    mc_drawdown_p95_pct: float = 0.0
    mc_drawdown_p99_pct: float = 0.0
    mc_drawdown_worst_pct: float = 0.0
    mc_drawdown_threshold_pct: float = 0.0
    mc_drawdown_breached: bool = False
    mc_drawdown_reason: str = ""
    mc_drawdown_samples: int = 0
    mc_drawdown_paths_run: int = 0
    regime_history: deque = field(default_factory=lambda: deque(maxlen=2000))
    regime_detector_history: deque = field(default_factory=lambda: deque(maxlen=5000))
    regime_detector_last_anchor: str = ""
    margin_tracker: Optional[MarginTracker] = field(default_factory=MarginTracker)


__all__ = ["MarginTracker", "RiskState"]
