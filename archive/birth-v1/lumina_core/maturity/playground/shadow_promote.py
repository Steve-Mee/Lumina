"""Shadow proof before a method may place SIM orders.

A shadow row has no order id and cannot enter the Playground tape.
Proving Ground and REAL refuse promotion. A promotion resets the green-day clock.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.maturity.playground.sense_lab import load_sense

SHADOW_MIN = int(POLICY_EDGE_MIN_TRADES)
CANDIDATES = ("h1", "h2")


def promotion_allowed(workspace_root: Path | str) -> bool:
    from lumina_core.maturity.continuum import load_continuum

    phase = str(load_continuum(Path(workspace_root)).get("active_phase") or "")
    return phase not in {"proving_ground", "real"}


def evaluate_shadow_promotion(workspace_root: Path | str) -> dict[str, Any]:
    """Measure only. Does not write the tape and does not promote by itself."""
    if not promotion_allowed(workspace_root):
        return {"ok": False, "reason": "promotion_frozen", "pass_now": False}
    state = load_sense(workspace_root)
    resolved = [row for row in list(state.get("resolved") or []) if isinstance(row, dict)]
    live = _live_mean_r(workspace_root)
    touch = _mean(resolved, "null_b")
    touch_n = _count(resolved, "null_b")
    if touch_n < SHADOW_MIN or touch is None:
        return {"ok": False, "reason": "first_touch_inconclusive", "pass_now": False, "n": touch_n}
    best_name = ""
    best_mean: float | None = None
    for name in CANDIDATES:
        n = _count(resolved, name)
        mean_r = _mean(resolved, name)
        if n < SHADOW_MIN or mean_r is None:
            continue
        if mean_r <= 0.0 or mean_r <= touch or mean_r <= live:
            continue
        if best_mean is None or mean_r > best_mean:
            best_name = name
            best_mean = mean_r
    if not best_name or best_mean is None:
        return {"ok": False, "reason": "no_method_beats_the_book", "pass_now": False}
    return {
        "ok": True,
        "reason": "shadow_proven",
        "method": best_name,
        "mean_r": best_mean,
        "pass_now": False,
    }


def promote_if_proven(workspace_root: Path | str) -> dict[str, Any]:
    """Retired by ADR-0056. H1/H2 do not become the hand."""
    del workspace_root
    return {"ok": False, "reason": "search_retired", "reset_streak": False, "pass_now": False}


def living_override_side(workspace_root: Path | str) -> int | None:
    """ADR-0056. H1/H2 and the frozen policy do not choose a Playground side."""
    del workspace_root
    return None


def _count(rows: list[dict[str, Any]], name: str) -> int:
    return sum(1 for row in rows if str(row.get("name")) == name and row.get("r") is not None)


def _mean(rows: list[dict[str, Any]], name: str) -> float | None:
    values = [float(row["r"]) for row in rows if str(row.get("name")) == name and row.get("r") is not None]
    if not values:
        return None
    return sum(values) / float(len(values))


def _live_mean_r(workspace_root: Path | str) -> float:
    from lumina_core.maturity.playground.tape import tape_skill_metrics

    metrics = tape_skill_metrics(workspace_root)
    mean_r = metrics.get("mean_r")
    n_p = int(metrics.get("n_p") or 0)
    if n_p <= 0 or mean_r is None:
        return 0.0
    try:
        return float(mean_r)
    except (TypeError, ValueError):
        return 0.0


def _sign(value: Any) -> int | None:
    if value in (1, -1):
        return int(value)
    return None
