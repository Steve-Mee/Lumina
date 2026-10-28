"""SELECT_OBJ P_BOUNCE_WEAK Gate 1 measure + license. Law is always NONE."""

from __future__ import annotations

import math
from typing import Any

from lumina_core.birth.awakening_edge import policy_only_rows
from lumina_core.birth.awakening_open_split_flags import (
    MISSING_SHARE,
    hole_from_u,
    universe_rows,
    winners_from_u,
)
from lumina_core.birth.awakening_path_early_flags import flag_s_harm, flag_s_split, flag_s_thin_k
from lumina_core.birth.awakening_path_early_path import median_values, universe_k
from lumina_core.birth.awakening_select_obj_bounce import (
    BOUNCE_WEAK,
    FAMILY,
    bounce_r,
    pred_bounce_weak,
)

TAG_OBJ_SPLIT = "OBJ_SPLIT"
TAG_OBJ_NONE = "OBJ_NONE"
TAG_S_HARM = "S_HARM"
TAG_S_MISSING = "S_MISSING"


def percentile_nearest_rank(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile. index = floor((n-1)*q) after sort."""
    if not values:
        return None
    ordered = sorted(values)
    idx = int(math.floor((len(ordered) - 1) * float(q)))
    return float(ordered[idx])


def bounce_defined_values(rows: list[dict[str, Any]]) -> list[float]:
    out: list[float] = []
    for row in rows:
        value = bounce_r(row)
        if value is not None:
            out.append(float(value))
    return out


def bounce_dist(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    vals = bounce_defined_values(rows)
    return {
        "p10": percentile_nearest_rank(vals, 0.10),
        "p50": median_values(vals),
        "p90": percentile_nearest_rank(vals, 0.90),
        "min": (min(vals) if vals else None),
    }


def empty_measure(*, missing: bool = True) -> dict[str, Any]:
    return {
        "n_U3": 0,
        "n_H3": 0,
        "n_W3": 0,
        "n_defined": 0,
        "missing_share": 1.0,
        "n_h_hit": 0,
        "n_w_hit": 0,
        "cov_H": 0.0,
        "cov_W": 0.0,
        "lift": 0.0,
        "S_SPLIT": False,
        "S_HARM": False,
        "S_THIN": True,
        "S_MISSING": bool(missing),
        "bounce_p10_H": None,
        "bounce_p50_H": None,
        "bounce_p90_H": None,
        "bounce_p10_W": None,
        "bounce_p50_W": None,
        "bounce_p90_W": None,
        "bounce_p10_U": None,
        "bounce_p50_U": None,
        "bounce_p90_U": None,
        "min_bounce_U": None,
        "BOUNCE_WEAK": float(BOUNCE_WEAK),
    }


def compute_obj_bounce_flags(rows: list[dict[str, Any]]) -> dict[str, Any]:
    policy = policy_only_rows(rows)
    universe = universe_rows(policy)
    u3 = universe_k(universe, 3)
    h3 = hole_from_u(u3)
    w3 = winners_from_u(u3)
    n_u3 = len(u3)
    n_h3 = len(h3)
    n_w3 = len(w3)
    n_defined = sum(1 for r in u3 if bounce_r(r) is not None)
    if n_u3 <= 0:
        missing_share = 1.0
        missing = True
    else:
        missing_share = 1.0 - (float(n_defined) / float(n_u3))
        missing = missing_share >= MISSING_SHARE - 1e-12
    s_thin = flag_s_thin_k(n_h_k=n_h3, n_w_k=n_w3)
    n_h_hit = sum(1 for r in h3 if pred_bounce_weak(r))
    n_w_hit = sum(1 for r in w3 if pred_bounce_weak(r))
    cov_h = float(n_h_hit) / float(max(n_h3, 1))
    cov_w = float(n_w_hit) / float(max(n_w3, 1))
    lift = cov_h - cov_w
    s_split = flag_s_split(
        s_missing_u=False,
        s_missing_path=False,
        s_thin_k=s_thin,
        missing=missing,
        cov_h=cov_h,
        lift=lift,
    )
    s_harm = flag_s_harm(
        s_missing_u=False,
        s_missing_path=False,
        s_thin_k=s_thin,
        missing=missing,
        cov_w=cov_w,
        lift=lift,
    )
    dist_h = bounce_dist(h3)
    dist_w = bounce_dist(w3)
    dist_u = bounce_dist(u3)
    return {
        "n_U3": int(n_u3),
        "n_H3": int(n_h3),
        "n_W3": int(n_w3),
        "n_defined": int(n_defined),
        "missing_share": float(missing_share),
        "n_h_hit": int(n_h_hit),
        "n_w_hit": int(n_w_hit),
        "cov_H": float(cov_h),
        "cov_W": float(cov_w),
        "lift": float(lift),
        "S_SPLIT": bool(s_split),
        "S_HARM": bool(s_harm),
        "S_THIN": bool(s_thin),
        "S_MISSING": bool(missing),
        "bounce_p10_H": dist_h["p10"],
        "bounce_p50_H": dist_h["p50"],
        "bounce_p90_H": dist_h["p90"],
        "bounce_p10_W": dist_w["p10"],
        "bounce_p50_W": dist_w["p50"],
        "bounce_p90_W": dist_w["p90"],
        "bounce_p10_U": dist_u["p10"],
        "bounce_p50_U": dist_u["p50"],
        "bounce_p90_U": dist_u["p90"],
        "min_bounce_U": dist_u["min"],
        "BOUNCE_WEAK": float(BOUNCE_WEAK),
    }


def license_obj(flags_a: dict[str, Any], flags_b: dict[str, Any]) -> dict[str, Any]:
    miss = bool(flags_a.get("S_MISSING")) or bool(flags_b.get("S_MISSING"))
    harm = bool(flags_a.get("S_HARM")) or bool(flags_b.get("S_HARM"))
    split_a = bool(flags_a.get("S_SPLIT"))
    split_b = bool(flags_b.get("S_SPLIT"))
    if miss:
        tag = TAG_S_MISSING
    elif harm:
        tag = TAG_S_HARM
    elif split_a and split_b:
        tag = TAG_OBJ_SPLIT
    else:
        tag = TAG_OBJ_NONE
    return {
        "tag": tag,
        "law": "NONE",
        "licensed_next_family": FAMILY if tag == TAG_OBJ_SPLIT else "H_NONE",
        "gate1": "NONE",
        "S_SPLIT_A": split_a,
        "S_SPLIT_B": split_b,
        "S_HARM_A": bool(flags_a.get("S_HARM")),
        "S_HARM_B": bool(flags_b.get("S_HARM")),
    }


__all__ = [
    "TAG_OBJ_NONE",
    "TAG_OBJ_SPLIT",
    "TAG_S_HARM",
    "TAG_S_MISSING",
    "bounce_defined_values",
    "bounce_dist",
    "compute_obj_bounce_flags",
    "empty_measure",
    "license_obj",
    "percentile_nearest_rank",
]
