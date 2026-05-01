"""DynamicKellyEstimator — volatility-adjusted rolling Kelly for Lumina.

Canonical location: ``lumina_core.risk.dynamic_kelly``
The engine shim at ``lumina_core.engine.dynamic_kelly`` re-exports from here.

Formula
-------
Classical Kelly:
    f* = (b·p - q) / b
    where p = win_rate, q = 1-p, b = avg_win / avg_loss

Volatility adjustment (vol-targeting):
    f_vol = f* × clamp(σ_target / σ_realized, 0, 1)

When realized volatility exceeds the target the fraction is scaled down
proportionally.  This prevents overexposure during high-vol regimes while
preserving full Kelly during calm markets.

Safety constraints
------------------
- Raw Kelly clipped to [min_kelly, fractional_kelly_cap].
- REAL mode: fractional_kelly_real enforced regardless.
- Insufficient trades → config fallback (never silently zero).
- All estimates logged to ``state/kelly_history.jsonl``.
"""

from __future__ import annotations

import json
import logging
import math
import threading
import warnings
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from lumina_core.engine.financial_contracts import DynamicKellyContract

logger = logging.getLogger(__name__)

_DEFAULT_HISTORY_PATH = Path("state/kelly_history.jsonl")
_MIN_WINDOW_TRADES = 10


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DynamicKellyEstimator:
    """Rolling, volatility-adjusted Kelly fraction estimator.

    Parameters
    ----------
    window:
        Rolling window size (number of recent trades).
    min_kelly:
        Floor for the Kelly estimate.
    fractional_kelly_real:
        Hard cap in REAL mode (e.g. 0.25 = 25 % of raw Kelly).
    fractional_kelly_sim:
        Cap in SIM mode (1.0 = full raw Kelly).
    config_fallback_real:
        Fallback when trade window is insufficient (REAL).
    config_fallback_sim:
        Fallback when trade window is insufficient (SIM).
    vol_target_annual:
        Target annualised volatility for the vol-scaling adjustment.
        Set to None to disable volatility adjustment.
    vol_lookback_trades:
        Number of recent trades used to estimate realized volatility.
    vol_scaling_enabled:
        Master switch for the volatility-targeting adjustment.
    history_path:
        JSONL audit log path.
    """

    window: int = 50
    min_kelly: float = 0.01
    fractional_kelly_real: float = 0.25
    fractional_kelly_sim: float = 1.0
    config_fallback_real: float = 0.25
    config_fallback_sim: float = 1.0
    vol_target_annual: float = 0.15
    vol_lookback_trades: int = 20
    vol_scaling_enabled: bool = True
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

        Accepts a fill event dict with a ``pnl``, ``net_pnl``, or
        ``realized_pnl`` key.
        """
        pnl = float(
            fill_event.get("pnl", fill_event.get("net_pnl", fill_event.get("realized_pnl", 0.0))) or 0.0
        )
        self.record_trade(pnl)

    # ------------------------------------------------------------------
    # Core estimation
    # ------------------------------------------------------------------

    def _compute_raw_kelly(self, trades: list[float]) -> dict[str, float]:
        """Compute raw Kelly fraction + trade statistics."""
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
            raw_kelly = max(self.min_kelly, win_rate)
        else:
            b = avg_win / avg_loss
            p = win_rate
            q = 1.0 - p
            raw_kelly = (b * p - q) / b

        profit_factor = (
            (avg_win * len(wins)) / (avg_loss * len(losses))
            if losses and avg_loss > 0
            else math.inf
        )

        return {
            "raw_kelly": float(raw_kelly),
            "win_rate": float(win_rate),
            "avg_win": float(avg_win),
            "avg_loss": float(avg_loss),
            "profit_factor": float(min(profit_factor, 999.0)),
            "sufficient": True,
        }

    # ------------------------------------------------------------------
    # Volatility scaling
    # ------------------------------------------------------------------

    def _realized_vol_scalar(self, trades: list[float]) -> float:
        """Return vol-scaling factor: clamp(CV_target / CV_realized, 0, 1).

        Uses the **coefficient of variation** (CV = std / mean_abs_pnl) so the
        scaling is unit-invariant — it works whether PnL is in dollars, ticks,
        or any other unit.

        ``vol_target_annual`` is reinterpreted here as the **target CV** of the
        rolling PnL window.  A value of 0.15 means: "allow up to 15 % relative
        dispersion; scale down proportionally when dispersion is higher."

        Returns 1.0 (no scaling) when:
          - vol scaling is disabled
          - insufficient data
          - realized CV ≤ target (not over-extended)
          - all trades have the same absolute value (CV = 0 → degenerate)

        Returns < 1.0 when realized CV exceeds the target.
        """
        if not self.vol_scaling_enabled:
            return 1.0

        recent = trades[-self.vol_lookback_trades :]
        if len(recent) < max(4, self.vol_lookback_trades // 2):
            return 1.0

        arr = np.asarray(recent, dtype=float)
        realized_std = float(np.std(arr, ddof=1))
        mean_abs = float(np.mean(np.abs(arr)))

        if realized_std <= 0.0 or mean_abs <= 0.0:
            return 1.0

        # Coefficient of variation: unit-invariant relative dispersion
        realized_cv = realized_std / mean_abs

        # Scale down when realized dispersion exceeds the target
        scalar = self.vol_target_annual / realized_cv
        return float(min(1.0, max(0.0, scalar)))

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def raw_kelly(self) -> float:
        """Return the unclipped Kelly fraction from the rolling window."""
        with self._lock:
            trades = list(self._trades)
        return float(self._compute_raw_kelly(trades)["raw_kelly"])

    def vol_scaling_factor(self) -> float:
        """Return the current volatility scaling factor (0–1)."""
        with self._lock:
            trades = list(self._trades)
        return self._realized_vol_scalar(trades)

    def fractional_kelly(self, mode: str = "real") -> float:
        """Return the safety-clipped, volatility-adjusted Kelly fraction.

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

        # Base fractional Kelly (classical cap)
        clipped = max(self.min_kelly, min(cap, raw * cap))

        # Apply volatility scaling — reduces fraction during high-vol regimes
        vol_scalar = self._realized_vol_scalar(trades)
        vol_adjusted = clipped * vol_scalar

        # Ensure floor is still respected after vol adjustment
        return float(max(self.min_kelly, vol_adjusted))

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
        """Append the current Kelly estimate to the JSONL audit log."""
        contract = self.snapshot(mode)
        vol_scalar = self.vol_scaling_factor()
        record = {
            "ts": _utcnow(),
            "mode": mode,
            "estimated_kelly": contract.estimated_kelly,
            "fractional_kelly": contract.fractional_kelly,
            "vol_scaling_factor": vol_scalar,
            "vol_target_annual": self.vol_target_annual,
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


def get_global_kelly_estimator(
    *,
    window: int = 50,
    min_kelly: float = 0.01,
    fractional_kelly_real: float = 0.25,
    fractional_kelly_sim: float = 1.0,
    config_fallback_real: float = 0.25,
    config_fallback_sim: float = 1.0,
    vol_target_annual: float = 0.15,
    vol_lookback_trades: int = 20,
    vol_scaling_enabled: bool = True,
    history_path: Path | None = None,
) -> DynamicKellyEstimator:
    """Deprecated compatibility factory (no singleton state).

    Historically this function returned a process-level singleton. To prevent
    configuration drift, it now returns a fresh estimator per call.
    """
    warnings.warn(
        "get_global_kelly_estimator no longer returns a singleton; "
        "prefer constructing DynamicKellyEstimator explicitly.",
        DeprecationWarning,
        stacklevel=2,
    )
    return DynamicKellyEstimator(
        window=window,
        min_kelly=min_kelly,
        fractional_kelly_real=fractional_kelly_real,
        fractional_kelly_sim=fractional_kelly_sim,
        config_fallback_real=config_fallback_real,
        config_fallback_sim=config_fallback_sim,
        vol_target_annual=vol_target_annual,
        vol_lookback_trades=vol_lookback_trades,
        vol_scaling_enabled=vol_scaling_enabled,
        history_path=history_path or _DEFAULT_HISTORY_PATH,
    )
