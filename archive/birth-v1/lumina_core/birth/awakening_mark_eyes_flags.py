"""MARK_EYES Gate 3 license. HOLE_MOVED requires both legs. Import #27 algebra."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.awakening_edge import policy_only_rows
from lumina_core.birth.awakening_mark_eyes import (
    DELTA_H_MIN,
    DELTA_MEAN_R_MIN,
    FAMILY,
    LAW_NONE,
    LAW_SHADOW,
    PATH_EARLY_A_MEAN_R,
    PATH_EARLY_A_N_H,
    PATH_EARLY_B_MEAN_R,
    PATH_EARLY_B_N_H,
    TAG_EYES_FAIL,
    TAG_EYES_OK,
    TAG_S_HARM,
    TAG_S_MISSING,
)
from lumina_core.birth.awakening_mech import bucket_stats
from lumina_core.birth.awakening_open_split_flags import hole_from_u, universe_rows, winners_from_u
from lumina_core.birth.awakening_path_exit_k3_flags import flag_hole_moved
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES


def flag_s_harm_eyes(
    *,
    n_h_child: int,
    n_h_base: int,
    mean_r_child: float,
    mean_r_base: float,
) -> bool:
    """mean_r drop >= 0.05 AND n_H not down 15."""
    mean_drop = float(mean_r_base) - float(mean_r_child)
    hole_drop = int(n_h_base) - int(n_h_child)
    return mean_drop >= float(DELTA_MEAN_R_MIN) and hole_drop < int(DELTA_H_MIN)


def hole_moved_leg(
    *,
    n_h_child: int,
    n_h_base: int,
    mean_r_child: float,
    mean_r_base: float,
    n_policy_child: int,
    s_missing_hook: bool = False,
    s_harm: bool = False,
) -> bool:
    if int(n_policy_child) < int(POLICY_EDGE_MIN_TRADES):
        return False
    return bool(
        flag_hole_moved(
            s_missing_hook=bool(s_missing_hook),
            s_harm=bool(s_harm),
            n_h_shadow=int(n_h_child),
            n_h_base=int(n_h_base),
            mean_r_policy_shadow=float(mean_r_child),
            mean_r_policy_base=float(mean_r_base),
        )
    )


def empty_leg(*, missing: bool = False, leg: str = "A") -> dict[str, Any]:
    early_h = PATH_EARLY_A_N_H if str(leg).upper() == "A" else PATH_EARLY_B_N_H
    early_r = PATH_EARLY_A_MEAN_R if str(leg).upper() == "A" else PATH_EARLY_B_MEAN_R
    return {
        "n_policy": 0,
        "wr_policy": 0.0,
        "mean_r_policy": 0.0,
        "n_H": 0,
        "n_W": 0,
        "n_H_early": int(early_h),
        "mean_r_early": float(early_r),
        "delta_n_H": 0,
        "delta_mean_r": 0.0,
        "HOLE_MOVED": False,
        "S_MISSING": bool(missing),
        "S_MISSING_HOOK": bool(missing),
        "S_HARM": False,
        "S_THIN": True,
    }


def compute_mark_eyes_leg(
    rows: list[dict[str, Any]],
    *,
    baseline: dict[str, Any],
    missing: bool = False,
) -> dict[str, Any]:
    policy = policy_only_rows(rows)
    universe = universe_rows(policy)
    hole = hole_from_u(universe)
    winners = winners_from_u(universe)
    pol = bucket_stats(policy)
    n_policy = int(len(policy))
    n_h = int(len(hole))
    n_w = int(len(winners))
    mean_r = float(pol["mean_r"])
    n_h_early = int(baseline.get("n_H") or 0)
    mean_r_early = float(baseline.get("mean_r_policy") or 0.0)
    s_missing = bool(missing) or not bool(baseline.get("present", True))
    s_thin = n_policy < int(POLICY_EDGE_MIN_TRADES)
    s_harm = flag_s_harm_eyes(
        n_h_child=n_h,
        n_h_base=n_h_early,
        mean_r_child=mean_r,
        mean_r_base=mean_r_early,
    )
    moved = hole_moved_leg(
        n_h_child=n_h,
        n_h_base=n_h_early,
        mean_r_child=mean_r,
        mean_r_base=mean_r_early,
        n_policy_child=n_policy,
        s_missing_hook=s_missing,
        s_harm=s_harm,
    )
    return {
        "n_policy": n_policy,
        "wr_policy": float(pol["wr"]),
        "mean_r_policy": mean_r,
        "n_H": n_h,
        "n_W": n_w,
        "n_H_early": n_h_early,
        "mean_r_early": mean_r_early,
        "delta_n_H": int(n_h_early) - int(n_h),
        "delta_mean_r": float(mean_r) - float(mean_r_early),
        "HOLE_MOVED": bool(moved),
        "S_MISSING": bool(s_missing),
        "S_MISSING_HOOK": bool(s_missing),
        "S_HARM": bool(s_harm),
        "S_THIN": bool(s_thin),
    }


def license_eyes(flags_a: dict[str, Any], flags_b: dict[str, Any]) -> dict[str, Any]:
    miss = (
        bool(flags_a.get("S_MISSING"))
        or bool(flags_b.get("S_MISSING"))
        or bool(flags_a.get("S_MISSING_HOOK"))
        or bool(flags_b.get("S_MISSING_HOOK"))
    )
    harm = bool(flags_a.get("S_HARM")) or bool(flags_b.get("S_HARM"))
    moved_a = bool(flags_a.get("HOLE_MOVED"))
    moved_b = bool(flags_b.get("HOLE_MOVED"))
    if miss:
        tag = TAG_S_MISSING
        law = LAW_NONE
        family = "H_NONE"
    elif harm:
        tag = TAG_S_HARM
        law = LAW_NONE
        family = "H_NONE"
    elif moved_a and moved_b:
        tag = TAG_EYES_OK
        law = LAW_SHADOW
        family = FAMILY
    else:
        tag = TAG_EYES_FAIL
        law = LAW_NONE
        family = "H_NONE"
    return {
        "tag": tag,
        "law": law,
        "licensed_next_family": family,
        "HOLE_MOVED_A": moved_a,
        "HOLE_MOVED_B": moved_b,
        "evolution_proof_stamped": False,
    }


__all__ = [
    "compute_mark_eyes_leg",
    "empty_leg",
    "flag_s_harm_eyes",
    "hole_moved_leg",
    "license_eyes",
]
