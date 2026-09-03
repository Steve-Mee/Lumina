"""Awakening E_EDGE Gate 0: policy-only reason × regime autopsy + trigger flags.

Measurement helper. Does not train, does not move Birth floors, does not drop
NEUTRAL, does not cap FORCE_OPEN. SYNTHETIC ≡ LIVE: same splitter, same inequalities.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any

from lumina_core.birth.awakening_edge_path import inspect_grind_geometry_path
from lumina_core.birth.awakening_mech import (
    load_close_jsonl,
    row_is_force_open,
    row_is_plant,
    split_close_rows,
)

GATE1_NONE = "NONE"
GATE1_WIRE_BIRTH_FILL = "WIRE_BIRTH_FILL"
GATE1_RELABEL_CLOSE_REASON = "RELABEL_CLOSE_REASON"
GATE1_ALIGN_CLIP_GAP = "ALIGN_CLIP_GAP"
EDGE_WIRED = "EDGE_WIRED"
EDGE_RELABEL = "EDGE_RELABEL"
EDGE_MEASURE_ONLY = "EDGE_MEASURE_ONLY"

TREND_LABELS = frozenset({"TREND_UP", "TREND_DOWN"})
PHYSICAL_MISMATCH = frozenset({"stop", "time_stop"})


def _f(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    raw = row.get(key)
    try:
        return float(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default


def policy_only_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """PR #18 identity: policy = not plant and not force_open (plant ≡ force_open on closes)."""
    return list(split_close_rows(rows)["policy"])


def bucket_stats(rows: list[dict[str, Any]]) -> dict[str, float]:
    n = len(rows)
    empty = {
        "n": 0.0,
        "wr": 0.0,
        "sum_usd": 0.0,
        "mean_usd": 0.0,
        "mean_r": 0.0,
        "median_r": 0.0,
        "cap_hit": 0.0,
    }
    if n == 0:
        return empty
    pnls = [_f(r, "pnl") for r in rows]
    rs = [_f(r, "trade_r") for r in rows if r.get("trade_r") is not None]
    wins = sum(1 for p in pnls if p > 0.0)
    return {
        "n": float(n),
        "wr": float(wins) / float(n),
        "sum_usd": float(sum(pnls)),
        "mean_usd": float(sum(pnls) / float(n)),
        "mean_r": (float(sum(rs) / float(len(rs))) if rs else 0.0),
        "median_r": (float(median(rs)) if rs else 0.0),
        "cap_hit": float(sum(1 for r in rows if bool(r.get("cap_hit")))),
    }


