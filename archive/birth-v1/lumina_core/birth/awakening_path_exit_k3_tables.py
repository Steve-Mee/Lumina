"""PATH_EXIT K3 tables T0–T5. Shadow flatten. No fill formula change."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_edge import policy_only_rows
from lumina_core.birth.awakening_entry_autopsy_tables import read_existing_hole_contrast
from lumina_core.birth.awakening_mech import bucket_stats, split_close_rows
from lumina_core.birth.awakening_open_split_flags import hole_from_u, universe_rows, winners_from_u
from lumina_core.birth.awakening_path_exit_k3 import (
    PAPER_DROP_H_A,
    PAPER_DROP_W_A,
    PAPER_N_EXIT_SCALE_A,
    SOURCE,
)
from lumina_core.birth.awakening_path_exit_k3_flags import (
    baseline_from_rows,
    compute_path_exit_k3_flags,
    empty_baseline,
    path_exit_k3_rows,
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
    ("open_split_A", "open_split_A_close_ledger.jsonl"),
    ("open_split_B", "open_split_B_close_ledger.jsonl"),
    ("policy_signal_A", "policy_signal_A_close_ledger.jsonl"),
    ("policy_signal_B", "policy_signal_B_close_ledger.jsonl"),
    ("path_early_A", "path_early_A_close_ledger.jsonl"),
    ("path_early_B", "path_early_B_close_ledger.jsonl"),
    ("path_unreal_k3_A", "path_unreal_k3_A_close_ledger.jsonl"),
    ("path_unreal_k3_B", "path_unreal_k3_B_close_ledger.jsonl"),
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
    hook_enabled: bool,
    skip_replay: bool = False,
    replay_ran: bool = False,
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
        "hook_enabled": bool(hook_enabled),
        "n_exit": int(len(path_exit_k3_rows(parts["policy"]))),
        "skip_replay": bool(skip_replay),
        "replay_ran": bool(replay_ran),
        "source": SOURCE,
    }


def table_t1(rows: list[dict[str, Any]]) -> dict[str, Any]:
    policy = policy_only_rows(rows)
    universe = universe_rows(policy)
    hole = hole_from_u(universe)
    winners = winners_from_u(universe)
    exits = path_exit_k3_rows(policy)
    return {
        "U": _bucket_cell(universe),
        "H": _bucket_cell(hole),
        "W": _bucket_cell(winners),
        "n_U": int(len(universe)),
        "n_H": int(len(hole)),
        "n_W": int(len(winners)),
        "n_exit": int(len(exits)),
        "mean_r_exit": float(bucket_stats(exits)["mean_r"]),
        "wr_exit": float(bucket_stats(exits)["wr"]),
    }


def table_t2(
    rows: list[dict[str, Any]],
    *,
    baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    flags = compute_path_exit_k3_flags(rows, baseline=baseline)
    base = flags.get("baseline") or empty_baseline()
    return {
        "n_H_base": int(base.get("n_H") or 0),
        "n_H_shadow": int(flags.get("n_H") or 0),
        "delta_n_H": int(flags.get("n_H") or 0) - int(base.get("n_H") or 0),
        "mean_r_H_base": float(base.get("mean_r_H") or 0.0),
        "mean_r_H_shadow": float(flags.get("mean_r_H") or 0.0),
        "n_W_base": int(base.get("n_W") or 0),
        "n_W_shadow": int(flags.get("n_W") or 0),
        "delta_n_W": int(flags.get("n_W") or 0) - int(base.get("n_W") or 0),
        "wr_policy_base": float(base.get("wr_policy") or 0.0),
        "wr_policy_shadow": float(flags.get("wr_policy") or 0.0),
        "mean_r_policy_base": float(base.get("mean_r_policy") or 0.0),
        "mean_r_policy_shadow": float(flags.get("mean_r_policy") or 0.0),
        "delta_mean_r_policy": float(flags.get("mean_r_policy") or 0.0)
        - float(base.get("mean_r_policy") or 0.0),
    }


def table_t3(*, n_exit: int, paper_drop_h: int = PAPER_DROP_H_A, paper_drop_w: int = PAPER_DROP_W_A) -> dict[str, Any]:
    paper = int(paper_drop_h) + int(paper_drop_w)
    live = int(n_exit)
    scale_fail = live == 0 or (paper > 0 and live > 2 * paper)
    return {
        "paper_drop_H": int(paper_drop_h),
        "paper_drop_W": int(paper_drop_w),
        "paper_n_exit_scale": int(PAPER_N_EXIT_SCALE_A if paper == PAPER_N_EXIT_SCALE_A else paper),
        "n_exit_live": live,
        "scale_fail": bool(scale_fail),
        "why": (
            "n_exit 0 or >2× paper 55 — dump threshold units / missing unreal / hook not wired"
            if scale_fail
            else "n_exit within 2× paper counterfactual scale"
        ),
    }


def table_t4(artifacts_dir: Path | str | None = None) -> dict[str, Any]:
    base = Path(artifacts_dir) if artifacts_dir is not None else reports_dir() / "artifacts"
    out: dict[str, Any] = {}
    for key, name in CONTRAST_BOOKS:
        out[key] = read_existing_hole_contrast(base / name)
    return out


def _join_key(row: dict[str, Any]) -> tuple[int, int] | None:
    if "entry_bar_index" not in row:
        return None
    side = row.get("open_side", row.get("side"))
    if side is None:
        return None
    try:
        return int(row.get("entry_bar_index")), int(side)
    except (TypeError, ValueError):
        return None


def table_t5(
    shadow_rows: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Share of exits that would have been H vs W if scored with baseline close_reason."""
    if not baseline_rows:
        return {"join_absent": True, "n_exit": 0, "would_H": 0, "would_W": 0}
    index: dict[tuple[int, int], dict[str, Any]] = {}
    for row in baseline_rows:
        key = _join_key(row)
        if key is not None:
            index[key] = row
    if not index:
        return {"join_absent": True, "n_exit": 0, "would_H": 0, "would_W": 0}
    exits = path_exit_k3_rows(policy_only_rows(shadow_rows))
    would_h = 0
    would_w = 0
    joined = 0
    for row in exits:
        key = _join_key(row)
        if key is None or key not in index:
            continue
        joined += 1
        base = index[key]
        reason = str(base.get("close_reason") or "")
        regime = str(base.get("regime") or "").upper()
        if reason == "stop" and regime == "NEUTRAL":
            would_h += 1
        elif reason == "target":
            would_w += 1
        elif reason == "time_stop":
            try:
                if float(base.get("trade_r")) > 0.0:
                    would_w += 1
            except (TypeError, ValueError):
                pass
    return {
        "join_absent": False,
        "n_exit": int(len(exits)),
        "n_joined": int(joined),
        "would_H": int(would_h),
        "would_W": int(would_w),
        "share_would_H": (float(would_h) / float(len(exits))) if exits else 0.0,
        "share_would_W": (float(would_w) / float(len(exits))) if exits else 0.0,
    }


__all__ = [
    "CONTRAST_BOOKS",
    "baseline_from_rows",
    "table_t0",
    "table_t1",
    "table_t2",
    "table_t3",
    "table_t4",
    "table_t5",
]
