"""PATH_EXIT K3 shadow triggers: HOLE_MOVED / S_HARM / S_MISSING_HOOK. Do not retune."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.awakening_edge import policy_only_rows
from lumina_core.birth.awakening_mech import bucket_stats
from lumina_core.birth.awakening_open_split_flags import hole_from_u, universe_rows, winners_from_u
from lumina_core.birth.awakening_path_early_path import still_open_at_k
from lumina_core.birth.awakening_path_exit_k3 import FAMILY, K_LOCKED, LAW_NONE, LAW_SHADOW

TAG_HOLE_MOVED = "HOLE_MOVED"
TAG_HOLE_INTACT = "HOLE_INTACT"
TAG_S_HARM = "S_HARM"
TAG_S_MISSING = "S_MISSING"
TAG_S_THIN = "S_THIN"


def path_exit_k3_rows(policy: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in policy if bool(r.get("path_exit_k3"))]


def flag_s_missing_hook(*, n_exit: int, n_still_open_at_3_baseline: int) -> bool:
    return int(n_exit) == 0 and int(n_still_open_at_3_baseline) >= 60


def flag_s_harm(*, n_w_shadow: int, n_w_base: int, n_h_shadow: int, n_h_base: int) -> bool:
    return int(n_w_shadow) <= int(n_w_base) - 20 and int(n_h_shadow) >= int(n_h_base) - 5


def flag_hole_moved(
    *,
    s_missing_hook: bool,
    s_harm: bool,
    n_h_shadow: int,
    n_h_base: int,
    mean_r_policy_shadow: float,
    mean_r_policy_base: float,
) -> bool:
    return (
        (not bool(s_missing_hook))
        and (not bool(s_harm))
        and int(n_h_shadow) <= int(n_h_base) - 15
        and float(mean_r_policy_shadow) >= float(mean_r_policy_base) + 0.05
    )


def flag_s_thin(*, n_policy: int) -> bool:
    return int(n_policy) < 100


def _mean_r(rows: list[dict[str, Any]]) -> float:
    return float(bucket_stats(rows)["mean_r"])


def _wr(rows: list[dict[str, Any]]) -> float:
    return float(bucket_stats(rows)["wr"])


def baseline_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    policy = policy_only_rows(rows)
    universe = universe_rows(policy)
    hole = hole_from_u(universe)
    winners = winners_from_u(universe)
    alive = still_open_at_k(universe, K_LOCKED)
    pol = bucket_stats(policy)
    return {
        "n_H": int(len(hole)),
        "mean_r_H": _mean_r(hole),
        "n_W": int(len(winners)),
        "mean_r_W": _mean_r(winners),
        "n_policy": int(len(policy)),
        "wr_policy": float(pol["wr"]),
        "mean_r_policy": float(pol["mean_r"]),
        "n_still_open_at_3": int(len(alive)),
        "present": True,
    }


def empty_baseline() -> dict[str, Any]:
    return {
        "n_H": 0,
        "mean_r_H": 0.0,
        "n_W": 0,
        "mean_r_W": 0.0,
        "n_policy": 0,
        "wr_policy": 0.0,
        "mean_r_policy": 0.0,
        "n_still_open_at_3": 0,
        "present": False,
    }


def compute_path_exit_k3_flags(
    rows: list[dict[str, Any]],
    *,
    baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy_only_rows(rows)
    universe = universe_rows(policy)
    hole = hole_from_u(universe)
    winners = winners_from_u(universe)
    exits = path_exit_k3_rows(policy)
    pol = bucket_stats(policy)
    base = dict(baseline or empty_baseline())
    n_exit = len(exits)
    n_h = len(hole)
    n_w = len(winners)
    n_policy = len(policy)
    mean_r_policy = float(pol["mean_r"])
    s_missing_base = not bool(base.get("present"))
    s_missing_hook = flag_s_missing_hook(
        n_exit=n_exit,
        n_still_open_at_3_baseline=int(base.get("n_still_open_at_3") or 0),
    )
    if s_missing_base:
        s_missing_hook = True
    s_harm = flag_s_harm(
        n_w_shadow=n_w,
        n_w_base=int(base.get("n_W") or 0),
        n_h_shadow=n_h,
        n_h_base=int(base.get("n_H") or 0),
    )
    hole_moved = flag_hole_moved(
        s_missing_hook=s_missing_hook,
        s_harm=s_harm,
        n_h_shadow=n_h,
        n_h_base=int(base.get("n_H") or 0),
        mean_r_policy_shadow=mean_r_policy,
        mean_r_policy_base=float(base.get("mean_r_policy") or 0.0),
    )
    s_thin = flag_s_thin(n_policy=n_policy)
    if s_missing_hook or s_missing_base:
        tag = TAG_S_MISSING
        law = LAW_NONE
    elif s_harm:
        tag = TAG_S_HARM
        law = LAW_SHADOW
    elif hole_moved:
        tag = TAG_HOLE_MOVED
        law = LAW_SHADOW
    else:
        tag = TAG_HOLE_INTACT
        law = LAW_SHADOW
    return {
        "n_policy": int(n_policy),
        "n_U": int(len(universe)),
        "n_H": int(n_h),
        "mean_r_H": _mean_r(hole),
        "n_W": int(n_w),
        "mean_r_W": _mean_r(winners),
        "n_exit": int(n_exit),
        "mean_r_exit": _mean_r(exits),
        "wr_exit": _wr(exits),
        "wr_policy": float(pol["wr"]),
        "mean_r_policy": mean_r_policy,
        "mean_usd_policy": float(pol["mean_usd"]),
        "S_MISSING_HOOK": bool(s_missing_hook),
        "S_HARM": bool(s_harm),
        "HOLE_MOVED": bool(hole_moved),
        "S_THIN": bool(s_thin),
        "tag": tag,
        "law": law,
        "family": FAMILY,
        "gate1": LAW_SHADOW,
        "baseline": base,
    }


def license_from_a(flags_a: dict[str, Any], flags_b: dict[str, Any]) -> dict[str, Any]:
    """A is SSOT. Print B. Law is SHADOW when scored, never silent default-on."""
    _ = flags_b
    tag = str(flags_a.get("tag") or TAG_S_MISSING)
    law = str(flags_a.get("law") or LAW_NONE)
    return {
        "tag": tag,
        "law": law,
        "licensed_next_family": FAMILY,
        "gate1": law,
    }


__all__ = [
    "FAMILY",
    "TAG_HOLE_INTACT",
    "TAG_HOLE_MOVED",
    "TAG_S_HARM",
    "TAG_S_MISSING",
    "TAG_S_THIN",
    "baseline_from_rows",
    "compute_path_exit_k3_flags",
    "empty_baseline",
    "flag_hole_moved",
    "flag_s_harm",
    "flag_s_missing_hook",
    "flag_s_thin",
    "license_from_a",
    "path_exit_k3_rows",
]
