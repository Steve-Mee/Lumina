"""Open-stash telemetry for close ledgers. Not a participation law."""

from __future__ import annotations

from typing import Any

ENTRY_AUTOPSY_SOURCE = "awakening_entry_autopsy"
OPEN_SPLIT_SOURCE = "awakening_open_split"

OPEN_OPTIONAL_KEYS = (
    "open_occ_flat", "open_cum_flat", "open_in_band_seen", "open_session_phase",
    "open_confluence", "open_news_proximity", "open_imbalance", "open_range_stop_frac",
    "open_participation_mode", "open_policy_value", "open_policy_entropy",
    "open_policy_action_margin", "open_policy_p_chosen", "open_policy_margin_is_top2",
)
K_LOCKED = (3, 5)
PATH_R_KEYS = tuple(f"path_k{k}_{kind}_r" for k in K_LOCKED for kind in ("mae", "mfe", "unreal"))


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


def snapshot_path_at_k(stash: dict[str, Any], tick: dict[str, Any], bars_from_entry: int) -> None:
    """k-bar paper MAE/MFE/unreal. Omit missing. Never impute 0.0."""
    k = int(bars_from_entry)
    if k not in K_LOCKED:
        return
    for kind in ("mae", "mfe"):
        usd = stash.get(f"{kind}_usd")
        if usd is not None:
            stash[f"path_k{k}_{kind}_usd"] = float(usd)
    raw = tick.get("close", tick.get("last")) if isinstance(tick, dict) else None
    try:
        mark = float(raw) if raw is not None else None
        entry = float(stash.get("entry_price") or 0.0)
        side = int(stash.get("side") or 0)
    except (TypeError, ValueError):
        return
    if mark is None or side == 0 or entry <= 0.0:
        return
    from lumina_core.birth.notional_cap import birth_gym_point_value
    stash[f"path_k{k}_unreal_usd"] = (mark - entry) * float(side) * float(birth_gym_point_value())


def stamp_open_host(
    host: Any, occ_flat: float, in_band: bool, stage_flats: int, stage_sigs: int,
    flats: int, sigs: int, geometry: Any | None = None,
) -> None:
    """Mirror live rollout occupancy onto the env so gather_open_features can read it."""
    host.occupancy_control_flat = float(occ_flat)
    host.occupancy_in_band_seen = bool(in_band)
    host.stage_range_flat_bars = int(stage_flats)
    host.stage_range_total_signals = int(stage_sigs)
    host.range_flat_bars = int(flats)
    host.range_total_signals = int(sigs)
    if geometry is not None:
        host.geometry = geometry


def gather_open_features(
    host: Any,
    tick: dict[str, Any],
    info: dict[str, Any],
    entry_px: float,
) -> dict[str, Any]:
    """Read at-OPEN fields from the live host/tick. Omit missing. Never impute 0.0."""
    payload = info if isinstance(info, dict) else {}
    row = tick if isinstance(tick, dict) else {}
    out: dict[str, Any] = {}

    occ = getattr(host, "occupancy_control_flat", None)
    if occ is None:
        occ = payload.get("occupancy_control_flat")
    if occ is not None:
        try:
            out["open_occ_flat"] = float(occ)
        except (TypeError, ValueError):
            pass

    signals = getattr(host, "stage_range_total_signals", None) or getattr(host, "range_total_signals", None)
    flats = getattr(host, "stage_range_flat_bars", None)
    if flats is None:
        flats = getattr(host, "range_flat_bars", None)
    if signals not in (None, 0) and flats is not None:
        try:
            out["open_cum_flat"] = float(flats) / float(signals)
        except (TypeError, ValueError, ZeroDivisionError):
            pass

    in_band = getattr(host, "occupancy_in_band_seen", None)
    if in_band is None:
        in_band = payload.get("occupancy_in_band_seen")
    if in_band is not None:
        out["open_in_band_seen"] = bool(in_band)

    if "bible_session_phase" in row:
        try:
            out["open_session_phase"] = float(row.get("bible_session_phase"))
        except (TypeError, ValueError):
            pass
    if "bible_confluence" in row:
        try:
            out["open_confluence"] = float(row.get("bible_confluence"))
        except (TypeError, ValueError):
            pass
    if "bible_news_proximity" in row:
        try:
            out["open_news_proximity"] = float(row.get("bible_news_proximity"))
        except (TypeError, ValueError):
            pass
    if "imbalance" in row and row.get("imbalance") is not None:
        try:
            out["open_imbalance"] = float(row["imbalance"])
        except (TypeError, ValueError):
            pass

    mode = getattr(getattr(host, "config", None), "participation_mode", None)
    if mode is None:
        mode = payload.get("participation_mode")
    if mode is None:
        mode = getattr(host, "participation_mode", None)
    if mode is not None and str(mode) != "":
        out["open_participation_mode"] = str(mode)

    stop_pct = (
        float(getattr(getattr(host, "geometry", None), "stop_pct", 0.0) or 0.0)
        or float((getattr(host, "envelope", {}) or {}).get("participation_stop_pct") or 0.0)
        or float(payload.get("stop_pct") or 0.0)
    )
    hl = tick_hl(row)
    try:
        entry = float(entry_px)
    except (TypeError, ValueError):
        entry = 0.0
    if hl is not None and stop_pct > 0.0 and entry > 0.0:
        high, low = hl
        out["open_range_stop_frac"] = ((high - low) / max(entry, 1e-9)) / max(stop_pct, 1e-12)
    return out


