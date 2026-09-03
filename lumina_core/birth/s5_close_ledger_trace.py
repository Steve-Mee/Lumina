"""Trace-only S5 close_ledger columns (Gate 0). No fill / floor / reward law."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.foundation_metrics import S3_OCCUPANCY_MIN

OCC_FLOOR_NEIGHBORHOOD_HI = 0.30
REGIME_JOIN_KEY = "lumina_core/birth/sim_runner.py:704"


def close_ledger_row(tr: dict[str, Any]) -> dict[str, Any]:
    """Persist exam + G0 columns. Regime is copied from the live tick join."""
    risk = tr.get("risk_usd")
    try:
        intended = float(risk) if risk is not None else 0.0
    except (TypeError, ValueError):
        intended = 0.0
    reward = tr.get("reward_on_close", tr.get("reward"))
    try:
        reward_f = float(reward) if reward is not None else None
    except (TypeError, ValueError):
        reward_f = None
    return {
        "pnl": tr.get("pnl"),
        "qty": tr.get("qty"),
        "cap_usd": tr.get("cap_usd"),
        "close_reason": tr.get("close_reason"),
        "gap": tr.get("gap"),
        "plant": tr.get("plant_entry"),
        "entry_price": tr.get("entry_price"),
        "risk_usd": tr.get("risk_usd"),
        "intended_risk_usd": intended,
        "trade_r": tr.get("trade_r"),
        "point_value": tr.get("point_value"),
        "regime": str(tr.get("regime") or ""),
        "reward_on_close": reward_f,
        "cap_hit": _cap_hit(tr),
    }


def _cap_hit(tr: dict[str, Any]) -> bool:
    try:
        pnl = abs(float(tr.get("pnl") or 0.0))
        cap = float(tr.get("cap_usd") or 0.0)
    except (TypeError, ValueError):
        return False
    if cap <= 0.0:
        return False
    return pnl + 1e-9 >= cap


def occupancy_floor_neighborhood(flat_ratio: float) -> bool:
    """True when occupancy sits in the exam-min neighborhood [0.25, 0.30]."""
    x = float(flat_ratio)
    return S3_OCCUPANCY_MIN - 1e-12 <= x <= OCC_FLOOR_NEIGHBORHOOD_HI + 1e-12


__all__ = [
    "OCC_FLOOR_NEIGHBORHOOD_HI",
    "REGIME_JOIN_KEY",
    "close_ledger_row",
    "occupancy_floor_neighborhood",
]
