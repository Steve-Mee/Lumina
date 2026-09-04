"""PATH_SHAPE K3 DEAD tables Tm + T0–T4. Shape flatten. No fill formula change."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_edge import policy_only_rows
from lumina_core.birth.awakening_entry_autopsy_tables import read_existing_hole_contrast
from lumina_core.birth.awakening_mech import bucket_stats, load_close_jsonl, split_close_rows
from lumina_core.birth.awakening_open_split_flags import hole_from_u, universe_rows, winners_from_u
from lumina_core.birth.awakening_path_exit_k3 import PATH_A_NAME, PATH_B_NAME
from lumina_core.birth.awakening_path_exit_k3_flags import (
    compute_path_exit_k3_flags,
    empty_baseline,
    path_exit_k3_rows,
)
from lumina_core.birth.awakening_path_exit_k3_t025 import PATH_T025_A_NAME, PATH_T025_B_NAME
from lumina_core.birth.awakening_path_shape_k3_dead import EPS_SIT, MFE_LIFE, SOURCE
from lumina_core.birth.awakening_path_shape_k3_dead_flags import (
    compute_shape_measure_flags,
    empty_measure,
    mean_stamped_shape,
    mean_stamped_threshold,
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
    ("path_exit_k3_A", PATH_A_NAME),
    ("path_exit_k3_B", PATH_B_NAME),
    ("path_exit_k3_t025_A", PATH_T025_A_NAME),
    ("path_exit_k3_t025_B", PATH_T025_B_NAME),
)


def table_tm(rows: list[dict[str, Any]] | None, *, present: bool = True) -> dict[str, Any]:
    if not present or rows is None:
        return empty_measure(missing=True)
    return compute_shape_measure_flags(rows)


def _bucket_cell(rows: list[dict[str, Any]]) -> dict[str, Any]:
    stats = bucket_stats(rows)
    return {
        "n": int(stats["n"]),
        "wr": float(stats["wr"]),
        "mean_r": float(stats["mean_r"]),
        "mean_usd": float(stats["mean_usd"]),
    }


def _mean_key(rows: list[dict[str, Any]], key: str) -> float | None:
    vals: list[float] = []
    for row in rows:
        raw = row.get(key)
        if raw is None:
            continue
        try:
            vals.append(float(raw))
        except (TypeError, ValueError):
            continue
    if not vals:
        return None
    return float(sum(vals) / float(len(vals)))


def table_t0(
    rows: list[dict[str, Any]],
    *,
    zip_sha256: str,
    ticks_sha16: str,
    price_sha16_value: str,
    optimizer_steps: int,
    hook_enabled: bool,
    shape_enabled: bool,
    t_family_enabled: bool,
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
        "shape_enabled": bool(shape_enabled),
        "T_family_enabled": bool(t_family_enabled),
        "mean_stamped_shape": mean_stamped_shape(rows),
        "n_exit": int(len(path_exit_k3_rows(parts["policy"]))),
        "skip_replay": bool(skip_replay),
        "replay_ran": bool(replay_ran),
        "source": SOURCE,
        "EPS_SIT": float(EPS_SIT),
        "MFE_LIFE": float(MFE_LIFE),
    }


def table_t1(rows: list[dict[str, Any]]) -> dict[str, Any]:
    policy = policy_only_rows(rows)
    universe = universe_rows(policy)
    hole = hole_from_u(universe)
    winners = winners_from_u(universe)
    exits = path_exit_k3_rows(policy)
    pol = bucket_stats(policy)
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
        "wr_policy": float(pol["wr"]),
        "mean_r_policy": float(pol["mean_r"]),
        "mean_mae_r_exit": _mean_key(exits, "path_exit_k3_mae_r"),
        "mean_mfe_r_exit": _mean_key(exits, "path_exit_k3_mfe_r"),
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
        "n_H_shape": int(flags.get("n_H") or 0),
        "delta_n_H": int(flags.get("n_H") or 0) - int(base.get("n_H") or 0),
        "n_W_base": int(base.get("n_W") or 0),
        "n_W_shape": int(flags.get("n_W") or 0),
        "delta_n_W": int(flags.get("n_W") or 0) - int(base.get("n_W") or 0),
        "wr_policy_base": float(base.get("wr_policy") or 0.0),
        "wr_policy_shape": float(flags.get("wr_policy") or 0.0),
        "delta_wr": float(flags.get("wr_policy") or 0.0) - float(base.get("wr_policy") or 0.0),
        "mean_r_policy_base": float(base.get("mean_r_policy") or 0.0),
        "mean_r_policy_shape": float(flags.get("mean_r_policy") or 0.0),
        "delta_mean_r_policy": float(flags.get("mean_r_policy") or 0.0) - float(base.get("mean_r_policy") or 0.0),
        "HOLE_MOVED": bool(flags.get("HOLE_MOVED")),
    }


def _prior_n_exit(artifacts_dir: Path | str | None, name: str) -> dict[str, Any]:
    base = Path(artifacts_dir) if artifacts_dir is not None else reports_dir() / "artifacts"
    path = base / name
    if not path.is_file():
        return {"absent": True, "n_exit": 0, "path": str(path)}
    rows = load_close_jsonl(path)
    return {
        "absent": False,
        "n_exit": int(len(path_exit_k3_rows(policy_only_rows(rows)))),
        "path": str(path),
    }


def table_t3(*, n_exit: int, artifacts: Path | str | None, leg: str) -> dict[str, Any]:
    k27_name = PATH_A_NAME if str(leg).upper() == "A" else PATH_B_NAME
    t025_name = PATH_T025_A_NAME if str(leg).upper() == "A" else PATH_T025_B_NAME
    k27 = _prior_n_exit(artifacts, k27_name)
    t025 = _prior_n_exit(artifacts, t025_name)
    live = int(n_exit)
    return {
        "n_exit_shape": live,
        "n_exit_k27": int(k27.get("n_exit") or 0),
        "n_exit_t025": int(t025.get("n_exit") or 0),
        "k27_absent": bool(k27.get("absent")),
        "t025_absent": bool(t025.get("absent")),
        "delta_vs_k27": live - int(k27.get("n_exit") or 0),
        "delta_vs_t025": live - int(t025.get("n_exit") or 0),
    }


def table_t4(artifacts_dir: Path | str | None = None) -> dict[str, Any]:
    base = Path(artifacts_dir) if artifacts_dir is not None else reports_dir() / "artifacts"
    out: dict[str, Any] = {}
    for key, name in CONTRAST_BOOKS:
        cell = read_existing_hole_contrast(base / name)
        if not (base / name).is_file():
            cell = {"absent": True}
        out[key] = cell
    return out


__all__ = [
    "CONTRAST_BOOKS",
    "mean_stamped_threshold",
    "table_t0",
    "table_t1",
    "table_t2",
    "table_t3",
    "table_t4",
    "table_tm",
]
