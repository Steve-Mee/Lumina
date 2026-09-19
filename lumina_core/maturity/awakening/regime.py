"""Holdout regime visibility — attempt every slice; empty tape is INCONCLUSIVE."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.s5_process_decomp import HOLDOUT_REGIMES

OPERATOR_SLICES: tuple[str, ...] = ("trend", "range", "mixed")
INCONCLUSIVE = "INCONCLUSIVE"

_TREND = frozenset({"TREND_UP", "TREND_DOWN", "trend", "TREND"})
_RANGE = frozenset({"NEUTRAL", "range", "RANGE", "CHOP"})


def _operator_label(raw: str) -> str:
    token = str(raw or "").strip()
    if token in _TREND:
        return "trend"
    if token in _RANGE:
        return "range"
    return "mixed"


def _row_regime(row: dict[str, Any]) -> str | None:
    for key in ("regime", "regime_name", "market_regime"):
        val = row.get(key)
        if val:
            return _operator_label(str(val))
    return None


def attempt_regime_slices(
    rows: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Always attempt trend/range/mixed. Missing tape → INCONCLUSIVE, never skip."""
    buckets: dict[str, list[dict[str, Any]]] = {name: [] for name in OPERATOR_SLICES}
    unlabeled = 0
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        label = _row_regime(row)
        if label is None:
            unlabeled += 1
            continue
        buckets[label].append(row)
    status: dict[str, str] = {}
    observed: list[str] = []
    for name in OPERATOR_SLICES:
        status[name] = "observed" if buckets[name] else INCONCLUSIVE
        if buckets[name]:
            observed.append(name)
    return {
        "slices": list(OPERATOR_SLICES),
        "status": status,
        "counts": {name: len(buckets[name]) for name in OPERATOR_SLICES},
        "observed": observed,
        "unlabeled": unlabeled,
        "holdout_regimes": list(HOLDOUT_REGIMES),
        "attempted": True,
        "visibility_ok": len(observed) > 0,
    }
