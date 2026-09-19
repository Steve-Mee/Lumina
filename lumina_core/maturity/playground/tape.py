"""Playground SIM tape — policy-only closes. JSON stamps are not rows."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

from lumina_core.birth.foundation_metrics import skill_winrate

TAPE_REL = Path("state") / "lumina_playground_tape.jsonl"


def tape_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / TAPE_REL


def load_tape_rows(workspace_root: Path | str) -> list[dict[str, Any]]:
    path = tape_path(workspace_root)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except ValueError:
            continue
        if isinstance(raw, dict):
            rows.append(raw)
    return rows


def append_tape_row(workspace_root: Path | str, row: dict[str, Any]) -> None:
    path = tape_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(row)
    payload.setdefault("ts", datetime.now(timezone.utc).isoformat())
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def tape_skill_metrics(workspace_root: Path | str) -> dict[str, Any]:
    """n_P / WR / mean R / process-R from policy closes only."""
    rows = load_tape_rows(workspace_root)
    policy_closes = [r for r in rows if _is_policy_close(r)]
    plant_closes = [r for r in rows if _is_close(r) and not _is_policy(r)]
    fills = [r for r in rows if str(r.get("kind") or "") in {"fill", "close", "entry"}]
    r_series = [_f(r.get("r")) for r in policy_closes]
    r_ok = [x for x in r_series if x is not None]
    losses = [abs(x) for x in r_ok if x < 0]
    wins = sum(1 for r in policy_closes if bool(r.get("win")) or (_f(r.get("r")) or 0.0) > 0.0)
    n_p = len(policy_closes)
    mean_r = (sum(r_ok) / float(len(r_ok))) if r_ok else None
    median_loss = float(median(losses)) if losses else (0.0 if n_p > 0 else None)
    return {
        "n_p": n_p,
        "n_plant": len(plant_closes),
        "n_fills": len(fills),
        "skill_wr": None if n_p <= 0 else skill_winrate(trades=n_p, wins=wins),
        "mean_r": mean_r,
        "median_loss_r": median_loss,
        "policy_only": True,
        "has_orderpath_fill": any(_is_orderpath(r) for r in rows),
    }


def _is_close(row: dict[str, Any]) -> bool:
    return str(row.get("kind") or "") == "close"


def _is_policy(row: dict[str, Any]) -> bool:
    return bool(row.get("policy"))


def _is_policy_close(row: dict[str, Any]) -> bool:
    return _is_close(row) and _is_policy(row)


def _is_orderpath(row: dict[str, Any]) -> bool:
    return str(row.get("source") or "") in {"orderpath", "ops_place_order", "venue_fill"}


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
