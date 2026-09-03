"""OPEN_SPLIT U/H/W universe and locked F_ / S_ flags. Measure-only. No controller."""

from __future__ import annotations

from typing import Any, Callable

from lumina_core.birth.awakening_edge import policy_only_rows
from lumina_core.birth.s5_close_ledger_trace import occupancy_floor_neighborhood

MISSING_SHARE = 0.20
N_U_MIN = 60
N_H_MIN = 40
N_W_MIN = 20
SPLIT_COV_H = 0.50
SPLIT_LIFT = 0.25
HARM_COV_W = 0.50
HARM_LIFT = -0.10
AFTER_STOP_BARS = 8
TIGHT_RANGE = 0.50
IMBAL_EPS = 0.02

FAMILY_OPEN_DECISION = "OPEN_DECISION"
FAMILY_H_NONE = "H_NONE"
TAG_S_SPLIT = "S_SPLIT"
TAG_S_MULTI = "S_MULTI"
TAG_S_NONE = "S_NONE"
TAG_S_MISSING = "S_MISSING"
TAG_S_THIN = "S_THIN"
TAG_S_AB_DISAGREE = "S_AB_DISAGREE"

F_OCC_FLOOR = "F_OCC_FLOOR"
F_SESSION_EARLY = "F_SESSION_EARLY"
F_TIGHT_RANGE = "F_TIGHT_RANGE"
F_AFTER_STOP = "F_AFTER_STOP"
F_IMBAL_FLAT = "F_IMBAL_FLAT"

CANDIDATE_NAMES = (
    F_OCC_FLOOR,
    F_SESSION_EARLY,
    F_TIGHT_RANGE,
    F_AFTER_STOP,
    F_IMBAL_FLAT,
)

CANDIDATE_RAW_KEY = {
    F_OCC_FLOOR: "open_occ_flat",
    F_SESSION_EARLY: "open_session_phase",
    F_TIGHT_RANGE: "open_range_stop_frac",
    F_AFTER_STOP: "bars_since_prev_policy_stop",
    F_IMBAL_FLAT: "open_imbalance",
}


def _field_present(row: dict[str, Any], key: str) -> bool:
    return key in row and row.get(key) is not None


def _opt_float(row: dict[str, Any], key: str) -> float | None:
    if not _field_present(row, key):
        return None
    try:
        return float(row.get(key))
    except (TypeError, ValueError):
        return None


def pred_occ_floor(row: dict[str, Any]) -> bool:
    """F_OCC_FLOOR: open_occ_flat in occupancy_floor_neighborhood [0.25, 0.30]."""
    value = _opt_float(row, "open_occ_flat")
    if value is None:
        return False
    return occupancy_floor_neighborhood(value)


def pred_session_early(row: dict[str, Any]) -> bool:
    """F_SESSION_EARLY: open_session_phase <= 1e-12 (bar_index < 120)."""
    value = _opt_float(row, "open_session_phase")
    if value is None:
        return False
    return float(value) <= 1e-12


def pred_tight_range(row: dict[str, Any]) -> bool:
    """F_TIGHT_RANGE: open_range_stop_frac < 0.50."""
    value = _opt_float(row, "open_range_stop_frac")
    if value is None:
        return False
    return float(value) < TIGHT_RANGE


def pred_after_stop(row: dict[str, Any]) -> bool:
    """F_AFTER_STOP: bars_since_prev_policy_stop <= 8."""
    value = _opt_float(row, "bars_since_prev_policy_stop")
    if value is None:
        return False
    return float(value) <= float(AFTER_STOP_BARS)


def pred_imbal_flat(row: dict[str, Any]) -> bool:
    """F_IMBAL_FLAT: abs(open_imbalance - 1.0) < 0.02. Missing imbalance cannot win."""
    value = _opt_float(row, "open_imbalance")
    if value is None:
        return False
    return abs(float(value) - 1.0) < IMBAL_EPS


PREDICATES: dict[str, Callable[[dict[str, Any]], bool]] = {
    F_OCC_FLOOR: pred_occ_floor,
    F_SESSION_EARLY: pred_session_early,
    F_TIGHT_RANGE: pred_tight_range,
    F_AFTER_STOP: pred_after_stop,
    F_IMBAL_FLAT: pred_imbal_flat,
}


