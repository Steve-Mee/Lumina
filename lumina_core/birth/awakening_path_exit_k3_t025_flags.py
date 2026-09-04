"""PATH_EXIT K3 T025 transfer license + n_exit vs T_LOCK clone. Do not retune #27 flags."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.awakening_edge import policy_only_rows
from lumina_core.birth.awakening_path_exit_k3 import FAMILY, T_LOCK
from lumina_core.birth.awakening_path_exit_k3_flags import path_exit_k3_rows
from lumina_core.birth.awakening_path_exit_k3_t025 import PathExitK3T025ProtocolError, T_FP

TAG_TRANSFER_OK = "TRANSFER_OK"
TAG_TRANSFER_FAIL = "TRANSFER_FAIL"
TAG_S_HARM = "S_HARM"
TAG_S_MISSING = "S_MISSING"


def mean_stamped_threshold(rows: list[dict[str, Any]]) -> float | None:
    exits = path_exit_k3_rows(policy_only_rows(rows))
    vals: list[float] = []
    for row in exits:
        raw = row.get("path_exit_k3_threshold") if "path_exit_k3_threshold" in row else None
        if raw is None:
            continue
        try:
            vals.append(float(raw))
        except (TypeError, ValueError):
            continue
    if not vals:
        return None
    return float(sum(vals) / float(len(vals)))


def assert_n_exit_not_tlock_clone(
    *,
    n_exit_a: int,
    mean_stamped_threshold_a: float | None,
) -> None:
    n = int(n_exit_a)
    if n >= 80:
        raise PathExitK3T025ProtocolError("n_exit A >= 80 — hook is <=0 or broken")
    if n <= 0:
        return
    if mean_stamped_threshold_a is None:
        raise PathExitK3T025ProtocolError("A exits missing path_exit_k3_threshold stamp")
    stamped = float(mean_stamped_threshold_a)
    if abs(stamped - T_LOCK) <= 1e-9:
        raise PathExitK3T025ProtocolError(
            "mean stamped path_exit_k3_threshold on A is T_LOCK — T025 flattened on the wrong constant"
        )
    if n in {48, 49, 50, 51, 52} and abs(stamped - T_LOCK) <= 1e-9:
        raise PathExitK3T025ProtocolError("n_exit A is a T_LOCK clone")
    _ = T_FP


def license_transfer(flags_a: dict[str, Any], flags_b: dict[str, Any]) -> dict[str, Any]:
    moved_a = bool(flags_a.get("HOLE_MOVED"))
    moved_b = bool(flags_b.get("HOLE_MOVED"))
    if flags_a.get("S_MISSING_HOOK") or flags_b.get("S_MISSING_HOOK"):
        tag = TAG_S_MISSING
    elif flags_a.get("S_HARM") or flags_b.get("S_HARM"):
        tag = TAG_S_HARM
    elif moved_a and moved_b:
        tag = TAG_TRANSFER_OK
    else:
        tag = TAG_TRANSFER_FAIL
    return {
        "tag": tag,
        "law": "SHADOW",
        "licensed_next_family": FAMILY,
        "gate1": "SHADOW",
        "HOLE_MOVED_A": moved_a,
        "HOLE_MOVED_B": moved_b,
    }


__all__ = [
    "TAG_S_HARM",
    "TAG_S_MISSING",
    "TAG_TRANSFER_FAIL",
    "TAG_TRANSFER_OK",
    "assert_n_exit_not_tlock_clone",
    "license_transfer",
    "mean_stamped_threshold",
]
