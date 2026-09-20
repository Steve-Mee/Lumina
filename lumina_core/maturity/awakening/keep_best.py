"""Prefer-better incumbent. A worse child never replaces frozen π*."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from lumina_core.birth.foundation_metrics import S3_OCCUPANCY_MAX, S3_OCCUPANCY_MIN
from lumina_core.maturity.awakening.progress import load_awakening_progress

INCUMBENT_ZIP_NAME = "awakening_incumbent_pi_star.zip"


def incumbent_zip(workspace_root: Path) -> Path:
    from lumina_core.maturity.phase_runners.awakening_shot import artifacts_dir

    return artifacts_dir(Path(workspace_root)) / INCUMBENT_ZIP_NAME


def occupancy_in_exam_band(occupancy: float | None) -> bool:
    if occupancy is None:
        return False
    return S3_OCCUPANCY_MIN - 1e-12 <= float(occupancy) <= S3_OCCUPANCY_MAX + 1e-12


def incumbent_from_shot(shot: dict[str, Any]) -> dict[str, Any]:
    return {
        "incumbent_n_b": int(shot.get("policy_trades") or shot.get("n_b") or 0),
        "incumbent_wr": shot.get("polish_oos_winrate", shot.get("wr")),
        "incumbent_mean_r": shot.get("mean_r"),
        "incumbent_sha": str(shot.get("child_sha256") or shot.get("incumbent_sha") or ""),
        "incumbent_occupancy": shot.get("occupancy"),
        "incumbent_edge": shot.get("edge"),
        "incumbent_sharpe": shot.get("oos_sharpe", shot.get("sharpe")),
        "incumbent_dd_pct": shot.get("oos_dd_pct", shot.get("dd_pct")),
        "incumbent_median_loss_r": shot.get("median_loss_r"),
        "incumbent_n_plant": int(shot.get("n_plant") or 0),
    }


def progress_from_incumbent(incumbent: dict[str, Any]) -> dict[str, Any]:
    """HUD/law fields follow the kept organism, not a discarded shot."""
    return {
        "n_b": int(incumbent.get("incumbent_n_b") or 0),
        "wr": incumbent.get("incumbent_wr"),
        "mean_r": incumbent.get("incumbent_mean_r"),
        "child_sha": str(incumbent.get("incumbent_sha") or ""),
        "occupancy": incumbent.get("incumbent_occupancy"),
        "edge": incumbent.get("incumbent_edge"),
        "sharpe": incumbent.get("incumbent_sharpe"),
        "dd_pct": incumbent.get("incumbent_dd_pct"),
        "median_loss_r": incumbent.get("incumbent_median_loss_r"),
        "n_plant": int(incumbent.get("incumbent_n_plant") or 0),
    }


def child_beats_incumbent(child: dict[str, Any], incumbent: dict[str, Any]) -> bool:
    """Keep a child that is not a skill regression.

    Live freeze: n_B 131 < 150 discarded a WR *gain* (33.6% vs 32%) so every
    cycle restored π* and the HUD never moved. Volume-down + skill-up is
    prefer-better. Volume-up + WR and mean_r both down is taxi, discard.
    """
    if not occupancy_in_exam_band(_f(child.get("occupancy"))):
        return False
    n_b = int(child.get("policy_trades") or child.get("n_b") or 0)
    inc_n = int(incumbent.get("incumbent_n_b") or 0)
    wr = _f(child.get("polish_oos_winrate", child.get("wr")))
    mean_r = _f(child.get("mean_r"))
    inc_wr = _f(incumbent.get("incumbent_wr"))
    inc_mean = _f(incumbent.get("incumbent_mean_r"))
    wr_worse = wr is not None and inc_wr is not None and float(wr) + 1e-12 < float(inc_wr)
    mean_worse = mean_r is not None and inc_mean is not None and float(mean_r) + 1e-12 < float(inc_mean)
    if wr_worse and mean_worse:
        return False
    if wr_worse and mean_r is None:
        return False
    if mean_worse and wr is None:
        return False
    wr_better = wr is not None and inc_wr is not None and float(wr) > float(inc_wr) + 1e-12
    mean_better = mean_r is not None and inc_mean is not None and float(mean_r) > float(inc_mean) + 1e-12
    n_better = n_b > inc_n
    return bool(wr_better or mean_better or n_better)


def persist_incumbent_proof(workspace_root: Path, incumbent: dict[str, Any]) -> None:
    """Evolution-proof disk SSOT follows the kept organism, not a discarded shot."""
    from lumina_core.birth.birth_exit_policy_export import file_sha256
    from lumina_core.birth.evolution_proof_gate import record_and_evaluate_at_certificate
    from lumina_core.birth.fitness_vector import load_fitness_vector
    from lumina_core.maturity.phase_runners.awakening_shot import (
        CHILD_META_NAME,
        CHILD_SCHEMA,
        artifacts_dir,
        live_child_zip,
    )

    root = Path(workspace_root)
    wr = _f(incumbent.get("incumbent_wr"))
    n_b = int(incumbent.get("incumbent_n_b") or 0)
    prog = load_awakening_progress(root)
    parent = _f(prog.get("parent_holdout_wr") if prog.get("parent_same_tape") else None)
    if parent is not None:
        birth = float(parent)
    else:
        vector = load_fitness_vector(root)
        birth = float(vector.oos_wr) if vector is not None else 0.0
    record_and_evaluate_at_certificate(
        root,
        eval_result={"oos_winrate": float(wr or 0.0), "holdout_trades": n_b},
        birth_exit_winrate=birth,
    )
    child = live_child_zip(root)
    sha = file_sha256(child) if child.is_file() else str(incumbent.get("incumbent_sha") or "")
    reports = artifacts_dir(root)
    reports.mkdir(parents=True, exist_ok=True)
    sidecar = {
        "schema": CHILD_SCHEMA,
        "path": str(child),
        "sha256": sha,
        "init_sha256": "",
        "oos_winrate": float(wr or 0.0),
        "holdout_trades": n_b,
        "birth_exit_winrate": birth,
        "incumbent": True,
    }
    (reports / CHILD_META_NAME).write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")


def copy_zip(src: Path, dest: Path) -> None:
    from lumina_core.maturity.awakening.freeze_pin import refuse_birth_pi_star_write

    if not src.is_file() or src.stat().st_size <= 0:
        return
    refuse_birth_pi_star_write(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "INCUMBENT_ZIP_NAME",
    "child_beats_incumbent",
    "copy_zip",
    "incumbent_from_shot",
    "incumbent_zip",
    "progress_from_incumbent",
    "occupancy_in_exam_band",
    "persist_incumbent_proof",
]