def _group(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        label = str(row.get(key) or "UNKNOWN")
        out.setdefault(label, []).append(row)
    return out


def table_by_close_reason(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    return {k: bucket_stats(v) for k, v in sorted(_group(rows, "close_reason").items())}


def loss_share_by_regime(rows: list[dict[str, Any]]) -> dict[str, float]:
    total_loss = sum(min(0.0, _f(r, "pnl")) for r in rows)
    out: dict[str, float] = {}
    for label, bucket in sorted(_group(rows, "regime").items()):
        share = 0.0
        if total_loss < 0.0:
            share = abs(sum(min(0.0, _f(r, "pnl")) for r in bucket)) / abs(total_loss)
        out[label] = float(share)
    return out


def table_by_regime(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    shares = loss_share_by_regime(rows)
    out: dict[str, dict[str, float]] = {}
    for label, bucket in sorted(_group(rows, "regime").items()):
        stats = bucket_stats(bucket)
        stats["loss_share"] = float(shares.get(label, 0.0))
        out[label] = stats
    return out


def reason_regime_cells(
    rows: list[dict[str, Any]],
    *,
    min_n: int = 8,
) -> dict[str, Any]:
    cells: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = f"{row.get('close_reason') or 'UNKNOWN'}|{row.get('regime') or 'UNKNOWN'}"
        cells.setdefault(key, []).append(row)
    trigger = {k: bucket_stats(v) for k, v in sorted(cells.items()) if len(v) >= int(min_n)}
    small = {k: float(len(v)) for k, v in sorted(cells.items()) if len(v) < int(min_n)}
    return {"min_n": float(min_n), "trigger": trigger, "small": small}


def target_gap_split(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    targets = [r for r in rows if str(r.get("close_reason") or "") == "target"]
    clean = [r for r in targets if not bool(r.get("gap"))]
    gapped = [r for r in targets if bool(r.get("gap"))]
    return {"target_no_gap": bucket_stats(clean), "target_gap": bucket_stats(gapped)}


def realized_vs_design(
    rows: list[dict[str, Any]],
    *,
    design_net_rr: float | None = None,
    design_stop_r: float = -1.0,
) -> dict[str, float]:
    targets = [r for r in rows if str(r.get("close_reason") or "") == "target"]
    stops = [r for r in rows if str(r.get("close_reason") or "") == "stop"]
    t_stats = bucket_stats(targets)
    s_stats = bucket_stats(stops)
    return {
        "mean_r_target": float(t_stats["mean_r"]),
        "mean_r_stop": float(s_stats["mean_r"]),
        "n_target": float(t_stats["n"]),
        "n_stop": float(s_stats["n"]),
        "design_net_rr": float(design_net_rr) if design_net_rr is not None else 0.0,
        "design_stop_r": float(design_stop_r),
        "design_net_rr_known": 1.0 if design_net_rr is not None else 0.0,
    }


def _loser_abs(rows: list[dict[str, Any]]) -> float:
    return abs(sum(min(0.0, _f(r, "pnl")) for r in rows))


def compute_g_miswire(dump: dict[str, Any] | None = None) -> bool:
    live = dump if dump is not None else inspect_grind_geometry_path()
    if "G_MISWIRE" in live:
        return bool(live["G_MISWIRE"])
    return True


def compute_g_mislabel(
    policy: list[dict[str, Any]],
    *,
    physical_reasons: list[str] | None = None,
) -> bool:
    """True iff ≥20% of policy targets have trade_r≤0 AND mean_r(target)≤0 AND fill is stop/time_stop."""
    targets = [r for r in policy if str(r.get("close_reason") or "") == "target"]
    n = len(targets)
    if n == 0:
        return False
    rs = [_f(r, "trade_r") for r in targets]
    frac_nonpos = float(sum(1 for x in rs if x <= 0.0)) / float(n)
    mean_r = float(sum(rs) / float(n))
    if frac_nonpos < 0.20 - 1e-12 or mean_r > 0.0:
        return False
    if not physical_reasons:
        return False
    phys = list(physical_reasons)
    mismatched = 0
    nonpos_n = 0
    for i, row in enumerate(targets):
        if _f(row, "trade_r") > 0.0:
            continue
        nonpos_n += 1
        tag = str(phys[i] if i < len(phys) else "")
        if tag in PHYSICAL_MISMATCH:
            mismatched += 1
    return bool(nonpos_n > 0 and mismatched == nonpos_n)


def compute_t_time(policy: list[dict[str, Any]]) -> bool:
    timed = [r for r in policy if str(r.get("close_reason") or "") == "time_stop"]
    if len(timed) < 10:
        return False
    mean_r = float(bucket_stats(timed)["mean_r"])
    if mean_r > -0.30 + 1e-12:
        return False
    all_loss = _loser_abs(policy)
    timed_loss = _loser_abs(timed)
    if all_loss <= 0.0:
        return False
    return (timed_loss / all_loss) >= 0.30 - 1e-12


def compute_t_target(policy: list[dict[str, Any]]) -> bool:
    targets = [r for r in policy if str(r.get("close_reason") or "") == "target"]
    if len(targets) < 15:
        return False
    return float(bucket_stats(targets)["mean_r"]) <= 0.0 + 1e-12


def compute_t_neutral(policy: list[dict[str, Any]]) -> bool:
    shares = loss_share_by_regime(policy)
    neu_share = float(shares.get("NEUTRAL", 0.0))
    if neu_share < 0.70 - 1e-12:
        return False
    trends = [r for r in policy if str(r.get("regime") or "") in TREND_LABELS]
    neu = [r for r in policy if str(r.get("regime") or "") == "NEUTRAL"]
    if len(trends) < 25:
        return False
    if float(bucket_stats(trends)["mean_r"]) < -0.05 - 1e-12:
        return False
    return float(bucket_stats(neu)["mean_r"]) <= -0.25 + 1e-12


def compute_t_stop_only(policy: list[dict[str, Any]], *, t_time: bool) -> bool:
    if bool(t_time):
        return False
    targets = [r for r in policy if str(r.get("close_reason") or "") == "target"]
    if float(bucket_stats(targets)["mean_r"]) <= 0.0 + 1e-12:
        return False
    stops = [r for r in policy if str(r.get("close_reason") or "") == "stop"]
    all_loss = _loser_abs(policy)
    if all_loss <= 0.0:
        return False
    return (_loser_abs(stops) / all_loss) >= 0.70 - 1e-12


def select_gate1_law(
    *,
    g_miswire: bool,
    g_mislabel: bool,
    t_target: bool,
    clip_gap_shared: bool,
) -> str:
    """First match. Stop. T_TIME / T_NEUTRAL / T_STOP_ONLY / none → no law."""
    if bool(g_miswire):
        return GATE1_WIRE_BIRTH_FILL
    if bool(g_mislabel):
        return GATE1_RELABEL_CLOSE_REASON
    if bool(t_target) and not bool(g_mislabel):
        if not bool(clip_gap_shared):
            return GATE1_ALIGN_CLIP_GAP
        return GATE1_NONE
    return GATE1_NONE


def edge_tag_for_law(law: str) -> str:
    if law == GATE1_WIRE_BIRTH_FILL:
        return EDGE_WIRED
    if law == GATE1_RELABEL_CLOSE_REASON:
        return EDGE_RELABEL
    return EDGE_MEASURE_ONLY


@dataclass(slots=True)
class EdgeFlags:
    G_MISWIRE: bool
    G_MISLABEL: bool
    T_TIME: bool
    T_TARGET: bool
    T_NEUTRAL: bool
    T_STOP_ONLY: bool
    n_policy: int
    policy_mean_r: float
    policy_mean_usd: float


def evaluate_policy_book(
    rows: list[dict[str, Any]],
    *,
    g_miswire: bool | None = None,
    physical_reasons: list[str] | None = None,
    design_net_rr: float | None = None,
    clip_gap_shared: bool | None = None,
) -> dict[str, Any]:
    dump = inspect_grind_geometry_path()
    policy = policy_only_rows(rows)
    w_flag = bool(dump["G_MISWIRE"]) if g_miswire is None else bool(g_miswire)
    t_time = compute_t_time(policy)
    t_target = compute_t_target(policy)
    t_neutral = compute_t_neutral(policy)
    t_stop = compute_t_stop_only(policy, t_time=t_time)
    g_label = compute_g_mislabel(policy, physical_reasons=physical_reasons)
    shared = bool(dump["clip_gap_shared"]) if clip_gap_shared is None else bool(clip_gap_shared)
    law = select_gate1_law(
        g_miswire=w_flag,
        g_mislabel=g_label,
        t_target=t_target,
        clip_gap_shared=shared,
    )
    pol_stats = bucket_stats(policy)
    flags = EdgeFlags(
        G_MISWIRE=w_flag,
        G_MISLABEL=g_label,
        T_TIME=t_time,
        T_TARGET=t_target,
        T_NEUTRAL=t_neutral,
        T_STOP_ONLY=t_stop,
        n_policy=int(pol_stats["n"]),
        policy_mean_r=float(pol_stats["mean_r"]),
        policy_mean_usd=float(pol_stats["mean_usd"]),
    )
    return {
        "n_all": len(rows),
        "n_policy": len(policy),
        "n_plant": sum(1 for r in rows if row_is_plant(r)),
        "n_force_open": sum(1 for r in rows if row_is_force_open(r)),
        "policy": pol_stats,
        "by_close_reason": table_by_close_reason(policy),
        "by_regime": table_by_regime(policy),
        "reason_regime": reason_regime_cells(policy),
        "target_gap": target_gap_split(policy),
        "realized_vs_design": realized_vs_design(policy, design_net_rr=design_net_rr),
        "occupancy_series": {"missing": True, "n_bars": 0},
        "flags": flags,
        "gate1": law,
        "edge_tag": edge_tag_for_law(law),
        "live_path": dump,
        "clip_gap_shared": shared,
    }


__all__ = [
    "EDGE_MEASURE_ONLY",
    "EDGE_RELABEL",
    "EDGE_WIRED",
    "EdgeFlags",
    "GATE1_ALIGN_CLIP_GAP",
    "GATE1_NONE",
    "GATE1_RELABEL_CLOSE_REASON",
    "GATE1_WIRE_BIRTH_FILL",
    "bucket_stats",
    "compute_g_mislabel",
    "compute_g_miswire",
    "compute_t_neutral",
    "compute_t_stop_only",
    "compute_t_target",
    "compute_t_time",
    "edge_tag_for_law",
    "evaluate_policy_book",
    "inspect_grind_geometry_path",
    "load_close_jsonl",
    "loss_share_by_regime",
    "policy_only_rows",
    "reason_regime_cells",
    "realized_vs_design",
    "select_gate1_law",
    "table_by_close_reason",
    "table_by_regime",
    "target_gap_split",
]
