"""DynamicKellyEstimator — rolling Kelly fraction estimation for Lumina v53.

Replaces the static config-based Kelly fraction with one that adapts to recent
trading performance.  The estimator is updated every time a trade fills via the
event bus topic ``execution.fill``.

Formula (classical Kelly):
    f* = (b·p - q) / b
where:
    p = win_rate (probability of winning trade)
    q = 1 - p (probability of losing trade)
    b = avg_win / avg_loss (reward-to-risk ratio, always > 0)

Safety constraints:
    - Raw Kelly is clipped to [min_kelly, fractional_kelly_cap].
    - In REAL mode, fractional_kelly_cap is enforced regardless of estimates.
    - If the rolling window has < min_window_trades, the config fallback is used.
    - Estimates are logged to ``state/kelly_history.jsonl`` for auditability.

Usage:
    estimator = DynamicKellyEstimator()
    estimator.record_trade(pnl=150.0)
    contract = estimator.snapshot()  # DynamicKellyContract
    fraction = estimator.fractional_kelly(mode="real")
"""

from __future__ import annotations

import json
import logging
import math
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.engine.financial_contracts import DynamicKellyContract

logger = logging.getLogger(__name__)

_DEFAULT_HISTORY_PATH = Path("state/kelly_history.jsonl")
_MIN_WINDOW_TRADES = 10   # Minimum trades before estimator is trusted


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DynamicKellyEstimator:
    """Rolling Kelly fraction estimator updated per-trade.

    Parameters
    ----------
    window:
        Number of recent trades in the rolling window.
    min_kelly:
        Floor for the Kelly estimate (prevents going to 0 in drawdown streaks).
    fractional_kelly_real:
        Cap applied in REAL mode (e.g., 0.25 = 25 % of raw Kelly).
    fractional_kelly_sim:
        Cap applied in SIM mode (1.0 = full raw Kelly allowed).
    config_fallback_real:
        Fallback fraction used when insufficient trades are available (REAL).
    history_path:
        Path to the JSONL audit log for Kelly estimates.
    """

    window: int = 50
    min_kelly: float = 0.01
    fractional_kelly_real: float = 0.25
    fractional_kelly_sim: float = 1.0
    config_fallback_real: float = 0.25
    config_fallback_sim: float = 1.0
    history_path: Path = field(default_factory=lambda: _DEFAULT_HISTORY_PATH)

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._trades: deque[float] = deque(maxlen=int(self.window))

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_trade(self, pnl: float) -> None:
        """Add a completed trade PnL to the rolling window."""
        with self._lock:
            self._trades.append(float(pnl))

    def record_fill(self, fill_event: dict[str, Any]) -> None:
        """Convenience method for event bus integration.

        Accepts a fill event dict with a ``pnl`` or ``net_pnl`` key.
        """
        pnl = float(
            fill_event.get("pnl", fill_event.get("net_pnl", fill_event.get("realized_pnl", 0.0))) or 0.0
        )
        self.record_trade(pnl)

    # ------------------------------------------------------------------
    # Estimation
    # ------------------------------------------------------------------

    def _compute_raw_kelly(self, trades: list[float]) -> dict[str, float]:
        """Compute raw Kelly fraction from a list of trade PnL values."""
        if len(trades) < _MIN_WINDOW_TRADES:
            return {
                "raw_kelly": 0.0,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "sufficient": False,
            }

        wins = [t for t in trades if t > 0]
        losses = [t for t in trades if t <= 0]

        n = len(trades)
        win_rate = len(wins) / n

        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0

        if avg_loss <= 0.0:
            # No losses — cap at min_kelly as a sanity check (too good to be true)
            raw_kelly = max(self.min_kelly, win_rate)
        else:
            b = avg_win / avg_loss  # reward-to-risk
            p = win_rate
            q = 1.0 - p
            raw_kelly = (b * p - q) / b

        profit_factor = (avg_win * len(wins)) / (avg_loss * len(losses)) if losses and avg_loss > 0 else math.inf

        return {
            "raw_kelly": float(raw_kelly),
            "win_rate": float(win_rate),
            "avg_win": float(avg_win),
            "avg_loss": float(avg_loss),
            "profit_factor": float(min(profit_factor, 999.0)),
            "sufficient": True,
        }

    def raw_kelly(self) -> float:
        """Return the unclipped Kelly fraction from the rolling window."""
        with self._lock:
            trades = list(self._trades)
        est = self._compute_raw_kelly(trades)
        return float(est["raw_kelly"])

    def fractional_kelly(self, mode: str = "real") -> float:
        """Return the safety-clipped Kelly fraction for the given trading mode.

        Falls back to config defaults when insufficient trades are in window.
        """
        with self._lock:
            trades = list(self._trades)

        est = self._compute_raw_kelly(trades)
        is_real = str(mode).lower() == "real"

        if not est["sufficient"]:
            return self.config_fallback_real if is_real else self.config_fallback_sim

        raw = float(est["raw_kelly"])
        cap = self.fractional_kelly_real if is_real else self.fractional_kelly_sim

        # Clip: [min_kelly, cap]
        clipped = max(self.min_kelly, min(cap, raw * cap))
        return float(clipped)

    # ------------------------------------------------------------------
    # Snapshot & audit
    # ------------------------------------------------------------------

    def snapshot(self, mode: str = "real") -> DynamicKellyContract:
        """Return a typed contract snapshot of the current Kelly state."""
        with self._lock:
            trades = list(self._trades)

        est = self._compute_raw_kelly(trades)
        frac = self.fractional_kelly(mode)

        return DynamicKellyContract(
            estimated_kelly=float(est["raw_kelly"]),
            fractional_kelly=frac,
            rolling_win_rate=float(est["win_rate"]),
            rolling_avg_win=float(est["avg_win"]),
            rolling_avg_loss=float(est["avg_loss"]),
            rolling_profit_factor=float(est["profit_factor"]),
            window_trades=len(trades),
        )

    def log_estimate(self, mode: str = "real") -> None:
        """Append the current Kelly estimate to the audit log."""
        contract = self.snapshot(mode)
        record = {
            "ts": _utcnow(),
            "mode": mode,
            "estimated_kelly": contract.estimated_kelly,
            "fractional_kelly": contract.fractional_kelly,
            "rolling_win_rate": contract.rolling_win_rate,
            "rolling_avg_win": contract.rolling_avg_win,
            "rolling_avg_loss": contract.rolling_avg_loss,
            "rolling_profit_factor": contract.rolling_profit_factor,
            "window_trades": contract.window_trades,
        }
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            with self.history_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
        except OSError as exc:
            logger.warning("DynamicKellyEstimator: could not write history: %s", exc)


# ---------------------------------------------------------------------------
# Module-level singleton (shared across the engine process)
# ---------------------------------------------------------------------------

_GLOBAL_KELLY: DynamicKellyEstimator | None = None
_GLOBAL_KELLY_LOCK = threading.Lock()


def get_global_kelly_estimator(
    *,
    window: int = 50,
    fractional_kelly_real: float = 0.25,
    fractional_kelly_sim: float = 1.0,
) -> DynamicKellyEstimator:
    """Return (or create) the process-level Kelly estimator singleton."""
    global _GLOBAL_KELLY
    with _GLOBAL_KELLY_LOCK:
        if _GLOBAL_KELLY is None:
            _GLOBAL_KELLY = DynamicKellyEstimator(
                window=window,
                fractional_kelly_real=fractional_kelly_real,
                fractional_kelly_sim=fractional_kelly_sim,
            )
    return _GLOBAL_KELLY