def update_open_telem(
    stash: dict[str, Any] | None,
    env: Any,
    info: dict[str, Any],
    pos_before: int,
    pos_after: int,
    tick: dict[str, Any],
    ticks: list[dict[str, Any]],
    policy_signals: dict[str, float | None] | None = None,
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
        tick_open = ticks[idx_after] if ticks else {}
        regime = str(tick_open.get("regime") or "UNKNOWN") if ticks else "UNKNOWN"
        extras = gather_open_features(env, tick_open if isinstance(tick_open, dict) else {}, info, entry_px)
        psig = policy_signals or {}
        out = start_open_telem(
            entry_regime=regime,
            entry_bar_index=int(getattr(env, "_idx", 0) or 0),
            entry_price=entry_px,
            side=side_open,
            open_occ_flat=extras.get("open_occ_flat"),
            open_cum_flat=extras.get("open_cum_flat"),
            open_in_band_seen=extras.get("open_in_band_seen"),
            open_session_phase=extras.get("open_session_phase"),
            open_confluence=extras.get("open_confluence"),
            open_news_proximity=extras.get("open_news_proximity"),
            open_imbalance=extras.get("open_imbalance"),
            open_range_stop_frac=extras.get("open_range_stop_frac"),
            open_participation_mode=extras.get("open_participation_mode"),
            open_policy_value=psig.get("open_policy_value"),
            open_policy_entropy=psig.get("open_policy_entropy"),
            open_policy_action_margin=psig.get("open_policy_action_margin"),
            open_policy_p_chosen=psig.get("open_policy_p_chosen"),
            open_policy_margin_is_top2=psig.get("open_policy_margin_is_top2"),
        )
    if out is not None:
        apply_open_excursion(out, tick)
        try:
            bars_k = int(getattr(env, "_idx", 0) or 0) - int(out.get("entry_bar_index") or 0)
        except (TypeError, ValueError):
            bars_k = -1
        if (int(pos_before) != 0 or int(pos_after) != 0) and bars_k in K_LOCKED:
            snapshot_path_at_k(out, tick, bars_k)
    return out


def start_open_telem(
    *,
    entry_regime: str,
    entry_bar_index: int,
    entry_price: float,
    side: int,
    open_occ_flat: float | None = None,
    open_cum_flat: float | None = None,
    open_in_band_seen: bool | None = None,
    open_session_phase: float | None = None,
    open_confluence: float | None = None,
    open_news_proximity: float | None = None,
    open_imbalance: float | None = None,
    open_range_stop_frac: float | None = None,
    open_participation_mode: str | None = None,
    open_policy_value: float | None = None,
    open_policy_entropy: float | None = None,
    open_policy_action_margin: float | None = None,
    open_policy_p_chosen: float | None = None,
    open_policy_margin_is_top2: bool | None = None,
) -> dict[str, Any]:
    stash: dict[str, Any] = {
        "entry_regime": str(entry_regime or "UNKNOWN"),
        "entry_bar_index": int(entry_bar_index),
        "entry_price": float(entry_price),
        "side": int(side),
        "mae_usd": None,
        "mfe_usd": None,
    }
    optional: dict[str, Any] = {
        "open_occ_flat": open_occ_flat,
        "open_cum_flat": open_cum_flat,
        "open_in_band_seen": open_in_band_seen,
        "open_session_phase": open_session_phase,
        "open_confluence": open_confluence,
        "open_news_proximity": open_news_proximity,
        "open_imbalance": open_imbalance,
        "open_range_stop_frac": open_range_stop_frac,
        "open_participation_mode": open_participation_mode,
        "open_policy_value": open_policy_value,
        "open_policy_entropy": open_policy_entropy,
        "open_policy_action_margin": open_policy_action_margin,
        "open_policy_p_chosen": open_policy_p_chosen,
        "open_policy_margin_is_top2": open_policy_margin_is_top2,
    }
    for key, value in optional.items():
        if value is not None:
            stash[key] = value
    return stash


def _resolve_last_policy_stop_bar(
    last_policy_stop_bar: int | None,
    host: Any | None,
) -> int | None:
    if isinstance(last_policy_stop_bar, int):
        return int(last_policy_stop_bar)
    if host is None:
        return None
    raw = getattr(host, "_last_policy_stop_bar", None)
    if isinstance(raw, int):
        return int(raw)
    return None


def _note_policy_stop(
    host: Any | None,
    *,
    close_idx: int,
    info: dict[str, Any],
    closed_was_plant: bool | None,
) -> None:
    if host is None:
        return
    plant = (
        bool(closed_was_plant)
        if closed_was_plant is not None
        else bool((info or {}).get("plant_entry") or (info or {}).get("plant"))
    )
    reason = str((info or {}).get("close_reason") or "")
    if (not plant) and reason == "stop":
        host._last_policy_stop_bar = int(close_idx)


def close_open_telem(
    stash: dict[str, Any] | None,
    close_idx: int,
    close_regime: str,
    info: dict[str, Any],
    last_policy_stop_bar: int | None = None,
    source: str | None = None,
    host: Any | None = None,
    closed_was_plant: bool | None = None,
) -> dict[str, Any]:
    """Attach open-stash telemetry onto a close trajectory. Omit missing MAE."""
    src = str(source or ENTRY_AUTOPSY_SOURCE)
    last_stop = _resolve_last_policy_stop_bar(last_policy_stop_bar, host)
    if not stash:
        _note_policy_stop(host, close_idx=close_idx, info=info, closed_was_plant=closed_was_plant)
        return {"source": src}
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
        "source": src,
        "open_side": int(stash.get("side") or 0),
    }
    for key in OPEN_OPTIONAL_KEYS:
        if key in stash and stash.get(key) is not None:
            out[key] = stash.get(key)
    if isinstance(last_stop, int):
        out["bars_since_prev_policy_stop"] = max(0, entry_bar - last_stop)
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
    if denom is not None:
        for k in K_LOCKED:
            for kind in ("mae", "mfe", "unreal"):
                usd = stash.get(f"path_k{k}_{kind}_usd")
                if usd is not None:
                    out[f"path_k{k}_{kind}_r"] = float(usd) / denom
    _note_policy_stop(host, close_idx=close_idx, info=info, closed_was_plant=closed_was_plant)
    return out


__all__ = [
    "ENTRY_AUTOPSY_SOURCE", "K_LOCKED", "OPEN_OPTIONAL_KEYS", "OPEN_SPLIT_SOURCE",
    "PATH_R_KEYS", "apply_open_excursion", "close_open_telem", "gather_open_features",
    "snapshot_path_at_k", "stamp_open_host", "start_open_telem", "tick_hl",
    "update_open_telem",
]
