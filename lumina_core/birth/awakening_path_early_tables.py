"""PATH_EARLY tables T0–T5. Measure-only. No fill change."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_edge import policy_only_rows
from lumina_core.birth.awakening_entry_autopsy_tables import read_existing_hole_contrast
from lumina_core.birth.awakening_mech import bucket_stats, split_close_rows
from lumina_core.birth.awakening_open_split_flags import (
    flag_s_missing_u,
    hole_from_u,
    missing_entry_share_policy,
    universe_rows,
    winners_from_u,
)
from lumina_core.birth.awakening_path_early_flags import (
    K_LOCKED,
    PATH_CANDIDATE_NAMES,
    PATH_CANDIDATE_K,
    compute_path_early_flags,
    flag_s_missing_path,
    path_candidate_grid_row,
)
from lumina_core.birth.awakening_path_early_path import compute_k_medians, universe_k
from lumina_core.birth.awakening_select import reports_dir

CONTRAST_BOOKS = (
    ("grind_A", "grind_A_close_ledger.jsonl"),
    ("grind_B", "grind_B_close_ledger.jsonl"),
    ("select_A", "select_A_close_ledger.jsonl"),
    ("select_B", "select_B_close_ledger.jsonl"),
    ("hole_tax_A", "hole_tax_A_close_ledger.jsonl"),
    ("hole_tax_B", "hole_tax_B_close_ledger.jsonl"),
    ("entry_autopsy_A", "entry_autopsy_A_close_ledger.jsonl"),
    ("entry_autopsy_B", "entry_autopsy_B_close_ledger.jsonl"),
    ("open_split_A", "open_split_A_close_ledger.jsonl"),
    ("open_split_B", "open_split_B_close_ledger.jsonl"),
    ("policy_signal_A", "policy_signal_A_close_ledger.jsonl"),
    ("policy_signal_B", "policy_signal_B_close_ledger.jsonl"),
)

T1B_KEYS = (
    "path_k3_mae_r",
    "path_k3_mfe_r",
    "path_k3_unreal_r",
    "path_k5_mae_r",
    "path_k5_mfe_r",
    "path_k5_unreal_r",
)


def _bucket_cell(rows: list[dict[str, Any]]) -> dict[str, Any]:
    stats = bucket_stats(rows)
    return {
        "n": int(stats["n"]),
        "wr": float(stats["wr"]),
        "mean_r": float(stats["mean_r"]),
        "mean_usd": float(stats["mean_usd"]),
    }


def table_t0(
    rows: list[dict[str, Any]],
    *,
    zip_sha256: str,
    ticks_sha16: str,
    price_sha16_value: str,
    optimizer_steps: int,
    skip_replay: bool = False,
) -> dict[str, Any]:
    parts = split_close_rows(rows)
    all_stats = bucket_stats(parts["all"])
    pol_stats = bucket_stats(parts["policy"])
    return {
        "n_all": int(all_stats["n"]),
        "n_policy": int(len(parts["policy"])),
        "n_plant": int(len(parts["plant"])),
        "wr_policy": float(pol_stats["wr"]),
        "mean_r_policy": float(pol_stats["mean_r"]),
        "zip_sha256": str(zip_sha256),
        "ticks_sha16": str(ticks_sha16),
        "price_sha16": str(price_sha16_value),
        "optimizer_steps": int(optimizer_steps),
        "skip_replay": bool(skip_replay),
    }


def table_t1(rows: list[dict[str, Any]]) -> dict[str, Any]:
    flags = compute_path_early_flags(rows)
    policy = policy_only_rows(rows)
    universe = universe_rows(policy)
    hole = hole_from_u(universe)
    winners = winners_from_u(universe)
    n_u = len(universe)
    n_h = len(hole)
    n_w = len(winners)
    per_k = {str(k): dict(flags["k"][k]) for k in K_LOCKED}
    return {
        "U": _bucket_cell(universe),
        "H": _bucket_cell(hole),
        "W": _bucket_cell(winners),
        "n_U": int(n_u),
        "n_H": int(n_h),
        "n_W": int(n_w),
        "share_H": (float(n_h) / float(n_u)) if n_u > 0 else 0.0,
        "share_W": (float(n_w) / float(n_u)) if n_u > 0 else 0.0,
        "k": per_k,
    }


def _quantiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "median": None, "p25": None, "p75": None}
    s = sorted(values)
    n = len(s)

    def _at(p: float) -> float:
        idx = min(n - 1, max(0, int(round(p * (n - 1)))))
        return float(s[idx])

    mid = n // 2
    median = float(s[mid]) if n % 2 == 1 else (float(s[mid - 1]) + float(s[mid])) / 2.0
    return {
        "mean": float(sum(s) / n),
        "median": median,
        "p25": _at(0.25),
        "p75": _at(0.75),
    }


def _dist_cell(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    defined: list[float] = []
    for row in rows:
        if key in row and row.get(key) is not None:
            try:
                defined.append(float(row.get(key)))
            except (TypeError, ValueError):
                continue
    n = len(rows)
    n_defined = len(defined)
    missing_share = 1.0 if n <= 0 else 1.0 - (float(n_defined) / float(n))
    stats = _quantiles(defined)
    return {"n_defined": int(n_defined), "missing_share": float(missing_share), **stats}


def table_t1b(rows: list[dict[str, Any]]) -> dict[str, Any]:
    policy = policy_only_rows(rows)
    universe = universe_rows(policy)
    out: dict[str, Any] = {}
    for key in T1B_KEYS:
        k = 3 if "k3" in key else 5
        u_k = universe_k(universe, k)
        hole_k = hole_from_u(u_k)
        winners_k = winners_from_u(u_k)
        out[key] = {
            "U_k": _dist_cell(u_k, key),
            "H_k": _dist_cell(hole_k, key),
            "W_k": _dist_cell(winners_k, key),
        }
    return out


def _grid_inputs(rows: list[dict[str, Any]]) -> dict[str, Any]:
    policy = policy_only_rows(rows)
    universe = universe_rows(policy)
    s_missing_u = flag_s_missing_u(
        missing_entry_share=missing_entry_share_policy(policy), n_u=len(universe)
    ) or len(universe) <= 0
    s_missing_path = flag_s_missing_path(universe)
    flags = compute_path_early_flags(rows)
    return {
        "universe": universe,
        "s_missing_u": s_missing_u,
        "s_missing_path": s_missing_path,
        "flags": flags,
    }


def table_t2(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ctx = _grid_inputs(rows)
    flags = ctx["flags"]
    grid: dict[str, Any] = {}
    for name in PATH_CANDIDATE_NAMES:
        row = (flags.get("candidates") or {}).get(name) or {}
        grid[name] = {
            "threshold": row.get("threshold"),
            "n_defined": row.get("n_defined"),
            "missing_share": row.get("missing_share"),
            "cov_H": row.get("cov_H"),
            "cov_W": row.get("cov_W"),
            "lift": row.get("lift"),
            "S_SPLIT": row.get("S_SPLIT"),
            "S_HARM": row.get("S_HARM"),
            "S_THIN": row.get("S_THIN"),
            "missing": row.get("missing"),
        }
    return grid


def table_t3(rows: list[dict[str, Any]]) -> dict[str, Any]:
    flags = compute_path_early_flags(rows)
    out: dict[str, Any] = {}
    for name in PATH_CANDIDATE_NAMES:
        row = (flags.get("candidates") or {}).get(name) or {}
        out[name] = {
            "drop_H": row.get("drop_H"),
            "drop_W": row.get("drop_W"),
            "remaining_H": row.get("remaining_H"),
            "remaining_W": row.get("remaining_W"),
        }
    return out


def table_t5(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Opposite-tail cov/lift. READ_ONLY_FLIP. Cannot win."""
    policy = policy_only_rows(rows)
    universe = universe_rows(policy)
    s_missing_u = flag_s_missing_u(
        missing_entry_share=missing_entry_share_policy(policy), n_u=len(universe)
    ) or len(universe) <= 0
    s_missing_path = flag_s_missing_path(universe)
    flags = compute_path_early_flags(rows)
    out: dict[str, Any] = {}
    for name in PATH_CANDIDATE_NAMES:
        k = PATH_CANDIDATE_K[name]
        sl = (flags.get("k") or {}).get(k) or {}
        u_k = universe_k(universe, k)
        row = path_candidate_grid_row(
            u_k,
            hole_from_u(u_k),
            winners_from_u(u_k),
            name=name,
            s_missing_u=s_missing_u,
            s_missing_path=s_missing_path,
            s_thin_k=bool(sl.get("S_THIN")),
            medians=compute_k_medians(u_k, k),
            flip=True,
        )
        out[name] = {
            "cov_H": row["cov_H"],
            "cov_W": row["cov_W"],
            "lift": row["lift"],
            "READ_ONLY_FLIP": True,
            "S_SPLIT": False,
        }
    return out


def table_t4(artifacts_dir: Path | str | None = None) -> dict[str, Any]:
    base = Path(artifacts_dir) if artifacts_dir is not None else reports_dir() / "artifacts"
    out: dict[str, Any] = {}
    for key, name in CONTRAST_BOOKS:
        out[key] = read_existing_hole_contrast(base / name)
    return out


__all__ = [
    "CONTRAST_BOOKS",
    "table_t0",
    "table_t1",
    "table_t1b",
    "table_t2",
    "table_t3",
    "table_t4",
    "table_t5",
]
