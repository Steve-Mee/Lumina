"""Gate 2 HOLD_COMPARE: why genesis MARK_EYES is thin. Measure only. No learn.

G5 ledgers are read-only. Floor POLICY_EDGE_MIN_TRADES=150 stays. GENESIS_EYES_OK
is forbidden. Cause tags are pinned before looking at numbers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_edge import policy_only_rows
from lumina_core.birth.awakening_mech import bucket_stats, load_close_jsonl
from lumina_core.birth.awakening_open_split_flags import hole_from_u, universe_rows
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.birth.genesis_cloud_const import GENESIS_ART, GENESIS_ROOT

# G5 ledger paths listed as read-only — do not overwrite genesis_*_close_ledger.jsonl
G5_BIRTH_A = GENESIS_ART / "genesis_birth_A_close_ledger.jsonl"
G5_BIRTH_B = GENESIS_ART / "genesis_birth_B_close_ledger.jsonl"
G5_EYES_A = GENESIS_ART / "genesis_mark_eyes_A_close_ledger.jsonl"
G5_EYES_B = GENESIS_ART / "genesis_mark_eyes_B_close_ledger.jsonl"
G5_FLAGS = GENESIS_ART / "genesis_cloud_flags.json"
G5_VERDICT = GENESIS_ROOT / "GENESIS_CLOUD_VERDICT.md"

HOLD_DELTA = 5.0
HOLDOUT_TICKS_A = 21585
HOLDOUT_TICKS_B = 21585
EVAL_BUDGET_REASONS = frozenset(
    {
        "truncated",
        "time_stop",
        "in-trade-at-end",
        "in_trade_at_end",
        "end_of_data",
        "eval_truncated",
    }
)
TAG_HOLD_LONGER = "HOLD_LONGER"
TAG_REFUSAL = "REFUSAL"
TAG_EVAL_BUDGET = "EVAL_BUDGET"
TAG_MIXED = "MIXED"
TAG_S_MISSING = "S_MISSING"
CAUSE_TAGS = frozenset({TAG_HOLD_LONGER, TAG_REFUSAL, TAG_EVAL_BUDGET, TAG_MIXED})


class GenesisHoldCompareError(ValueError):
    """Protocol crime: GENESIS_EYES_OK or floor move."""


def refuse_genesis_eyes_ok(flags: dict[str, Any]) -> dict[str, Any]:
    if bool(flags.get("GENESIS_EYES_OK")):
        raise GenesisHoldCompareError("GENESIS_EYES_OK is forbidden; floor 150 is not met")
    flags["GENESIS_EYES_OK"] = False
    flags["HOLE_MOVED_A"] = False
    flags["HOLE_MOVED_B"] = False
    return flags


def _f(row: dict[str, Any], key: str) -> float | None:
    if key not in row or row.get(key) is None:
        return None
    try:
        return float(row.get(key))
    except (TypeError, ValueError):
        return None


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * (float(p) / 100.0)
    lo = int(rank)
    hi = min(lo + 1, len(ordered) - 1)
    if lo == hi:
        return float(ordered[lo])
    frac = rank - lo
    return float(ordered[lo] + (ordered[hi] - ordered[lo]) * frac)


def bars_held_values(rows: list[dict[str, Any]]) -> list[float] | None:
    values: list[float] = []
    missing = False
    for row in rows:
        val = _f(row, "bars_held")
        if val is None:
            missing = True
            continue
        values.append(val)
    if missing and not values:
        return None
    if not values:
        return None
    return values


def policy_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    policy = policy_only_rows(rows)
    universe = universe_rows(policy)
    hole = hole_from_u(universe)
    pol = bucket_stats(policy)
    held = bars_held_values(policy)
    return {
        "n_policy": int(len(policy)),
        "n_entries": int(len(rows)),
        "mean_r": float(pol["mean_r"]),
        "n_H": int(len(hole)),
        "bars_held_p50": percentile(held, 50.0) if held else None,
        "bars_held_p90": percentile(held, 90.0) if held else None,
        "bars_held_present": held is not None,
    }


def trades_per_10k(n_policy: int, holdout_ticks: int) -> float:
    if int(holdout_ticks) <= 0:
        return 0.0
    return float(n_policy) * 10000.0 / float(holdout_ticks)


def _eval_budget_hit(last_row: dict[str, Any] | None, n_policy_child: int) -> bool:
    if not last_row or int(n_policy_child) >= int(POLICY_EDGE_MIN_TRADES):
        return False
    reason = str(last_row.get("close_reason") or "").strip().lower().replace(" ", "_")
    if reason in EVAL_BUDGET_REASONS:
        return True
    if "truncated" in reason or "in-trade" in reason or "in_trade" in reason:
        return True
    return False


def classify_cause(
    *,
    birth: dict[str, Any],
    child: dict[str, Any],
    child_last_row: dict[str, Any] | None,
) -> str:
    if not birth.get("bars_held_present") or not child.get("bars_held_present"):
        return TAG_S_MISSING
    b_p50 = birth.get("bars_held_p50")
    c_p50 = child.get("bars_held_p50")
    if b_p50 is None or c_p50 is None:
        return TAG_S_MISSING
    n_b = int(birth.get("n_policy") or 0)
    n_c = int(child.get("n_policy") or 0)
    fired: list[str] = []
    if float(c_p50) >= float(b_p50) + HOLD_DELTA and n_c < n_b:
        fired.append(TAG_HOLD_LONGER)
    if abs(float(c_p50) - float(b_p50)) < HOLD_DELTA and n_c < n_b:
        fired.append(TAG_REFUSAL)
    if _eval_budget_hit(child_last_row, n_c):
        fired.append(TAG_EVAL_BUDGET)
    if not fired:
        return TAG_MIXED
    if len(fired) == 1:
        return fired[0]
    if set(fired) == {TAG_EVAL_BUDGET, TAG_HOLD_LONGER}:
        return TAG_HOLD_LONGER
    return TAG_MIXED


def combine_leg_tags(tag_a: str, tag_b: str) -> str:
    if tag_a == TAG_S_MISSING or tag_b == TAG_S_MISSING:
        return TAG_S_MISSING
    if tag_a == tag_b:
        return tag_a
    return TAG_MIXED


def licensed_next_family(gate2_tag: str, *, gate1_ok: bool) -> str:
    if not gate1_ok:
        return "H_NONE"
    if gate2_tag in {TAG_HOLD_LONGER, TAG_EVAL_BUDGET}:
        return "GENESIS_EYES_BUDGET"
    return "H_NONE"


def load_leg(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any] | None]:
    rows = load_close_jsonl(path) if path.is_file() else []
    stats = policy_stats(rows)
    last = rows[-1] if rows else None
    return rows, stats, last


def compare_leg(
    *,
    birth_path: Path,
    child_path: Path,
    holdout_ticks: int,
    expected_n_policy_child: int | None = None,
) -> dict[str, Any]:
    _birth_rows, birth, _ = load_leg(birth_path)
    child_rows, child, last = load_leg(child_path)
    if expected_n_policy_child is not None:
        child["n_policy_restated"] = int(expected_n_policy_child)
    cause = classify_cause(birth=birth, child=child, child_last_row=last)
    return {
        "birth": birth,
        "child": child,
        "cause": cause,
        "trades_per_10k_birth": trades_per_10k(int(birth["n_policy"]), holdout_ticks),
        "trades_per_10k_child": trades_per_10k(int(child["n_policy"]), holdout_ticks),
        "holdout_ticks": int(holdout_ticks),
        "child_last_close_reason": str((last or {}).get("close_reason") or ""),
        "g5_ledgers_read_only": True,
        "learn_called": False,
        "n_child_rows": len(child_rows),
    }


def g5_inputs_present() -> bool:
    return all(p.is_file() for p in (G5_BIRTH_A, G5_BIRTH_B, G5_EYES_A, G5_EYES_B, G5_FLAGS))


__all__ = [
    "CAUSE_TAGS",
    "G5_BIRTH_A",
    "G5_BIRTH_B",
    "G5_EYES_A",
    "G5_EYES_B",
    "G5_FLAGS",
    "G5_VERDICT",
    "GenesisHoldCompareError",
    "HOLDOUT_TICKS_A",
    "HOLDOUT_TICKS_B",
    "POLICY_EDGE_MIN_TRADES",
    "TAG_EVAL_BUDGET",
    "TAG_HOLD_LONGER",
    "TAG_MIXED",
    "TAG_REFUSAL",
    "TAG_S_MISSING",
    "classify_cause",
    "combine_leg_tags",
    "compare_leg",
    "g5_inputs_present",
    "licensed_next_family",
    "policy_stats",
    "refuse_genesis_eyes_ok",
    "trades_per_10k",
]
