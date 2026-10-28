"""SELECT_OBJ P_BOUNCE_WEAK tables Tm + T0 + T4. Measure-only. No flatten books."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_edge import policy_only_rows
from lumina_core.birth.awakening_entry_autopsy_tables import read_existing_hole_contrast
from lumina_core.birth.awakening_path_exit_k3 import PATH_A_NAME, PATH_B_NAME, PATH_EARLY_A_NAME, PATH_EARLY_B_NAME
from lumina_core.birth.awakening_path_exit_k3_t025 import PATH_T025_A_NAME, PATH_T025_B_NAME
from lumina_core.birth.awakening_path_shape_k3_dead import PATH_SHAPE_A_NAME, PATH_SHAPE_B_NAME
from lumina_core.birth.awakening_select import reports_dir
from lumina_core.birth.awakening_select_obj_bounce import (
    BOUNCE_WEAK,
    KNOWN_PATH_EARLY_A_SHA256,
    KNOWN_PATH_EARLY_B_SHA256,
    PATH_EARLY_FLAGS_NAME,
    SOURCE,
)
from lumina_core.birth.awakening_select_obj_bounce_flags import compute_obj_bounce_flags, empty_measure

CONTRAST_BOOKS = (
    ("path_early_A", PATH_EARLY_A_NAME),
    ("path_early_B", PATH_EARLY_B_NAME),
    ("path_exit_k3_A", PATH_A_NAME),
    ("path_exit_k3_B", PATH_B_NAME),
    ("path_exit_k3_t025_A", PATH_T025_A_NAME),
    ("path_exit_k3_t025_B", PATH_T025_B_NAME),
    ("path_shape_k3_dead_A", PATH_SHAPE_A_NAME),
    ("path_shape_k3_dead_B", PATH_SHAPE_B_NAME),
)


def table_tm(rows: list[dict[str, Any]] | None, *, present: bool = True) -> dict[str, Any]:
    if not present or rows is None:
        return empty_measure(missing=True)
    return compute_obj_bounce_flags(rows)


def _n_policy_from_flags(artifacts: Path | str | None, *, leg: str) -> int | None:
    base = Path(artifacts) if artifacts is not None else reports_dir() / "artifacts"
    path = base / PATH_EARLY_FLAGS_NAME
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    block = payload.get(str(leg).upper()) or {}
    raw = block.get("n_policy")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def table_t0(
    rows: list[dict[str, Any]] | None,
    *,
    sha_a: str,
    sha_b: str,
    optimizer_steps: int,
    hooks_false: bool,
    artifacts: Path | str | None = None,
    present: bool = True,
    n_policy: int | None = None,
) -> dict[str, Any]:
    n_policy_a = _n_policy_from_flags(artifacts, leg="A")
    n_policy_b = _n_policy_from_flags(artifacts, leg="B")
    if n_policy is not None:
        n_live = int(n_policy)
    elif present and rows is not None:
        n_live = int(len(policy_only_rows(rows)))
    else:
        n_live = int(n_policy_a or 0)
    return {
        "path_early_A_sha256": str(sha_a),
        "path_early_B_sha256": str(sha_b),
        "path_early_A_sha256_known": KNOWN_PATH_EARLY_A_SHA256,
        "path_early_B_sha256_known": KNOWN_PATH_EARLY_B_SHA256,
        "sha_match": str(sha_a) == KNOWN_PATH_EARLY_A_SHA256 and str(sha_b) == KNOWN_PATH_EARLY_B_SHA256,
        "n_policy": int(n_live),
        "n_policy_flags_A": n_policy_a,
        "n_policy_flags_B": n_policy_b,
        "optimizer_steps": int(optimizer_steps),
        "hooks_false": bool(hooks_false),
        "source": SOURCE,
        "BOUNCE_WEAK": float(BOUNCE_WEAK),
        "replay_ran": False,
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


__all__ = ["CONTRAST_BOOKS", "table_t0", "table_t4", "table_tm"]
