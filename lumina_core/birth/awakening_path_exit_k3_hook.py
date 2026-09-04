"""Live PATH_EXIT K3 arm/stamp. Uses existing force_flatten close path."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.awakening_path_exit_k3 import (
    K_LOCKED,
    path_exit_k3_shadow_enabled,
    path_exit_k3_threshold,
    should_path_exit_k3,
)
from lumina_core.birth.awakening_path_shape_k3_dead import (
    FAMILY as SHAPE_FAMILY,
    PathShapeK3DeadProtocolError,
    path_shape_k3_shadow_enabled,
    should_path_shape_k3_dead,
)
from lumina_core.birth.awakening_path_shape_k3_dead_peek import _peek_excursion_usd, _r_from_usd


def _open_intended_risk(env: Any, stash: dict[str, Any]) -> float | None:
    try:
        entry = float(stash.get("entry_price") or 0.0)
        stop_pct = float(getattr(env, "_entry_stop_pct", 0.0) or 0.0)
    except (TypeError, ValueError):
        return None
    if entry <= 0.0 or stop_pct <= 0.0:
        return None
    from lumina_core.birth.foundation_metrics import intended_risk_usd
    from lumina_core.birth.notional_cap import birth_gym_point_value

    return float(
        intended_risk_usd(
            stop_pct=stop_pct,
            entry_price=entry,
            qty=1,
            point_value=float(birth_gym_point_value()),
        )
    )


def _unreal_usd_from_tick(stash: dict[str, Any], tick: dict[str, Any] | None) -> float | None:
    if not isinstance(tick, dict):
        return None
    raw = tick.get("close", tick.get("last"))
    try:
        mark = float(raw) if raw is not None else None
        entry = float(stash.get("entry_price") or 0.0)
        side = int(stash.get("side") or 0)
    except (TypeError, ValueError):
        return None
    if mark is None or side == 0 or entry <= 0.0:
        return None
    from lumina_core.birth.notional_cap import birth_gym_point_value

    return (mark - entry) * float(side) * float(birth_gym_point_value())


def _unreal_r(stash: dict[str, Any], env: Any, usd: float | None) -> float | None:
    if usd is None:
        return None
    denom = _open_intended_risk(env, stash)
    if denom is None or denom <= 0.0:
        return None
    return float(usd) / float(denom)


def after_open_telem_path_exit_k3(
    stash: dict[str, Any],
    env: Any,
    ticks: list[dict[str, Any]],
    info: dict[str, Any],
    bars_from_entry: int,
    pos_after: int,
) -> None:
    """Arm next-bar flatten at k=2; stamp sidecar after the k=3 snapshot."""
    shape_on = path_shape_k3_shadow_enabled()
    t_on = path_exit_k3_shadow_enabled()
    if shape_on and t_on:
        raise PathShapeK3DeadProtocolError("T-family shadow and shape shadow both on")
    is_policy = bool(stash.get("is_policy", False))
    entry_regime = str(stash.get("entry_regime") or "")
    bars = int(bars_from_entry)
    if bars == 2 and int(pos_after) != 0 and (shape_on or t_on):
        try:
            nxt_idx = int(getattr(env, "_idx", 0) or 0)
            nxt = ticks[nxt_idx] if ticks and 0 <= nxt_idx < len(ticks) else None
        except (TypeError, ValueError, IndexError):
            nxt = None
        peek_unreal_usd = _unreal_usd_from_tick(stash, nxt)
        peek_unreal_r = _unreal_r(stash, env, peek_unreal_usd)
        peek_mae_usd, peek_mfe_usd = _peek_excursion_usd(stash, nxt)
        intended = _open_intended_risk(env, stash)
        peek_mae_r = _r_from_usd(peek_mae_usd, intended)
        peek_mfe_r = _r_from_usd(peek_mfe_usd, intended)
        if shape_on and should_path_shape_k3_dead(
            enabled=True,
            is_policy=is_policy,
            entry_regime=entry_regime,
            bars_from_entry=K_LOCKED,
            unreal_r=peek_unreal_r,
            mae_r=peek_mae_r,
            mfe_r=peek_mfe_r,
        ):
            env._path_exit_k3_request = True
        elif t_on and should_path_exit_k3(
            enabled=True,
            is_policy=is_policy,
            entry_regime=entry_regime,
            bars_from_entry=K_LOCKED,
            unreal_r=peek_unreal_r,
        ):
            env._path_exit_k3_request = True
    if bars != K_LOCKED:
        return
    usd = stash.get("path_k3_unreal_usd")
    try:
        unreal_r = _unreal_r(stash, env, float(usd) if usd is not None else None)
    except (TypeError, ValueError):
        unreal_r = None
    if unreal_r is not None:
        stash["path_k3_unreal_r"] = float(unreal_r)
    requested = bool(getattr(env, "_path_exit_k3_request", False))
    reason = str((info or {}).get("close_reason") or "")
    if requested and reason == "force_exit" and unreal_r is not None:
        stash["path_exit_k3"] = True
        stash["path_exit_k3_unreal_r"] = float(unreal_r)
        if shape_on:
            intended = _open_intended_risk(env, stash)
            stash["path_exit_k3_mae_r"] = _r_from_usd(stash.get("mae_usd"), intended)
            stash["path_exit_k3_mfe_r"] = _r_from_usd(stash.get("mfe_usd"), intended)
            stash["path_exit_k3_shape"] = "DEAD"
            stash["path_exit_k3_family"] = SHAPE_FAMILY
        else:
            stash["path_exit_k3_threshold"] = path_exit_k3_threshold()
    env._path_exit_k3_request = False


__all__ = ["after_open_telem_path_exit_k3"]
