"""OPEN_POLICY_SIGNAL U/H/W universe and P_ candidate flags. Measure-only."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.awakening_edge import policy_only_rows
from lumina_core.birth.awakening_open_split_flags import (
    HARM_COV_W,
    HARM_LIFT,
    MISSING_SHARE,
    SPLIT_COV_H,
    SPLIT_LIFT,
    flag_s_missing_u,
    flag_s_thin,
    hole_from_u,
    missing_entry_share_policy,
    universe_rows,
    winners_from_u,
)

P_VALUE = "P_VALUE"  # low tail: open_policy_value <= median_U
P_ENTROPY = "P_ENTROPY"  # high tail: open_policy_entropy >= median_U
P_ACTION_MARGIN = "P_ACTION_MARGIN"  # low tail: open_policy_action_margin <= median_U

POLICY_CANDIDATE_NAMES = (P_VALUE, P_ENTROPY, P_ACTION_MARGIN)

POLICY_CANDIDATE_RAW_KEY = {
    P_VALUE: "open_policy_value",
    P_ENTROPY: "open_policy_entropy",
    P_ACTION_MARGIN: "open_policy_action_margin",
}

SIGNAL_KEYS = ("open_policy_value", "open_policy_entropy", "open_policy_action_margin")

FAMILY_H_NONE = "H_NONE"

TAG_S_SPLIT = "S_SPLIT"
TAG_S_MULTI = "S_MULTI"
TAG_S_NONE = "S_NONE"
TAG_S_MISSING = "S_MISSING"
TAG_S_THIN = "S_THIN"
TAG_S_AB_DISAGREE = "S_AB_DISAGREE"
TAG_S_MISSING_SIGNAL = "S_MISSING_SIGNAL"

# Empty-list median placeholders only. Never used as a decision threshold on defined data.
VALUE_MEDIAN_THRESHOLD = 0.0
ENTROPY_LOW_THRESHOLD = 0.5
ACTION_MARGIN_HIGH_THRESHOLD = 0.3


def _field_present(row: dict[str, Any], key: str) -> bool:
    return key in row and row.get(key) is not None


def _opt_float(row: dict[str, Any], key: str) -> float | None:
    if not _field_present(row, key):
        return None
    try:
        return float(row.get(key))
    except (TypeError, ValueError):
        return None


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def compute_adaptive_thresholds(universe: list[dict[str, Any]]) -> dict[str, float]:
    """Median of U where the field is present. Does not use H/W labels."""
    vals_v: list[float] = []
    vals_e: list[float] = []
    vals_m: list[float] = []
    for row in universe:
        v = _opt_float(row, "open_policy_value")
        if v is not None:
            vals_v.append(v)
        e = _opt_float(row, "open_policy_entropy")
        if e is not None:
            vals_e.append(e)
        m = _opt_float(row, "open_policy_action_margin")
        if m is not None:
            vals_m.append(m)
    return {
        "value_median": _median(vals_v) if vals_v else VALUE_MEDIAN_THRESHOLD,
        "entropy_median": _median(vals_e) if vals_e else ENTROPY_LOW_THRESHOLD,
        "action_margin_median": _median(vals_m) if vals_m else ACTION_MARGIN_HIGH_THRESHOLD,
    }


def pred_value_below_median(row: dict[str, Any], *, threshold: float) -> bool:
    """P_VALUE: value <= median_U (inclusive low tail)."""
    value = _opt_float(row, "open_policy_value")
    if value is None:
        return False
    return float(value) <= float(threshold)


def pred_entropy_high(row: dict[str, Any], *, threshold: float) -> bool:
    """P_ENTROPY: entropy >= median_U (inclusive high tail)."""
    value = _opt_float(row, "open_policy_entropy")
    if value is None:
        return False
    return float(value) >= float(threshold)


def pred_action_margin_low(row: dict[str, Any], *, threshold: float) -> bool:
    """P_ACTION_MARGIN: margin <= median_U (inclusive low tail)."""
    value = _opt_float(row, "open_policy_action_margin")
    if value is None:
        return False
    return float(value) <= float(threshold)


def pred_value_flip(row: dict[str, Any], *, threshold: float) -> bool:
    value = _opt_float(row, "open_policy_value")
    if value is None:
        return False
    return float(value) > float(threshold)


def pred_entropy_flip(row: dict[str, Any], *, threshold: float) -> bool:
    value = _opt_float(row, "open_policy_entropy")
    if value is None:
        return False
    return float(value) < float(threshold)


def pred_action_margin_flip(row: dict[str, Any], *, threshold: float) -> bool:
    value = _opt_float(row, "open_policy_action_margin")
    if value is None:
        return False
    return float(value) > float(threshold)


def flag_s_missing_signal(universe: list[dict[str, Any]]) -> bool:
    """S_MISSING_SIGNAL: share of U missing all three signal keys >= 0.20."""
    n_u = len(universe)
    if n_u <= 0:
        return True
    n_miss = sum(1 for r in universe if all(not _field_present(r, k) for k in SIGNAL_KEYS))
    return float(n_miss) / float(n_u) >= MISSING_SHARE - 1e-12


def flag_s_split(
    *,
    s_missing_u: bool,
    s_thin: bool,
    missing: bool,
    cov_h: float,
    lift: float,
    s_missing_signal: bool = False,
) -> bool:
    return (
        (not bool(s_missing_u))
        and (not bool(s_missing_signal))
        and (not bool(s_thin))
        and (not bool(missing))
        and float(cov_h) >= SPLIT_COV_H - 1e-12
        and float(lift) >= SPLIT_LIFT - 1e-12
    )


def flag_s_harm(
    *,
    s_missing_u: bool,
    s_thin: bool,
    missing: bool,
    cov_w: float,
    lift: float,
    s_missing_signal: bool = False,
) -> bool:
    return (
        (not bool(s_missing_u))
        and (not bool(s_missing_signal))
        and (not bool(s_thin))
        and (not bool(missing))
        and float(cov_w) >= HARM_COV_W - 1e-12
        and float(lift) <= HARM_LIFT + 1e-12
    )


def _hits_for_name(
    hole: list[dict[str, Any]],
    winners: list[dict[str, Any]],
    *,
    name: str,
    thr: float,
    flip: bool,
) -> tuple[int, int]:
    if name == P_VALUE:
        pred = pred_value_flip if flip else pred_value_below_median
    elif name == P_ENTROPY:
        pred = pred_entropy_flip if flip else pred_entropy_high
    elif name == P_ACTION_MARGIN:
        pred = pred_action_margin_flip if flip else pred_action_margin_low
    else:
        return 0, 0
    return (
        sum(1 for r in hole if pred(r, threshold=float(thr))),
        sum(1 for r in winners if pred(r, threshold=float(thr))),
    )


def policy_candidate_grid_row(
    universe: list[dict[str, Any]],
    hole: list[dict[str, Any]],
    winners: list[dict[str, Any]],
    *,
    name: str,
    s_missing_u: bool,
    s_thin: bool,
    thresholds: dict[str, float],
    s_missing_signal: bool = False,
    flip: bool = False,
) -> dict[str, Any]:
    raw_key = POLICY_CANDIDATE_RAW_KEY[name]
    n_u = len(universe)
    n_h = len(hole)
    n_w = len(winners)
    n_defined = sum(1 for r in universe if _field_present(r, raw_key))
    if n_u <= 0:
        missing_share = 1.0
        missing = True
        n_defined = 0
    else:
        missing_share = 1.0 - (float(n_defined) / float(n_u))
        missing = missing_share >= MISSING_SHARE - 1e-12
    if name == P_VALUE:
        thr = thresholds.get("value_median", VALUE_MEDIAN_THRESHOLD) if n_defined else VALUE_MEDIAN_THRESHOLD
    elif name == P_ENTROPY:
        thr = thresholds.get("entropy_median", ENTROPY_LOW_THRESHOLD) if n_defined else ENTROPY_LOW_THRESHOLD
    elif name == P_ACTION_MARGIN:
        thr = (
            thresholds.get("action_margin_median", ACTION_MARGIN_HIGH_THRESHOLD)
            if n_defined
            else ACTION_MARGIN_HIGH_THRESHOLD
        )
    else:
        thr = 0.0
    n_h_hit, n_w_hit = _hits_for_name(hole, winners, name=name, thr=float(thr), flip=flip)
    cov_h = float(n_h_hit) / float(max(n_h, 1))
    cov_w = float(n_w_hit) / float(max(n_w, 1))
    lift = cov_h - cov_w
    return {
        "threshold": float(thr),
        "missing": bool(missing),
        "missing_share": float(missing_share),
        "n_defined": int(n_defined),
        "cov_H": float(cov_h),
        "cov_W": float(cov_w),
        "lift": float(lift),
        "S_SPLIT": False
        if flip
        else flag_s_split(
            s_missing_u=s_missing_u,
            s_thin=s_thin,
            missing=missing,
            cov_h=cov_h,
            lift=lift,
            s_missing_signal=s_missing_signal,
        ),
        "S_HARM": False
        if flip
        else flag_s_harm(
            s_missing_u=s_missing_u,
            s_thin=s_thin,
            missing=missing,
            cov_w=cov_w,
            lift=lift,
            s_missing_signal=s_missing_signal,
        ),
        "drop_H": float(cov_h) * float(n_h),
        "drop_W": float(cov_w) * float(n_w),
        "remaining_H": float(n_h) - float(cov_h) * float(n_h),
        "remaining_W": float(n_w) - float(cov_w) * float(n_w),
        "READ_ONLY_FLIP": bool(flip),
    }


def compute_open_policy_signal_flags(rows: list[dict[str, Any]]) -> dict[str, Any]:
    policy = policy_only_rows(rows)
    universe = universe_rows(policy)
    hole = hole_from_u(universe)
    winners = winners_from_u(universe)
    n_u = len(universe)
    n_h = len(hole)
    n_w = len(winners)
    miss_share = missing_entry_share_policy(policy)
    s_missing_u = flag_s_missing_u(missing_entry_share=miss_share, n_u=n_u) or n_u <= 0
    s_missing_signal = flag_s_missing_signal(universe)
    s_thin = flag_s_thin(n_h=n_h, n_w=n_w)
    thresholds = compute_adaptive_thresholds(universe)
    candidates: dict[str, Any] = {}
    split_names: list[str] = []
    for name in POLICY_CANDIDATE_NAMES:
        row = policy_candidate_grid_row(
            universe,
            hole,
            winners,
            name=name,
            s_missing_u=s_missing_u,
            s_thin=s_thin,
            thresholds=thresholds,
            s_missing_signal=s_missing_signal,
        )
        candidates[name] = row
        if bool(row["S_SPLIT"]) and not bool(row["S_HARM"]):
            split_names.append(name)
    if s_missing_u:
        tag = TAG_S_MISSING
        winning = "none"
    elif s_missing_signal:
        tag = TAG_S_MISSING
        winning = "none"
    elif s_thin:
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
    return {
        "n_U": int(n_u),
        "n_H": int(n_h),
        "n_W": int(n_w),
        "S_MISSING_U": bool(s_missing_u),
        "S_MISSING_SIGNAL": bool(s_missing_signal),
        "S_THIN": bool(s_thin),
        "winning_P": winning,
        "tag": tag,
        "candidates": candidates,
        "thresholds": thresholds,
        "gate1": "NONE",
    }


def license_from_ab(flags_a: dict[str, Any], flags_b: dict[str, Any]) -> dict[str, Any]:
    """Leg A is SSOT. Miss / none / thin / multi / disagree → H_NONE. Never ENTRY family."""
    win_a = str(flags_a.get("winning_P") or "none")
    win_b = str(flags_b.get("winning_P") or "none")
    licensed_next_family = FAMILY_H_NONE
    if bool(flags_a.get("S_MISSING_U")) or bool(flags_a.get("S_MISSING_SIGNAL")):
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
            "licensed_next_family": f"OPEN_FILTER:POLICY_{win_a}",
        }
    return {"tag": TAG_S_NONE, "winning_P": "none", "licensed_next_family": licensed_next_family}


__all__ = [
    "ACTION_MARGIN_HIGH_THRESHOLD",
    "ENTROPY_LOW_THRESHOLD",
    "FAMILY_H_NONE",
    "POLICY_CANDIDATE_NAMES",
    "POLICY_CANDIDATE_RAW_KEY",
    "P_ACTION_MARGIN",
    "P_ENTROPY",
    "P_VALUE",
    "SIGNAL_KEYS",
    "TAG_S_AB_DISAGREE",
    "TAG_S_MISSING",
    "TAG_S_MISSING_SIGNAL",
    "TAG_S_MULTI",
    "TAG_S_NONE",
    "TAG_S_SPLIT",
    "TAG_S_THIN",
    "VALUE_MEDIAN_THRESHOLD",
    "compute_adaptive_thresholds",
    "compute_open_policy_signal_flags",
    "flag_s_harm",
    "flag_s_missing_signal",
    "flag_s_split",
    "license_from_ab",
    "policy_candidate_grid_row",
    "pred_action_margin_low",
    "pred_entropy_high",
    "pred_value_below_median",
]
