"""PATH_EARLY U_k / H_k / W_k universe and locked P_ candidate flags. Measure-only."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.awakening_edge import policy_only_rows
from lumina_core.birth.awakening_open_split_flags import (
    HARM_COV_W,
    HARM_LIFT,
    MISSING_SHARE,
    N_H_MIN,
    N_W_MIN,
    SPLIT_COV_H,
    SPLIT_LIFT,
    flag_s_missing_u,
    hole_from_u,
    missing_entry_share_policy,
    universe_rows,
    winners_from_u,
)
from lumina_core.birth.awakening_path_early_path import (
    compute_k_medians,
    field_present,
    pred_mae_deep,
    pred_mae_flip,
    pred_unreal_flip,
    pred_unreal_red,
    snapshot_present,
    still_open_at_k,
    universe_k,
)

K_LOCKED = (3, 5)

P_K3_MAE_DEEP = "P_K3_MAE_DEEP"
P_K3_UNREAL_RED = "P_K3_UNREAL_RED"
P_K5_MAE_DEEP = "P_K5_MAE_DEEP"
P_K5_UNREAL_RED = "P_K5_UNREAL_RED"

PATH_CANDIDATE_NAMES = (P_K3_MAE_DEEP, P_K3_UNREAL_RED, P_K5_MAE_DEEP, P_K5_UNREAL_RED)

PATH_CANDIDATE_RAW_KEY = {
    P_K3_MAE_DEEP: "path_k3_mae_r",
    P_K3_UNREAL_RED: "path_k3_unreal_r",
    P_K5_MAE_DEEP: "path_k5_mae_r",
    P_K5_UNREAL_RED: "path_k5_unreal_r",
}

PATH_CANDIDATE_K = {
    P_K3_MAE_DEEP: 3,
    P_K3_UNREAL_RED: 3,
    P_K5_MAE_DEEP: 5,
    P_K5_UNREAL_RED: 5,
}

FAMILY_H_NONE = "H_NONE"

TAG_S_SPLIT = "S_SPLIT"
TAG_S_MULTI = "S_MULTI"
TAG_S_NONE = "S_NONE"
TAG_S_MISSING = "S_MISSING"
TAG_S_THIN = "S_THIN"
TAG_S_AB_DISAGREE = "S_AB_DISAGREE"
TAG_S_MISSING_PATH = "S_MISSING_PATH"


def flag_s_thin_k(*, n_h_k: int, n_w_k: int) -> bool:
    return int(n_h_k) < N_H_MIN or int(n_w_k) < N_W_MIN


def flag_s_missing_path(universe: list[dict[str, Any]]) -> bool:
    """S_MISSING_PATH: for both k, snapshot missing on ≥0.20 of bars_held>=k rows."""
    misses: list[bool] = []
    for k in K_LOCKED:
        alive = still_open_at_k(universe, k)
        if not alive:
            misses.append(True)
            continue
        n_miss = sum(1 for r in alive if not snapshot_present(r, k))
        misses.append(float(n_miss) / float(len(alive)) >= MISSING_SHARE - 1e-12)
    return all(misses)


def flag_s_split(
    *,
    s_missing_u: bool,
    s_missing_path: bool,
    s_thin_k: bool,
    missing: bool,
    cov_h: float,
    lift: float,
) -> bool:
    return (
        (not bool(s_missing_u))
        and (not bool(s_missing_path))
        and (not bool(s_thin_k))
        and (not bool(missing))
        and float(cov_h) >= SPLIT_COV_H - 1e-12
        and float(lift) >= SPLIT_LIFT - 1e-12
    )


def flag_s_harm(
    *,
    s_missing_u: bool,
    s_missing_path: bool,
    s_thin_k: bool,
    missing: bool,
    cov_w: float,
    lift: float,
) -> bool:
    return (
        (not bool(s_missing_u))
        and (not bool(s_missing_path))
        and (not bool(s_thin_k))
        and (not bool(missing))
        and float(cov_w) >= HARM_COV_W - 1e-12
        and float(lift) <= HARM_LIFT + 1e-12
    )


def _hits_for_name(
    hole: list[dict[str, Any]],
    winners: list[dict[str, Any]],
    *,
    name: str,
    thr: float | None,
    flip: bool,
) -> tuple[int, int]:
    k = PATH_CANDIDATE_K[name]
    if name in {P_K3_MAE_DEEP, P_K5_MAE_DEEP}:
        pred = pred_mae_flip if flip else pred_mae_deep
    elif name in {P_K3_UNREAL_RED, P_K5_UNREAL_RED}:
        pred = pred_unreal_flip if flip else pred_unreal_red
    else:
        return 0, 0
    return (
        sum(1 for r in hole if pred(r, k=k, threshold=thr)),
        sum(1 for r in winners if pred(r, k=k, threshold=thr)),
    )


def path_candidate_grid_row(
    u_k: list[dict[str, Any]],
    hole_k: list[dict[str, Any]],
    winners_k: list[dict[str, Any]],
    *,
    name: str,
    s_missing_u: bool,
    s_missing_path: bool,
    s_thin_k: bool,
    medians: dict[str, float | None],
    flip: bool = False,
) -> dict[str, Any]:
    raw_key = PATH_CANDIDATE_RAW_KEY[name]
    n_u = len(u_k)
    n_h = len(hole_k)
    n_w = len(winners_k)
    n_defined = sum(1 for r in u_k if field_present(r, raw_key))
    if n_u <= 0:
        missing_share = 1.0
        missing = True
        n_defined = 0
    else:
        missing_share = 1.0 - (float(n_defined) / float(n_u))
        missing = missing_share >= MISSING_SHARE - 1e-12
    if name in {P_K3_MAE_DEEP, P_K5_MAE_DEEP}:
        thr = medians.get("mae_r") if n_defined else None
    else:
        thr = medians.get("unreal_r") if n_defined else None
    n_h_hit, n_w_hit = _hits_for_name(hole_k, winners_k, name=name, thr=thr, flip=flip)
    cov_h = float(n_h_hit) / float(max(n_h, 1))
    cov_w = float(n_w_hit) / float(max(n_w, 1))
    lift = cov_h - cov_w
    return {
        "threshold": thr,
        "missing": bool(missing),
        "missing_share": float(missing_share),
        "n_defined": int(n_defined),
        "cov_H": float(cov_h),
        "cov_W": float(cov_w),
        "lift": float(lift),
        "S_THIN": bool(s_thin_k),
        "S_SPLIT": False
        if flip
        else flag_s_split(
            s_missing_u=s_missing_u,
            s_missing_path=s_missing_path,
            s_thin_k=s_thin_k,
            missing=missing,
            cov_h=cov_h,
            lift=lift,
        ),
        "S_HARM": False
        if flip
        else flag_s_harm(
            s_missing_u=s_missing_u,
            s_missing_path=s_missing_path,
            s_thin_k=s_thin_k,
            missing=missing,
            cov_w=cov_w,
            lift=lift,
        ),
        "drop_H": float(cov_h) * float(n_h),
        "drop_W": float(cov_w) * float(n_w),
        "remaining_H": float(n_h) - float(cov_h) * float(n_h),
        "remaining_W": float(n_w) - float(cov_w) * float(n_w),
        "READ_ONLY_FLIP": bool(flip),
    }


def _k_slice(universe: list[dict[str, Any]], k: int) -> dict[str, Any]:
    alive = still_open_at_k(universe, k)
    u_k = universe_k(universe, k)
    hole_k = hole_from_u(u_k)
    winners_k = winners_from_u(u_k)
    n_alive = len(alive)
    n_miss = sum(1 for r in alive if not snapshot_present(r, k)) if n_alive else n_alive
    missing_share = 1.0 if n_alive <= 0 else float(n_miss) / float(n_alive)
    return {
        "alive": alive,
        "U_k": u_k,
        "H_k": hole_k,
        "W_k": winners_k,
        "n_Uk": len(u_k),
        "n_Hk": len(hole_k),
        "n_Wk": len(winners_k),
        "n_died_before_k": len(universe) - n_alive,
        "n_still_open": n_alive,
        "missing_share": float(missing_share),
        "S_THIN": flag_s_thin_k(n_h_k=len(hole_k), n_w_k=len(winners_k)),
        "medians": compute_k_medians(u_k, k),
    }


def compute_path_early_flags(rows: list[dict[str, Any]]) -> dict[str, Any]:
    policy = policy_only_rows(rows)
    universe = universe_rows(policy)
    hole = hole_from_u(universe)
    winners = winners_from_u(universe)
    n_u = len(universe)
    miss_share = missing_entry_share_policy(policy)
    s_missing_u = flag_s_missing_u(missing_entry_share=miss_share, n_u=n_u) or n_u <= 0
    s_missing_path = flag_s_missing_path(universe)
    slices: dict[int, dict[str, Any]] = {k: _k_slice(universe, k) for k in K_LOCKED}
    candidates: dict[str, Any] = {}
    split_names: list[str] = []
    for name in PATH_CANDIDATE_NAMES:
        k = PATH_CANDIDATE_K[name]
        sl = slices[k]
        row = path_candidate_grid_row(
            sl["U_k"],
            sl["H_k"],
            sl["W_k"],
            name=name,
            s_missing_u=s_missing_u,
            s_missing_path=s_missing_path,
            s_thin_k=bool(sl["S_THIN"]),
            medians=sl["medians"],
        )
        candidates[name] = row
        if bool(row["S_SPLIT"]) and not bool(row["S_HARM"]):
            split_names.append(name)
    both_thin = all(bool(slices[k]["S_THIN"]) for k in K_LOCKED)
    if s_missing_u or s_missing_path:
        tag = TAG_S_MISSING
        winning = "none"
    elif both_thin:
        tag = TAG_S_THIN
        winning = "none"
    elif len(split_names) >= 2:
        tag = TAG_S_MULTI
        winning = "none"
    elif len(split_names) == 1:
        tag = TAG_S_SPLIT
        winning = split_names[0]
    else:
        tag = TAG_S_NONE
        winning = "none"
    k_pub = {
        k: {
            "n_Uk": sl["n_Uk"],
            "n_Hk": sl["n_Hk"],
            "n_Wk": sl["n_Wk"],
            "n_died_before_k": sl["n_died_before_k"],
            "n_still_open": sl["n_still_open"],
            "missing_share": sl["missing_share"],
            "S_THIN": sl["S_THIN"],
            "medians": sl["medians"],
        }
        for k, sl in slices.items()
    }
    return {
        "n_U": int(n_u),
        "n_H": int(len(hole)),
        "n_W": int(len(winners)),
        "S_MISSING_U": bool(s_missing_u),
        "S_MISSING_PATH": bool(s_missing_path),
        "S_THIN": bool(both_thin),
        "winning_P": winning,
        "tag": tag,
        "candidates": candidates,
        "k": k_pub,
        "gate1": "NONE",
    }


def license_from_ab(flags_a: dict[str, Any], flags_b: dict[str, Any]) -> dict[str, Any]:
    """Leg A is SSOT. Miss / none / thin / multi / disagree → H_NONE. Never the closed open-time family."""
    win_a = str(flags_a.get("winning_P") or "none")
    win_b = str(flags_b.get("winning_P") or "none")
    licensed_next_family = FAMILY_H_NONE
    if bool(flags_a.get("S_MISSING_U")) or bool(flags_a.get("S_MISSING_PATH")):
        return {"tag": TAG_S_MISSING, "winning_P": "none", "licensed_next_family": licensed_next_family}
    if bool(flags_a.get("S_THIN")):
        return {"tag": TAG_S_THIN, "winning_P": "none", "licensed_next_family": licensed_next_family}
    tag_a = str(flags_a.get("tag") or TAG_S_NONE)
    if tag_a == TAG_S_MULTI:
        return {"tag": TAG_S_MULTI, "winning_P": "none", "licensed_next_family": licensed_next_family}
    if tag_a == TAG_S_SPLIT:
        if win_a != win_b:
            return {"tag": TAG_S_AB_DISAGREE, "winning_P": "none", "licensed_next_family": licensed_next_family}
        return {
            "tag": TAG_S_SPLIT,
            "winning_P": win_a,
            "licensed_next_family": f"PATH_EXIT:{win_a}",
        }
    return {"tag": TAG_S_NONE, "winning_P": "none", "licensed_next_family": licensed_next_family}


__all__ = [
    "FAMILY_H_NONE",
    "K_LOCKED",
    "PATH_CANDIDATE_NAMES",
    "PATH_CANDIDATE_RAW_KEY",
    "P_K3_MAE_DEEP",
    "P_K3_UNREAL_RED",
    "P_K5_MAE_DEEP",
    "P_K5_UNREAL_RED",
    "TAG_S_AB_DISAGREE",
    "TAG_S_MISSING",
    "TAG_S_MISSING_PATH",
    "TAG_S_MULTI",
    "TAG_S_NONE",
    "TAG_S_SPLIT",
    "TAG_S_THIN",
    "compute_path_early_flags",
    "flag_s_harm",
    "flag_s_missing_path",
    "flag_s_split",
    "flag_s_thin_k",
    "license_from_ab",
    "path_candidate_grid_row",
]
