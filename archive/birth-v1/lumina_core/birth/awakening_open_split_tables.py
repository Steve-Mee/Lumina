"""OPEN_SPLIT tables T0–T4. Measure-only. No fill change."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_edge import policy_only_rows
from lumina_core.birth.awakening_entry_autopsy_tables import read_existing_hole_contrast
from lumina_core.birth.awakening_mech import bucket_stats, split_close_rows
from lumina_core.birth.awakening_open_split import (
    CANDIDATE_NAMES,
    candidate_grid_row,
    compute_open_split_flags,
    flag_s_missing_u,
    flag_s_thin,
    hole_from_u,
    missing_entry_share_policy,
    universe_rows,
    winners_from_u,
)
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
    }


def table_t1(rows: list[dict[str, Any]]) -> dict[str, Any]:
    policy = policy_only_rows(rows)
    universe = universe_rows(policy)
    hole = hole_from_u(universe)
    winners = winners_from_u(universe)
    n_u = len(universe)
    n_h = len(hole)
    n_w = len(winners)
    return {
        "U": _bucket_cell(universe),
        "H": _bucket_cell(hole),
        "W": _bucket_cell(winners),
        "n_U": int(n_u),
        "n_H": int(n_h),
        "n_W": int(n_w),
        "share_H": (float(n_h) / float(n_u)) if n_u > 0 else 0.0,
        "share_W": (float(n_w) / float(n_u)) if n_u > 0 else 0.0,
    }


def table_t2(rows: list[dict[str, Any]]) -> dict[str, Any]:
    policy = policy_only_rows(rows)
    universe = universe_rows(policy)
    hole = hole_from_u(universe)
    winners = winners_from_u(universe)
    s_missing_u = flag_s_missing_u(missing_entry_share=missing_entry_share_policy(policy), n_u=len(universe))
    s_thin = flag_s_thin(n_h=len(hole), n_w=len(winners))
    grid: dict[str, Any] = {}
    for name in CANDIDATE_NAMES:
        row = candidate_grid_row(universe, hole, winners, name=name, s_missing_u=s_missing_u, s_thin=s_thin)
        grid[name] = {
            "n_defined": row["n_defined"],
            "missing_share": row["missing_share"],
            "cov_H": row["cov_H"],
            "cov_W": row["cov_W"],
            "lift": row["lift"],
            "S_SPLIT": row["S_SPLIT"],
            "S_HARM": row["S_HARM"],
            "missing": row["missing"],
        }
    return grid


def table_t3(rows: list[dict[str, Any]]) -> dict[str, Any]:
    policy = policy_only_rows(rows)
    universe = universe_rows(policy)
    hole = hole_from_u(universe)
    winners = winners_from_u(universe)
    s_missing_u = flag_s_missing_u(missing_entry_share=missing_entry_share_policy(policy), n_u=len(universe))
    s_thin = flag_s_thin(n_h=len(hole), n_w=len(winners))
    out: dict[str, Any] = {}
    for name in CANDIDATE_NAMES:
        row = candidate_grid_row(universe, hole, winners, name=name, s_missing_u=s_missing_u, s_thin=s_thin)
        out[name] = {
            "drop_H": row["drop_H"],
            "drop_W": row["drop_W"],
            "remaining_H": row["remaining_H"],
            "remaining_W": row["remaining_W"],
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
    "compute_open_split_flags",
    "read_existing_hole_contrast",
    "table_t0",
    "table_t1",
    "table_t2",
    "table_t3",
    "table_t4",
]