def universe_rows(policy: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in policy if str(r.get("entry_regime") or "").upper() == "NEUTRAL"]


def hole_from_u(universe: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        r
        for r in universe
        if str(r.get("close_reason") or "") == "stop" and str(r.get("regime") or "").upper() == "NEUTRAL"
    ]


def winners_from_u(universe: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in universe:
        reason = str(row.get("close_reason") or "")
        if reason == "target":
            out.append(row)
            continue
        if reason == "time_stop":
            try:
                if float(row.get("trade_r")) > 0.0:
                    out.append(row)
            except (TypeError, ValueError):
                continue
    return out


def missing_entry_share_policy(policy: list[dict[str, Any]]) -> float:
    n = len(policy)
    if n <= 0:
        return 0.0
    n_miss = sum(1 for r in policy if not _field_present(r, "entry_regime"))
    return float(n_miss) / float(n)


def flag_s_missing_u(*, missing_entry_share: float, n_u: int) -> bool:
    """S_MISSING_U = (missing entry_regime on policy >= 0.20) OR n_U < 60."""
    return float(missing_entry_share) >= MISSING_SHARE - 1e-12 or int(n_u) < N_U_MIN


def flag_s_thin(*, n_h: int, n_w: int) -> bool:
    return int(n_h) < N_H_MIN or int(n_w) < N_W_MIN


def flag_s_split(
    *,
    s_missing_u: bool,
    s_thin: bool,
    missing: bool,
    cov_h: float,
    lift: float,
) -> bool:
    """S_SPLIT(F): not missing-U, not thin, F defined, cov_H >= 0.50, lift >= 0.25."""
    return (
        (not bool(s_missing_u))
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
) -> bool:
    """S_HARM(F): not missing-U, not thin, F defined, cov_W >= 0.50, lift <= -0.10."""
    return (
        (not bool(s_missing_u))
        and (not bool(s_thin))
        and (not bool(missing))
        and float(cov_w) >= HARM_COV_W - 1e-12
        and float(lift) <= HARM_LIFT + 1e-12
    )


def candidate_grid_row(
    universe: list[dict[str, Any]],
    hole: list[dict[str, Any]],
    winners: list[dict[str, Any]],
    *,
    name: str,
    s_missing_u: bool,
    s_thin: bool,
) -> dict[str, Any]:
    raw_key = CANDIDATE_RAW_KEY[name]
    pred = PREDICATES[name]
    n_u = len(universe)
    n_h = len(hole)
    n_w = len(winners)
    n_defined = sum(1 for r in universe if _field_present(r, raw_key))
    missing_share = 0.0 if n_u <= 0 else 1.0 - (float(n_defined) / float(n_u))
    missing = missing_share >= MISSING_SHARE - 1e-12
    n_h_hit = sum(1 for r in hole if pred(r))
    n_w_hit = sum(1 for r in winners if pred(r))
    cov_h = float(n_h_hit) / float(max(n_h, 1))
    cov_w = float(n_w_hit) / float(max(n_w, 1))
    lift = cov_h - cov_w
    return {
        "missing": bool(missing),
        "missing_share": float(missing_share),
        "n_defined": int(n_defined),
        "cov_H": float(cov_h),
        "cov_W": float(cov_w),
        "lift": float(lift),
        "S_SPLIT": flag_s_split(s_missing_u=s_missing_u, s_thin=s_thin, missing=missing, cov_h=cov_h, lift=lift),
        "S_HARM": flag_s_harm(s_missing_u=s_missing_u, s_thin=s_thin, missing=missing, cov_w=cov_w, lift=lift),
        "drop_H": float(cov_h) * float(n_h),
        "drop_W": float(cov_w) * float(n_w),
        "remaining_H": float(n_h) - float(cov_h) * float(n_h),
        "remaining_W": float(n_w) - float(cov_w) * float(n_w),
    }


def compute_open_split_flags(rows: list[dict[str, Any]]) -> dict[str, Any]:
    policy = policy_only_rows(rows)
    universe = universe_rows(policy)
    hole = hole_from_u(universe)
    winners = winners_from_u(universe)
    n_u = len(universe)
    n_h = len(hole)
    n_w = len(winners)
    miss_share = missing_entry_share_policy(policy)
    s_missing_u = flag_s_missing_u(missing_entry_share=miss_share, n_u=n_u)
    s_thin = flag_s_thin(n_h=n_h, n_w=n_w)
    candidates: dict[str, Any] = {}
    split_names: list[str] = []
    for name in CANDIDATE_NAMES:
        row = candidate_grid_row(universe, hole, winners, name=name, s_missing_u=s_missing_u, s_thin=s_thin)
        candidates[name] = row
        if bool(row["S_SPLIT"]) and not bool(row["S_HARM"]):
            split_names.append(name)
    if s_missing_u:
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
        "S_THIN": bool(s_thin),
        "winning_F": winning,
        "tag": tag,
        "candidates": candidates,
        "gate1": "NONE",
    }


