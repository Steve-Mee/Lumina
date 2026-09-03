"""Awakening mechanism Gate 0: policy vs plant vs FORCE_OPEN split + triggers.

Measurement helper. Does not train, does not move Birth floors, does not invent
an idle controller. SYNTHETIC ≡ LIVE: same close-row tags, same inequalities.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_mech_path import inspect_grind_live_path
from lumina_core.birth.s5_process_decomp import target_clean_count

GATE1_NONE = "NONE"
GATE1_WIRE_BIRTH_PARTICIPATION = "WIRE_BIRTH_PARTICIPATION"
GATE1_WIRE_CHATTER_BOUND = "WIRE_CHATTER_BOUND"
MECH_MEASURE_ONLY = "MECH_MEASURE_ONLY"
MECH_WIRED = "MECH_WIRED"

POLICY_MEAN_MATERIAL_USD = 10.0
P_UNION_FRAC_MIN = 0.40
P_DOLLAR_SHARE_MIN = 0.50
P_POLICY_N_MIN = 40
E_POLICY_N_MIN = 80
E_MEAN_R_MAX = -0.15
E_MEAN_USD_MAX = -40.0


def _f(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    raw = row.get(key)
    try:
        return float(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default


def _truthy(row: dict[str, Any], key: str) -> bool:
    return bool(row.get(key))


def row_is_plant(row: dict[str, Any]) -> bool:
    return _truthy(row, "plant") or _truthy(row, "plant_entry")


def row_is_force_open(row: dict[str, Any]) -> bool:
    """Close-row FORCE_OPEN. Missing column falls back to plant (Birth identity)."""
    if "force_open" in row and row.get("force_open") is not None:
        return bool(row.get("force_open"))
    return row_is_plant(row)


def load_close_jsonl(path: Path | str) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        if isinstance(raw, dict):
            rows.append(raw)
    return rows


def bucket_stats(rows: list[dict[str, Any]]) -> dict[str, float]:
    n = len(rows)
    if n == 0:
        return {
            "n": 0.0,
            "wr": 0.0,
            "sum_usd": 0.0,
            "mean_usd": 0.0,
            "mean_r": 0.0,
            "cap_hit": 0.0,
            "stop": 0.0,
            "target": 0.0,
            "time_stop": 0.0,
            "target_clean": 0.0,
        }
    pnls = [_f(r, "pnl") for r in rows]
    rs = [_f(r, "trade_r") for r in rows if r.get("trade_r") is not None]
    wins = sum(1 for p in pnls if p > 0.0)
    return {
        "n": float(n),
        "wr": float(wins) / float(n),
        "sum_usd": float(sum(pnls)),
        "mean_usd": float(sum(pnls) / float(n)),
        "mean_r": (float(sum(rs) / float(len(rs))) if rs else 0.0),
        "cap_hit": float(sum(1 for r in rows if bool(r.get("cap_hit")))),
        "stop": float(sum(1 for r in rows if str(r.get("close_reason") or "") == "stop")),
        "target": float(sum(1 for r in rows if str(r.get("close_reason") or "") == "target")),
        "time_stop": float(sum(1 for r in rows if str(r.get("close_reason") or "") == "time_stop")),
        "target_clean": float(target_clean_count(rows)),
    }


def split_close_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Partition closes. Overlap is a separate list; totals must not double-count."""
    policy: list[dict[str, Any]] = []
    force: list[dict[str, Any]] = []
    plant: list[dict[str, Any]] = []
    overlap: list[dict[str, Any]] = []
    for row in rows:
        is_plant = row_is_plant(row)
        is_force = row_is_force_open(row)
        if is_plant and is_force:
            overlap.append(row)
            plant.append(row)
            force.append(row)
        elif is_force:
            force.append(row)
        elif is_plant:
            plant.append(row)
        else:
            policy.append(row)
    return {
        "policy": policy,
        "force_open": force,
        "plant": plant,
        "overlap": overlap,
        "all": list(rows),
    }


