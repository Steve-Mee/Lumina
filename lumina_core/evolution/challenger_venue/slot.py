"""Single active challenger slot (K9)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lumina_core.evolution.challenger_venue.dna_namespace import challenger_state_root


def slot_path(workspace: Path | str) -> Path:
    root = challenger_state_root(workspace)
    root.mkdir(parents=True, exist_ok=True)
    return root / "slot.json"


def load_slot(workspace: Path | str) -> dict[str, Any]:
    path = slot_path(workspace)
    if not path.is_file():
        return {"active": None, "queued": None, "fitness": float("-inf")}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"active": None, "queued": None, "fitness": float("-inf")}
    return dict(raw) if isinstance(raw, dict) else {"active": None, "queued": None}


def save_slot(workspace: Path | str, payload: dict[str, Any]) -> None:
    slot_path(workspace).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def try_occupy(
    workspace: Path | str,
    *,
    candidate_id: str,
    fitness: float,
) -> dict[str, Any]:
    """Occupy if empty. Queue if busy. Replace only on strict fitness lift."""
    slot = load_slot(workspace)
    active = slot.get("active")
    current_fit = float(slot.get("fitness") if slot.get("fitness") is not None else float("-inf"))
    if not active:
        slot = {"active": candidate_id, "queued": None, "fitness": float(fitness)}
        save_slot(workspace, slot)
        return {"status": "occupied", **slot}
    if float(fitness) > current_fit:
        slot = {"active": candidate_id, "queued": None, "fitness": float(fitness), "replaced": active}
        save_slot(workspace, slot)
        return {"status": "replaced", **slot}
    slot["queued"] = candidate_id
    save_slot(workspace, slot)
    return {"status": "queued", **slot}