def license_from_ab(flags_a: dict[str, Any], flags_b: dict[str, Any]) -> dict[str, Any]:
    """Leg A is SSOT. B cannot invent a law. Disagree on winning F name → S_AB_DISAGREE."""
    win_a = str(flags_a.get("winning_F") or "none")
    win_b = str(flags_b.get("winning_F") or "none")
    if bool(flags_a.get("S_MISSING_U")):
        return {
            "tag": TAG_S_MISSING,
            "winning_F": "none",
            "licensed_next_family": FAMILY_OPEN_DECISION,
        }
    if bool(flags_a.get("S_THIN")):
        return {
            "tag": TAG_S_THIN,
            "winning_F": "none",
            "licensed_next_family": FAMILY_OPEN_DECISION,
        }
    tag_a = str(flags_a.get("tag") or TAG_S_NONE)
    if tag_a == TAG_S_MULTI:
        return {"tag": TAG_S_MULTI, "winning_F": "none", "licensed_next_family": FAMILY_OPEN_DECISION}
    if tag_a == TAG_S_SPLIT:
        if win_a != win_b:
            return {
                "tag": TAG_S_AB_DISAGREE,
                "winning_F": "none",
                "licensed_next_family": FAMILY_OPEN_DECISION,
            }
        return {
            "tag": TAG_S_SPLIT,
            "winning_F": win_a,
            "licensed_next_family": f"OPEN_FILTER:{win_a}",
        }
    return {"tag": TAG_S_NONE, "winning_F": "none", "licensed_next_family": FAMILY_H_NONE}


def honesty_paragraph(tag: str, winning_f: str, lift: float | None = None) -> str:
    if tag == TAG_S_SPLIT:
        lift_s = "…" if lift is None else f"{lift}"
        return (
            f"NEUTRAL-open splits on {winning_f} (lift={lift_s}). Filter is **not** shipped. "
            "Next human ticket may implement only this F as evaluate-only refuse-open. "
            "Exam still grades NEUTRAL."
        )
    if tag == TAG_S_MULTI:
        return "Two+ open features split. Do not pick. No law."
    if tag == TAG_S_NONE:
        return (
            "NEUTRAL-open hole and NEUTRAL-open winners are not separable with the locked "
            "candidate set. Blanket refuse remains forbidden."
        )
    return "No train law licensed."


__all__ = [
    "CANDIDATE_NAMES",
    "FAMILY_H_NONE",
    "FAMILY_OPEN_DECISION",
    "F_AFTER_STOP",
    "F_IMBAL_FLAT",
    "F_OCC_FLOOR",
    "F_SESSION_EARLY",
    "F_TIGHT_RANGE",
    "TAG_S_AB_DISAGREE",
    "TAG_S_MISSING",
    "TAG_S_MULTI",
    "TAG_S_NONE",
    "TAG_S_SPLIT",
    "TAG_S_THIN",
    "candidate_grid_row",
    "compute_open_split_flags",
    "flag_s_harm",
    "flag_s_missing_u",
    "flag_s_split",
    "flag_s_thin",
    "hole_from_u",
    "honesty_paragraph",
    "license_from_ab",
    "missing_entry_share_policy",
    "pred_after_stop",
    "pred_imbal_flat",
    "pred_occ_floor",
    "pred_session_early",
    "pred_tight_range",
    "universe_rows",
    "winners_from_u",
]