def split_table(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    parts = split_close_rows(rows)
    return {
        "policy": bucket_stats(parts["policy"]),
        "force_open": bucket_stats(parts["force_open"]),
        "plant": bucket_stats(parts["plant"]),
        "overlap": bucket_stats(parts["overlap"]),
        "all": bucket_stats(parts["all"]),
    }


def loss_share_by_regime(rows: list[dict[str, Any]]) -> dict[str, float]:
    total_loss = sum(min(0.0, _f(r, "pnl")) for r in rows)
    labels = sorted({str(r.get("regime") or "UNKNOWN") for r in rows})
    out: dict[str, float] = {}
    for label in labels:
        bucket = [r for r in rows if str(r.get("regime") or "UNKNOWN") == label]
        share = 0.0
        if total_loss < 0.0:
            bucket_loss = sum(min(0.0, _f(r, "pnl")) for r in bucket)
            share = abs(bucket_loss) / abs(total_loss)
        out[label] = float(share)
    return out


def occupancy_band_fractions(bar_occupancy: list[float] | None) -> dict[str, Any]:
    """Fraction of bars in [0.25,0.30], (0.30,0.75], >0.75. Missing series → None."""
    if not bar_occupancy:
        return {
            "n_bars": 0,
            "in_025_030": None,
            "in_030_075": None,
            "gt_075": None,
            "missing": True,
        }
    n = len(bar_occupancy)
    a = sum(1 for x in bar_occupancy if 0.25 - 1e-12 <= float(x) <= 0.30 + 1e-12)
    b = sum(1 for x in bar_occupancy if 0.30 + 1e-12 < float(x) <= 0.75 + 1e-12)
    c = sum(1 for x in bar_occupancy if float(x) > 0.75 + 1e-12)
    return {
        "n_bars": n,
        "in_025_030": float(a) / float(n),
        "in_030_075": float(b) / float(n),
        "gt_075": float(c) / float(n),
        "missing": False,
    }


@dataclass(slots=True)
class TriggerFlags:
    P_PARTICIPATION: bool
    E_EDGE: bool
    W_WIRE: bool
    BOTH_BAD: bool
    n: int
    n_policy: int
    n_force: int
    n_plant: int
    n_overlap: int
    union_frac: float
    dollar_share: float
    policy_mean_usd: float
    overall_mean_usd: float
    policy_mean_r: float
    union_sum_usd: float
    loser_sum_abs: float


def compute_pe_flags(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    parts = split_close_rows(rows)
    policy = parts["policy"]
    n_force = len(parts["force_open"])
    n_plant = len(parts["plant"])
    n_overlap = len(parts["overlap"])
    n_policy = len(policy)
    union_n = n_force + n_plant - n_overlap
    union_frac = (float(union_n) / float(n)) if n else 0.0
    overlap_ids = {id(r) for r in parts["overlap"]}
    union_rows = list(parts["force_open"]) + [r for r in parts["plant"] if id(r) not in overlap_ids]
    union_sum = float(sum(_f(r, "pnl") for r in union_rows))
    losers = [r for r in rows if _f(r, "pnl") < 0.0]
    loser_sum_abs = abs(float(sum(_f(r, "pnl") for r in losers)))
    dollar_share = (abs(union_sum) / loser_sum_abs) if loser_sum_abs > 0.0 else 0.0
    policy_mean = float(sum(_f(r, "pnl") for r in policy) / float(n_policy)) if n_policy else 0.0
    overall_mean = float(sum(_f(r, "pnl") for r in rows) / float(n)) if n else 0.0
    policy_rs = [_f(r, "trade_r") for r in policy if r.get("trade_r") is not None]
    policy_mean_r = float(sum(policy_rs) / float(len(policy_rs))) if policy_rs else 0.0
    p_vol = union_frac >= P_UNION_FRAC_MIN - 1e-12
    p_usd = dollar_share >= P_DOLLAR_SHARE_MIN - 1e-12
    p_better = policy_mean > overall_mean
    p_n = n_policy >= P_POLICY_N_MIN
    p_flag = bool((p_vol or p_usd) and p_better and p_n)
    e_flag = bool(
        n_policy >= E_POLICY_N_MIN and (policy_mean_r <= E_MEAN_R_MAX + 1e-12 or policy_mean <= E_MEAN_USD_MAX + 1e-12)
    )
    return {
        "P_PARTICIPATION": p_flag,
        "E_EDGE": e_flag,
        "n": n,
        "n_policy": n_policy,
        "n_force": n_force,
        "n_plant": n_plant,
        "n_overlap": n_overlap,
        "union_frac": union_frac,
        "dollar_share": dollar_share,
        "policy_mean_usd": policy_mean,
        "overall_mean_usd": overall_mean,
        "policy_mean_r": policy_mean_r,
        "union_sum_usd": union_sum,
        "loser_sum_abs": loser_sum_abs,
        "p_vol": p_vol,
        "p_usd": p_usd,
        "p_better": p_better,
        "p_n": p_n,
    }


def compute_w_wire(
    *,
    envelope_enabled: bool,
    chatter_bound_live: bool,
    refractory_live: bool,
    min_dwell_in_kwargs: bool,
    plant_tag_present: bool,
) -> bool:
    """True when a Birth participation law is dead on the grind runner."""
    return (
        (not bool(envelope_enabled))
        or (not bool(chatter_bound_live))
        or (not bool(refractory_live))
        or (not bool(min_dwell_in_kwargs))
        or (not bool(plant_tag_present))
    )


def compute_both_bad(
    *,
    p_participation: bool,
    e_edge: bool,
    policy_mean_usd: float,
    overall_mean_usd: float,
) -> bool:
    if not (bool(p_participation) and bool(e_edge)):
        return False
    return float(policy_mean_usd) <= float(overall_mean_usd) + POLICY_MEAN_MATERIAL_USD + 1e-12


def select_gate1_law(
    *,
    p_participation: bool,
    e_edge: bool,
    w_wire: bool,
    both_bad: bool,
) -> str:
    """First matching rule. Stop after one. Do not stack."""
    if bool(w_wire):
        return GATE1_WIRE_BIRTH_PARTICIPATION
    if bool(p_participation) and not bool(both_bad) and not bool(e_edge):
        return GATE1_WIRE_CHATTER_BOUND
    return GATE1_NONE


def evaluate_book(
    rows: list[dict[str, Any]],
    *,
    w_wire: bool | None = None,
    bar_occupancy: list[float] | None = None,
) -> dict[str, Any]:
    dump = inspect_grind_live_path()
    w_flag = bool(dump["W_WIRE"]) if w_wire is None else bool(w_wire)
    pe = compute_pe_flags(rows)
    both = compute_both_bad(
        p_participation=bool(pe["P_PARTICIPATION"]),
        e_edge=bool(pe["E_EDGE"]),
        policy_mean_usd=float(pe["policy_mean_usd"]),
        overall_mean_usd=float(pe["overall_mean_usd"]),
    )
    law = select_gate1_law(
        p_participation=bool(pe["P_PARTICIPATION"]),
        e_edge=bool(pe["E_EDGE"]),
        w_wire=w_flag,
        both_bad=both,
    )
    flags = TriggerFlags(
        P_PARTICIPATION=bool(pe["P_PARTICIPATION"]),
        E_EDGE=bool(pe["E_EDGE"]),
        W_WIRE=w_flag,
        BOTH_BAD=both,
        n=int(pe["n"]),
        n_policy=int(pe["n_policy"]),
        n_force=int(pe["n_force"]),
        n_plant=int(pe["n_plant"]),
        n_overlap=int(pe["n_overlap"]),
        union_frac=float(pe["union_frac"]),
        dollar_share=float(pe["dollar_share"]),
        policy_mean_usd=float(pe["policy_mean_usd"]),
        overall_mean_usd=float(pe["overall_mean_usd"]),
        policy_mean_r=float(pe["policy_mean_r"]),
        union_sum_usd=float(pe["union_sum_usd"]),
        loser_sum_abs=float(pe["loser_sum_abs"]),
    )
    return {
        "table": split_table(rows),
        "loss_share_by_regime": loss_share_by_regime(rows),
        "occupancy_bands": occupancy_band_fractions(bar_occupancy),
        "flags": flags,
        "pe": pe,
        "gate1": law,
        "mech_tag": MECH_WIRED if law != GATE1_NONE else MECH_MEASURE_ONLY,
        "live_path": dump,
        "jsonl_columns": sorted({k for r in rows for k in r.keys()}),
    }


__all__ = [
    "GATE1_NONE",
    "GATE1_WIRE_BIRTH_PARTICIPATION",
    "GATE1_WIRE_CHATTER_BOUND",
    "MECH_MEASURE_ONLY",
    "MECH_WIRED",
    "TriggerFlags",
    "bucket_stats",
    "compute_both_bad",
    "compute_pe_flags",
    "compute_w_wire",
    "evaluate_book",
    "inspect_grind_live_path",
    "load_close_jsonl",
    "loss_share_by_regime",
    "occupancy_band_fractions",
    "row_is_force_open",
    "row_is_plant",
    "select_gate1_law",
    "split_close_rows",
    "split_table",
]
