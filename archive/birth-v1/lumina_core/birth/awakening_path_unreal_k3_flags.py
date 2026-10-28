"""PATH_UNREAL_K3 U_3 / H_3 / W_3 universe and the single P_K3_UNREAL_RED flag."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.awakening_edge import policy_only_rows
from lumina_core.birth.awakening_open_split_flags import (
    MISSING_SHARE,
    SPLIT_LIFT,
    flag_s_missing_u,
    hole_from_u,
    missing_entry_share_policy,
    universe_rows,
    winners_from_u,
)
from lumina_core.birth.awakening_path_early_flags import (
    FAMILY_H_NONE,
    P_K3_UNREAL_RED,
    PATH_CANDIDATE_RAW_KEY,
    TAG_S_AB_DISAGREE,
    TAG_S_MISSING,
    TAG_S_MISSING_PATH,
    TAG_S_MULTI,
    TAG_S_NONE,
    TAG_S_SPLIT,
    TAG_S_THIN,
    flag_s_harm,
    flag_s_split,
    flag_s_thin_k,
    path_candidate_grid_row,
)
from lumina_core.birth.awakening_path_early_path import (
    compute_k_medians,
    field_present,
    pred_unreal_flip,
    pred_unreal_red,
    still_open_at_k,
    universe_k,
)

K_LOCKED = 3  # candidate lock: only k=3
CANDIDATE_NAMES = (P_K3_UNREAL_RED,)
RAW_KEY = PATH_CANDIDATE_RAW_KEY[P_K3_UNREAL_RED]
FAMILY_PATH_EXIT_P_K3_UNREAL_RED = "PATH_EXIT:P_K3_UNREAL_RED"
IMPORTED_SPLIT = (flag_s_split, SPLIT_LIFT)


def flag_s_missing_path_k3(universe: list[dict[str, Any]]) -> bool:
    """S_MISSING_PATH: path_k3_unreal_r missing on ≥0.20 of still_open_at_k(U, 3)."""
    alive = still_open_at_k(universe, K_LOCKED)
    if not alive:
        return True
    n_miss = sum(1 for r in alive if not field_present(r, RAW_KEY))
    return float(n_miss) / float(len(alive)) >= MISSING_SHARE - 1e-12


def missing_unreal_share_alive(universe: list[dict[str, Any]]) -> float:
    alive = still_open_at_k(universe, K_LOCKED)
    if not alive:
        return 1.0
    n_present = sum(1 for r in alive if field_present(r, RAW_KEY))
    return 1.0 - (float(n_present) / float(len(alive)))


def _u3_slice(universe: list[dict[str, Any]]) -> dict[str, Any]:
    alive = still_open_at_k(universe, K_LOCKED)
    u_3 = universe_k(universe, K_LOCKED)
    hole_3 = hole_from_u(u_3)
    winners_3 = winners_from_u(u_3)
    n_alive = len(alive)
    missing_share = missing_unreal_share_alive(universe)
    return {
        "alive": alive,
        "U_k": u_3,
        "H_k": hole_3,
        "W_k": winners_3,
        "n_Uk": len(u_3),
        "n_Hk": len(hole_3),
        "n_Wk": len(winners_3),
        "n_died_before_k": len(universe) - n_alive,
        "n_still_open": n_alive,
        "missing_share": float(missing_share),
        "S_THIN": flag_s_thin_k(n_h_k=len(hole_3), n_w_k=len(winners_3)),
        "medians": compute_k_medians(u_3, K_LOCKED),
    }


def compute_path_unreal_k3_flags(rows: list[dict[str, Any]]) -> dict[str, Any]:
    policy = policy_only_rows(rows)
    universe = universe_rows(policy)
    hole = hole_from_u(universe)
    winners = winners_from_u(universe)
    n_u = len(universe)
    miss_share = missing_entry_share_policy(policy)
    s_missing_u = flag_s_missing_u(missing_entry_share=miss_share, n_u=n_u) or n_u <= 0
    s_missing_path = flag_s_missing_path_k3(universe)
    sl = _u3_slice(universe)
    row = path_candidate_grid_row(
        sl["U_k"],
        sl["H_k"],
        sl["W_k"],
        name=P_K3_UNREAL_RED,
        s_missing_u=s_missing_u,
        s_missing_path=s_missing_path,
        s_thin_k=bool(sl["S_THIN"]),
        medians=sl["medians"],
    )
    candidates = {P_K3_UNREAL_RED: row}
    s_thin = bool(sl["S_THIN"])
    if s_missing_u or s_missing_path:
        tag = TAG_S_MISSING
        winning = "none"
    elif s_thin:
        tag = TAG_S_THIN
        winning = "none"
    elif bool(row["S_SPLIT"]) and not bool(row["S_HARM"]):
        tag = TAG_S_SPLIT
        winning = P_K3_UNREAL_RED
    else:
        tag = TAG_S_NONE
        winning = "none"
    u3_pub = {
        "n_Uk": sl["n_Uk"],
        "n_Hk": sl["n_Hk"],
        "n_Wk": sl["n_Wk"],
        "n_died_before_k": sl["n_died_before_k"],
        "n_still_open": sl["n_still_open"],
        "missing_share": sl["missing_share"],
        "S_THIN": sl["S_THIN"],
        "medians": sl["medians"],
    }
    return {
        "n_U": int(n_u),
        "n_H": int(len(hole)),
        "n_W": int(len(winners)),
        "n_died_before_3": int(sl["n_died_before_k"]),
        "U_3": u3_pub,
        "S_MISSING_U": bool(s_missing_u),
        "S_MISSING_PATH": bool(s_missing_path),
        "S_THIN": bool(s_thin),
        "winning_P": winning,
        "tag": tag,
        "candidates": candidates,
        "gate1": "NONE",
    }


def license_from_ab_k3(flags_a: dict[str, Any], flags_b: dict[str, Any]) -> dict[str, Any]:
    """A is SSOT. Miss / thin / none → H_NONE. Dual S_SPLIT → PATH_EXIT:P_K3_UNREAL_RED."""
    _ = TAG_S_MULTI  # unreachable: CANDIDATE_NAMES length is 1
    if bool(flags_a.get("S_MISSING_U")) or bool(flags_a.get("S_MISSING_PATH")):
        return {
            "tag": TAG_S_MISSING,
            "winning_P": "none",
            "licensed_next_family": FAMILY_H_NONE,
        }
    if bool(flags_a.get("S_THIN")) or str(flags_a.get("tag") or "") == TAG_S_THIN:
        return {
            "tag": TAG_S_THIN,
            "winning_P": "none",
            "licensed_next_family": FAMILY_H_NONE,
        }
    tag_a = str(flags_a.get("tag") or TAG_S_NONE)
    tag_b = str(flags_b.get("tag") or TAG_S_NONE)
    if tag_a == TAG_S_SPLIT:
        if tag_b == TAG_S_SPLIT:
            return {
                "tag": TAG_S_SPLIT,
                "winning_P": P_K3_UNREAL_RED,
                "licensed_next_family": FAMILY_PATH_EXIT_P_K3_UNREAL_RED,
            }
        return {
            "tag": TAG_S_AB_DISAGREE,
            "winning_P": "none",
            "licensed_next_family": FAMILY_H_NONE,
        }
    return {
        "tag": TAG_S_NONE,
        "winning_P": "none",
        "licensed_next_family": FAMILY_H_NONE,
    }


def flip_row(
    u_3: list[dict[str, Any]],
    hole_3: list[dict[str, Any]],
    winners_3: list[dict[str, Any]],
    *,
    s_missing_u: bool,
    s_missing_path: bool,
    s_thin_k: bool,
    medians: dict[str, float | None],
) -> dict[str, Any]:
    _ = pred_unreal_flip
    row = path_candidate_grid_row(
        u_3,
        hole_3,
        winners_3,
        name=P_K3_UNREAL_RED,
        s_missing_u=s_missing_u,
        s_missing_path=s_missing_path,
        s_thin_k=s_thin_k,
        medians=medians,
        flip=True,
    )
    return {
        "cov_H": row["cov_H"],
        "cov_W": row["cov_W"],
        "lift": row["lift"],
        "READ_ONLY_FLIP": True,
        "S_SPLIT": False,
    }


__all__ = [
    "CANDIDATE_NAMES",
    "FAMILY_H_NONE",
    "FAMILY_PATH_EXIT_P_K3_UNREAL_RED",
    "IMPORTED_SPLIT",
    "K_LOCKED",
    "P_K3_UNREAL_RED",
    "RAW_KEY",
    "TAG_S_AB_DISAGREE",
    "TAG_S_MISSING",
    "TAG_S_MISSING_PATH",
    "TAG_S_MULTI",
    "TAG_S_NONE",
    "TAG_S_SPLIT",
    "TAG_S_THIN",
    "compute_path_unreal_k3_flags",
    "flag_s_harm",
    "flag_s_missing_path_k3",
    "flag_s_split",
    "flag_s_thin_k",
    "flip_row",
    "license_from_ab_k3",
    "missing_unreal_share_alive",
    "pred_unreal_red",
]
