"""PATH_SHAPE K3 DEAD Gate 1 measure + Gate 2 transfer license. Do not retune #27/#28."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.awakening_edge import policy_only_rows
from lumina_core.birth.awakening_open_split_flags import (
    MISSING_SHARE,
    hole_from_u,
    universe_rows,
    winners_from_u,
)
from lumina_core.birth.awakening_path_early_flags import flag_s_harm, flag_s_split, flag_s_thin_k
from lumina_core.birth.awakening_path_early_path import opt_float, universe_k
from lumina_core.birth.awakening_path_exit_k3 import T_LOCK
from lumina_core.birth.awakening_path_exit_k3_flags import path_exit_k3_rows
from lumina_core.birth.awakening_path_exit_k3_t025 import T_FP
from lumina_core.birth.awakening_path_shape_k3_dead import (
    FAMILY,
    PathShapeK3DeadProtocolError,
    should_path_shape_k3_dead,
)

TAG_SHAPE_SPLIT = "SHAPE_SPLIT"
TAG_SHAPE_NONE = "SHAPE_NONE"
TAG_TRANSFER_OK = "TRANSFER_OK"
TAG_TRANSFER_FAIL = "TRANSFER_FAIL"
TAG_S_HARM = "S_HARM"
TAG_S_MISSING = "S_MISSING"


def pred_dead_row(row: dict[str, Any]) -> bool:
    return should_path_shape_k3_dead(
        enabled=True,
        is_policy=True,
        entry_regime=row.get("entry_regime"),
        bars_from_entry=3,
        unreal_r=opt_float(row, "path_k3_unreal_r"),
        mae_r=opt_float(row, "path_k3_mae_r"),
        mfe_r=opt_float(row, "path_k3_mfe_r"),
    )


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
        "EPS_SIT": 0.05,
        "MFE_LIFE": 0.25,
    }


def compute_shape_measure_flags(rows: list[dict[str, Any]]) -> dict[str, Any]:
    policy = policy_only_rows(rows)
    universe = universe_rows(policy)
    u3 = universe_k(universe, 3)
    h3 = hole_from_u(u3)
    w3 = winners_from_u(u3)
    n_u3 = len(u3)
    n_h3 = len(h3)
    n_w3 = len(w3)
    n_defined = sum(
        1
        for r in u3
        if opt_float(r, "path_k3_mae_r") is not None
        and opt_float(r, "path_k3_mfe_r") is not None
        and opt_float(r, "path_k3_unreal_r") is not None
    )
    if n_u3 <= 0:
        missing_share = 1.0
        missing = True
    else:
        missing_share = 1.0 - (float(n_defined) / float(n_u3))
        missing = missing_share >= MISSING_SHARE - 1e-12
    s_thin = flag_s_thin_k(n_h_k=n_h3, n_w_k=n_w3)
    n_h_hit = sum(1 for r in h3 if pred_dead_row(r))
    n_w_hit = sum(1 for r in w3 if pred_dead_row(r))
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
        "EPS_SIT": 0.05,
        "MFE_LIFE": 0.25,
    }


def license_shape(flags_a: dict[str, Any], flags_b: dict[str, Any]) -> dict[str, Any]:
    miss = bool(flags_a.get("S_MISSING")) or bool(flags_b.get("S_MISSING"))
    harm = bool(flags_a.get("S_HARM")) or bool(flags_b.get("S_HARM"))
    split_a = bool(flags_a.get("S_SPLIT"))
    split_b = bool(flags_b.get("S_SPLIT"))
    if miss:
        tag = TAG_S_MISSING
    elif harm:
        tag = TAG_S_HARM
    elif split_a and split_b:
        tag = TAG_SHAPE_SPLIT
    else:
        tag = TAG_SHAPE_NONE
    return {
        "tag": tag,
        "law": "NONE" if tag != TAG_SHAPE_SPLIT else "SHADOW",
        "licensed_next_family": FAMILY if tag == TAG_SHAPE_SPLIT else "H_NONE",
        "gate1": "NONE" if tag != TAG_SHAPE_SPLIT else "SHADOW",
        "S_SPLIT_A": split_a,
        "S_SPLIT_B": split_b,
        "S_HARM_A": bool(flags_a.get("S_HARM")),
        "S_HARM_B": bool(flags_b.get("S_HARM")),
    }


def license_transfer(flags_a: dict[str, Any], flags_b: dict[str, Any]) -> dict[str, Any]:
    moved_a = bool(flags_a.get("HOLE_MOVED"))
    moved_b = bool(flags_b.get("HOLE_MOVED"))
    if flags_a.get("S_MISSING_HOOK") or flags_b.get("S_MISSING_HOOK"):
        tag = TAG_S_MISSING
    elif flags_a.get("S_HARM") or flags_b.get("S_HARM"):
        tag = TAG_S_HARM
    elif moved_a and moved_b:
        tag = TAG_TRANSFER_OK
    else:
        tag = TAG_TRANSFER_FAIL
    return {
        "tag": tag,
        "law": "SHADOW",
        "licensed_next_family": FAMILY,
        "gate1": "SHADOW",
        "HOLE_MOVED_A": moved_a,
        "HOLE_MOVED_B": moved_b,
    }


def mean_stamped_threshold(rows: list[dict[str, Any]]) -> float | None:
    exits = path_exit_k3_rows(policy_only_rows(rows))
    vals: list[float] = []
    for row in exits:
        raw = row.get("path_exit_k3_threshold") if "path_exit_k3_threshold" in row else None
        if raw is None:
            continue
        try:
            vals.append(float(raw))
        except (TypeError, ValueError):
            continue
    if not vals:
        return None
    return float(sum(vals) / float(len(vals)))


def mean_stamped_shape(rows: list[dict[str, Any]]) -> str | None:
    exits = path_exit_k3_rows(policy_only_rows(rows))
    if not exits:
        return None
    shapes = [str(r.get("path_exit_k3_shape") or "") for r in exits]
    if shapes and all(s == "DEAD" for s in shapes):
        return "DEAD"
    return None


def assert_n_exit_not_tfamily_clone(
    *,
    n_exit_a: int,
    exits_a: list[dict[str, Any]] | None = None,
    mean_stamped_threshold_a: float | None = None,
) -> None:
    n = int(n_exit_a)
    if n >= 80:
        raise PathShapeK3DeadProtocolError("n_exit A >= 80 — hook is <=0 or broken")
    rows = list(exits_a or [])
    shape_missing = (not rows) or any(str(r.get("path_exit_k3_shape") or "") != "DEAD" for r in rows)
    stamped = None if mean_stamped_threshold_a is None else float(mean_stamped_threshold_a)
    if n > 0:
        if shape_missing:
            raise PathShapeK3DeadProtocolError("A exit missing path_exit_k3_shape==DEAD")
        for row in rows:
            if row.get("path_exit_k3_mae_r") is None or row.get("path_exit_k3_mfe_r") is None:
                raise PathShapeK3DeadProtocolError("A exit missing path_exit_k3 mae/mfe stamp")
        if stamped is not None and abs(stamped - T_LOCK) <= 1e-9:
            raise PathShapeK3DeadProtocolError("mean stamped path_exit_k3_threshold on A is T_LOCK")
        if stamped is not None and abs(stamped - T_FP) <= 1e-9 and shape_missing:
            raise PathShapeK3DeadProtocolError("mean stamped threshold is T_FP without DEAD shape")
    if n in {48, 49, 50, 51, 52} and shape_missing:
        raise PathShapeK3DeadProtocolError("n_exit A is a T_LOCK clone")
    if n in {28, 29, 30, 31, 32} and shape_missing and stamped is not None and abs(stamped - T_FP) <= 1e-9:
        raise PathShapeK3DeadProtocolError("n_exit A is a T025 clone")


__all__ = [
    "TAG_S_HARM",
    "TAG_S_MISSING",
    "TAG_SHAPE_NONE",
    "TAG_SHAPE_SPLIT",
    "TAG_TRANSFER_FAIL",
    "TAG_TRANSFER_OK",
    "assert_n_exit_not_tfamily_clone",
    "compute_shape_measure_flags",
    "empty_measure",
    "license_shape",
    "license_transfer",
    "mean_stamped_shape",
    "mean_stamped_threshold",
    "pred_dead_row",
]
