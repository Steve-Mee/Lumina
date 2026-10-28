"""FORCE_OPEN plant geometry: ATR × √dwell, constitution-clipped.

Extracted from sim_runner so the rollout file stays under the M5 ceiling.
Live stop remains on — never suppress hit_stop.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from lumina_core.birth.birth_trade_geometry import BirthTradeGeometry
from lumina_core.birth.stage2_participation_envelope import force_open_stop_from_atr


def tape_atr_pct_for_force_open(
    row: dict[str, Any],
    geometry: BirthTradeGeometry,
) -> float:
    """Tape ATR for FORCE_OPEN dwell survival.

    Geometry stop is ``0.9 × ATR median`` (``_geometry_from_atr``). Tick
    ``trend_atr_norm`` uses the same ≥0.05 ⇒ divide-by-price rule as
    ``_collect_atr_samples``.
    """
    geo_stop = max(0.0, float(getattr(geometry, "stop_pct", 0.0) or 0.0))
    geo_atr = geo_stop / 0.9 if geo_stop > 0.0 else 0.0
    try:
        atr = float(row.get("trend_atr_norm") or 0.0)
    except (TypeError, ValueError):
        atr = 0.0
    try:
        px = float(row.get("last") or row.get("close") or 0.0)
    except (TypeError, ValueError):
        px = 0.0
    if atr >= 0.05 and px > 0.0:
        atr = atr / px
    atr = min(0.02, max(0.0, atr))
    return max(geo_atr, atr, geo_stop)


def apply_force_open_side(action: np.ndarray, row: dict[str, Any]) -> np.ndarray:
    """Prefer MTF bias over blind L/S alternate. Occupancy plant only."""
    try:
        mtf = float(row.get("bible_mtf_bias", 0.0) or 0.0)
        conf = float(row.get("bible_confluence", 0.0) or 0.0)
        if abs(mtf) >= 0.05 or conf >= 0.15:
            side_sel = 1.0 if mtf >= 0.0 else 2.0
            return np.array(
                [side_sel, float(action[1]), float(action[2]), float(action[3])],
                dtype=np.float32,
            )
    except Exception:
        pass
    return action


def apply_force_open_stop(
    action: np.ndarray,
    row: dict[str, Any],
    geometry: BirthTradeGeometry,
    *,
    min_dwell_bars: int,
    equity: float,
    qty: int = 1,
) -> tuple[np.ndarray, float]:
    """Widen FORCE_OPEN stop to ATR×√dwell, clip to constitution + dollar 1%.

    Dollar cap includes qty in the denominator. Birth still ships qty_frac=0
    (gym ``force_qty_one`` fills 1 lot). Exam equity is the $50k yardstick.
    """
    atr_pct = tape_atr_pct_for_force_open(row, geometry)
    stop = force_open_stop_from_atr(
        atr_pct=atr_pct,
        min_dwell_bars=int(min_dwell_bars),
    )
    try:
        px = float(row.get("last") or row.get("close") or 0.0)
    except (TypeError, ValueError):
        px = 0.0
    from lumina_core.birth.foundation_metrics import S5_DD_EQUITY_USD
    from lumina_core.birth.notional_cap import birth_stop_pct_dollar_cap

    qty_n = max(1, int(qty))
    try:
        live_eq = float(equity)
    except (TypeError, ValueError):
        live_eq = 0.0
    exam_eq = float(S5_DD_EQUITY_USD)
    eq = exam_eq if live_eq <= 0.0 else min(live_eq, exam_eq)
    if px > 0.0 and eq > 0.0:
        dollar_cap = birth_stop_pct_dollar_cap(price=px, qty=qty_n, equity=eq)
        if dollar_cap > 0.0:
            stop = min(stop, dollar_cap)
    try:
        from lumina_core.birth.birth_constitution_guard import (
            BIRTH_MAX_RISK_STOP_PCT,
            BIRTH_MIN_STOP_PCT,
        )

        stop = max(float(BIRTH_MIN_STOP_PCT), min(float(BIRTH_MAX_RISK_STOP_PCT), float(stop)))
    except Exception:
        stop = max(0.0004, min(0.01, float(stop)))
    prev_stop = max(float(action[2]), 1e-12)
    rr = max(1.25, float(action[3]) / prev_stop)
    target = max(stop * 1.25, min(0.05, stop * rr))
    out = np.array(
        [float(action[0]), 0.0, float(stop), float(target)],
        dtype=np.float32,
    )
    return out, float(stop)


class ForceOpenChatterBound:
    """Min-dwell refractory after a FORCE_OPEN plant settles. Shared airframe."""

    __slots__ = ("bars_since_settle",)

    def __init__(self) -> None:
        self.bars_since_settle: int | None = None

    def on_bar(self, *, trade_closed: bool, closed_was_plant: bool) -> None:
        if trade_closed and closed_was_plant:
            self.bars_since_settle = 0
            return
        if self.bars_since_settle is not None:
            self.bars_since_settle += 1

    def blocks(self, min_dwell_bars: int) -> bool:
        if self.bars_since_settle is None:
            return False
        return int(self.bars_since_settle) < max(1, int(min_dwell_bars))


__all__ = [
    "ForceOpenChatterBound",
    "apply_force_open_side",
    "apply_force_open_stop",
    "tape_atr_pct_for_force_open",
]
