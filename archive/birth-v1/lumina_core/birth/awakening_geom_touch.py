"""G2 first-touch gate. TARGET_FRAC_MIN==0.10 is the world-can-pay floor, not 0.46."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_edge import policy_only_rows
from lumina_core.birth.awakening_geom_reward import map_close_reason
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES

TARGET_FRAC_MIN = 0.10  # TARGET_FRAC_MIN==0.10
G2_NAME = "g2_first_touch.json"


def first_touch_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    policy = policy_only_rows(list(rows or []))
    n_target = n_stop = n_time = 0
    for row in policy:
        kind = map_close_reason(str(row.get("close_reason") or ""))
        if kind == "target":
            n_target += 1
        elif kind == "stop":
            n_stop += 1
        else:
            n_time += 1
    n_policy = int(len(policy))
    denom = float(n_policy) if n_policy > 0 else 0.0
    target_frac = (float(n_target) / denom) if denom else 0.0
    stop_frac = (float(n_stop) / denom) if denom else 0.0
    time_frac = (float(n_time) / denom) if denom else 0.0
    return {
        "n_policy": n_policy,
        "n_target": int(n_target),
        "n_stop": int(n_stop),
        "n_time": int(n_time),
        "target_frac": float(target_frac),
        "stop_frac": float(stop_frac),
        "time_frac": float(time_frac),
    }


def first_touch_books(rows_a: list[dict[str, Any]], rows_b: list[dict[str, Any]]) -> dict[str, Any]:
    book_a = first_touch_from_rows(rows_a)
    book_b = first_touch_from_rows(rows_b)
    n_a = int(book_a["n_policy"])
    n_b = int(book_b["n_policy"])
    n_pooled = n_a + n_b
    n_target = int(book_a["n_target"]) + int(book_b["n_target"])
    n_stop = int(book_a["n_stop"]) + int(book_b["n_stop"])
    n_time = int(book_a["n_time"]) + int(book_b["n_time"])
    denom = float(n_pooled) if n_pooled > 0 else 0.0
    target_frac = (float(n_target) / denom) if denom else 0.0
    stop_frac = (float(n_stop) / denom) if denom else 0.0
    time_frac = (float(n_time) / denom) if denom else 0.0
    baseline_thin = (n_a < int(POLICY_EDGE_MIN_TRADES)) or (n_b < int(POLICY_EDGE_MIN_TRADES))
    unhittable = (not baseline_thin) and (target_frac < float(TARGET_FRAC_MIN))
    return {
        "n_policy_A": n_a,
        "n_policy_B": n_b,
        "n_policy_pooled": n_pooled,
        "n_target": n_target,
        "n_stop": n_stop,
        "n_time": n_time,
        "target_frac": float(target_frac),
        "stop_frac": float(stop_frac),
        "time_frac": float(time_frac),
        "unhittable": bool(unhittable),
        "baseline_thin": bool(baseline_thin),
        "TARGET_FRAC_MIN": float(TARGET_FRAC_MIN),
        "A": book_a,
        "B": book_b,
    }


def write_g2_first_touch(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "n_policy_A": int(payload.get("n_policy_A") or 0),
        "n_policy_B": int(payload.get("n_policy_B") or 0),
        "n_policy_pooled": int(payload.get("n_policy_pooled") or 0),
        "n_target": int(payload.get("n_target") or 0),
        "n_stop": int(payload.get("n_stop") or 0),
        "n_time": int(payload.get("n_time") or 0),
        "target_frac": float(payload.get("target_frac") or 0.0),
        "stop_frac": float(payload.get("stop_frac") or 0.0),
        "time_frac": float(payload.get("time_frac") or 0.0),
        "unhittable": bool(payload.get("unhittable")),
        "TARGET_FRAC_MIN": float(TARGET_FRAC_MIN),
    }
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return body


assert TARGET_FRAC_MIN == 0.10

__all__ = [
    "G2_NAME",
    "TARGET_FRAC_MIN",
    "first_touch_books",
    "first_touch_from_rows",
    "write_g2_first_touch",
]
