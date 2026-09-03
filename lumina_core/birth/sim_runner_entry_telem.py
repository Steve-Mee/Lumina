"""Open-stash telemetry for close ledgers. Not a participation law."""

from __future__ import annotations

from typing import Any

ENTRY_AUTOPSY_SOURCE = "awakening_entry_autopsy"


def tick_hl(tick: dict[str, Any]) -> tuple[float, float] | None:
    """High/low as present on the fixture tick. Missing → skip, do not invent OHLC."""
    if "high" not in tick or "low" not in tick:
        return None
    high_raw = tick.get("high")
    low_raw = tick.get("low")
    if high_raw is None or low_raw is None:
        return None
    try:
        return float(high_raw), float(low_raw)
    except (TypeError, ValueError):
        return None


def apply_open_excursion(stash: dict[str, Any], tick: dict[str, Any]) -> None:
    """Paper MAE/MFE vs entry, qty=1 MES $5. Adverse ≤ 0, favorable ≥ 0."""
    hl = tick_hl(tick)
    if hl is None:
        return
    high, low = hl
    try:
        entry = float(stash.get("entry_price") or 0.0)
        side = int(stash.get("side") or 0)
    except (TypeError, ValueError):
        return
    if side == 0 or entry <= 0.0:
        return
    from lumina_core.birth.notional_cap import birth_gym_point_value

    pv = float(birth_gym_point_value())
    pnl_h = (high - entry) * float(side) * 1.0 * pv
    pnl_l = (low - entry) * float(side) * 1.0 * pv
    adverse = min(0.0, min(pnl_h, pnl_l))
    favorable = max(0.0, max(pnl_h, pnl_l))
    prev_mae = stash.get("mae_usd")
    prev_mfe = stash.get("mfe_usd")
    stash["mae_usd"] = adverse if prev_mae is None else min(float(prev_mae), adverse)
    stash["mfe_usd"] = favorable if prev_mfe is None else max(float(prev_mfe), favorable)


def update_open_telem(
    stash: dict[str, Any] | None,
    env: Any,
    info: dict[str, Any],
    pos_before: int,
    pos_after: int,
    tick: dict[str, Any],
    ticks: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Stash open-state when flat→open (incl. same-bar close). Apply bar excursion."""
    opened = int(pos_before) == 0 and (int(pos_after) != 0 or bool(info.get("trade_closed")))
    out = stash
    if opened and out is None:
        side_open = int(pos_after) if int(pos_after) != 0 else int(getattr(env, "_entry_side", 0) or 0)
        try:
            entry_px = float(getattr(env, "_entry_price", 0.0) or 0.0)
        except (TypeError, ValueError):
            entry_px = 0.0
        if entry_px <= 0.0:
            try:
                entry_px = float(info.get("entry_price") or 0.0)
            except (TypeError, ValueError):
                entry_px = 0.0
        idx_after = min(int(getattr(env, "_idx", 0) or 0), max(0, len(ticks) - 1))
        regime = str(ticks[idx_after].get("regime") or "UNKNOWN") if ticks else "UNKNOWN"
        out = start_open_telem(
            entry_regime=regime,
            entry_bar_index=int(getattr(env, "_idx", 0) or 0),
            entry_price=entry_px,
            side=side_open,
        )
    if out is not None:
        apply_open_excursion(out, tick)
    return out


def start_open_telem(
    *,
    entry_regime: str,
    entry_bar_index: int,
    entry_price: float,
    side: int,
) -> dict[str, Any]:
    return {
        "entry_regime": str(entry_regime or "UNKNOWN"),
        "entry_bar_index": int(entry_bar_index),
        "entry_price": float(entry_price),
        "side": int(side),
        "mae_usd": None,
        "mfe_usd": None,
    }


def close_open_telem(
    stash: dict[str, Any] | None,
    close_idx: int,
    close_regime: str,
    info: dict[str, Any],
) -> dict[str, Any]:
    """Attach open-stash telemetry onto a close trajectory. Omit missing MAE."""
    if not stash:
        return {"source": ENTRY_AUTOPSY_SOURCE}
    entry_regime = str(stash.get("entry_regime") or "UNKNOWN")
    try:
        entry_bar = int(stash.get("entry_bar_index") or 0)
    except (TypeError, ValueError):
        entry_bar = 0
    close_bar = int(close_idx)
    out: dict[str, Any] = {
        "entry_regime": entry_regime,
        "entry_bar_index": entry_bar,
        "close_bar_index": close_bar,
        "bars_held": max(0, close_bar - entry_bar),
        "regime_flip": entry_regime.upper() != str(close_regime or "").upper(),
        "source": ENTRY_AUTOPSY_SOURCE,
    }
    risk_usd = info.get("intended_risk_usd", info.get("risk_usd"))
    try:
        intended = float(risk_usd) if risk_usd is not None else None
    except (TypeError, ValueError):
        intended = None
    denom = max(float(intended), 1e-9) if intended is not None else None
    mae_usd = stash.get("mae_usd")
    mfe_usd = stash.get("mfe_usd")
    if mae_usd is not None and denom is not None:
        out["mae_r"] = float(mae_usd) / denom
    if mfe_usd is not None and denom is not None:
        out["mfe_r"] = float(mfe_usd) / denom
    return out


__all__ = [
    "ENTRY_AUTOPSY_SOURCE",
    "apply_open_excursion",
    "close_open_telem",
    "start_open_telem",
    "tick_hl",
    "update_open_telem",
]
